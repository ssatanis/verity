#!/usr/bin/env python3
"""State Medicaid exclusion lists beyond CA, NY and TX: download each state's published list (ingest/sources/state_exclusion_lists.csv),
find the actual file (xlsx, csv, pdf or an HTML table), and extract rows into the state_exclusions schema. Spreadsheets are read with
pandas and Claude maps the columns; PDFs and HTML tables are read by Claude directly (structured output, one request per chunk).
Every extracted NPI is validated with the check digit. Results land in state_exclusions_claude (with source URL, extraction method and
a confidence note) and are unioned into state_exclusions by ingest/05 on the next run. Writes docs/state_lists_status.md.
Usage: .venv/bin/python ingest/07_state_exclusions_claude.py [--states OH,PA,NJ] [--max-pages 40]"""
import argparse, base64, csv, io, json, os, re, sys, time
import httpx, duckdb, pandas as pd
from pydantic import BaseModel, Field
from typing import List, Optional
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api")
import llm
ap = argparse.ArgumentParser(); ap.add_argument("--states", default=""); ap.add_argument("--max-pages", type=int, default=40); ap.add_argument("--dry", action="store_true"); a = ap.parse_args()
want = {s.strip().upper() for s in a.states.split(",") if s.strip()}
D = "data/state_exclusions/auto"; os.makedirs(D, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Macintosh) Verity/0.1 public-data research", "Accept": "*/*"}
class Row(BaseModel):
    name: str = Field(description="Provider or entity name as printed; for individuals 'Last, First' or 'First Last' as printed")
    is_individual: Optional[bool] = None
    npi: Optional[str] = Field(default=None, description="10 digit NPI if printed, else null")
    license: Optional[str] = None
    provider_type: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    action: Optional[str] = Field(default=None, description="exclusion, termination, suspension, sanction, debarment or reinstatement as printed")
    effective_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD if a date is printed")
    end_date: Optional[str] = Field(default=None, description="ISO end or reinstatement date if printed")
    reason: Optional[str] = None
class Rows(BaseModel):
    rows: List[Row]
    note: Optional[str] = Field(default=None, description="anything a reviewer should know about this chunk, e.g. columns that were ambiguous")
class ColMap(BaseModel):
    name: Optional[str] = None; last_name: Optional[str] = None; first_name: Optional[str] = None; npi: Optional[str] = None; license: Optional[str] = None
    provider_type: Optional[str] = None; city: Optional[str] = None; state: Optional[str] = None; action: Optional[str] = None; effective_date: Optional[str] = None
    end_date: Optional[str] = None; reason: Optional[str] = None; header_row_index: int = Field(description="0-based index of the header row in the sample")
SYS_X = "You extract Medicaid provider exclusion, termination and sanction lists into structured rows. Copy names, identifiers and dates exactly as printed; never guess an NPI; leave fields null when absent. Skip page headers, footers and instructions."
SYS_C = "You map spreadsheet columns of a state Medicaid exclusion list to a fixed schema. Return the exact column header text for each schema field, or null."
def luhn(n):
    if not n or not re.fullmatch(r"[12]\d{9}", str(n)): return None
    s = 24
    for i, ch in enumerate(str(n)[:9]):
        d = int(ch)
        if i % 2 == 0: d = d * 2; d = d - 9 if d > 9 else d
        s += d
    return str(n) if int(str(n)[9]) == (10 - s % 10) % 10 else None
def fetch(url, timeout=90):
    r = httpx.get(url, headers=UA, timeout=timeout, follow_redirects=True); r.raise_for_status(); return r
def find_file_links(html, base):
    links = re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I)
    out = []
    for l in links:
        u = httpx.URL(base).join(l).__str__() if not l.startswith("http") else l
        low = u.lower()
        if re.search(r"\.(xlsx|xls|csv|pdf)(\?|$)", low) and re.search(r"exclu|sanction|terminat|suspend|debar|list|provider", low): out.append(u)
    # de-duplicate, prefer spreadsheets
    seen = []; [seen.append(x) for x in out if x not in seen]
    return sorted(seen, key=lambda u: (0 if re.search(r"\.(xlsx|xls|csv)", u.lower()) else 1))
def html_to_text(html):
    html = re.sub(r"(?is)<(script|style|nav|footer|header).*?</\1>", " ", html)
    html = re.sub(r"(?i)</(tr|p|div|li|h\d)>", "\n", html); html = re.sub(r"(?i)</t[dh]>", " | ", html)
    txt = re.sub(r"<[^>]+>", " ", html); txt = re.sub(r"[ \t]+", " ", txt); txt = re.sub(r"\n\s*\n+", "\n", txt)
    return txt.strip()
def extract_pdf(pdf_bytes, max_pages):
    """Send the PDF to Claude in page chunks; returns rows."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(io.BytesIO(pdf_bytes)); n = min(len(reader.pages), max_pages); rows = []; notes = []
    for start in range(0, n, 12):
        w = PdfWriter()
        for i in range(start, min(start + 12, n)): w.add_page(reader.pages[i])
        buf = io.BytesIO(); w.write(buf); b64 = base64.standard_b64encode(buf.getvalue()).decode()
        r = llm.client().messages.parse(model=llm.MODEL, max_tokens=16000, system=SYS_X, output_config={"effort": "medium"},
              messages=[{"role": "user", "content": [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": b64}},
                                                     {"type": "text", "text": f"Extract every excluded, terminated, suspended or sanctioned provider row on pages {start+1} to {min(start+12, n)}."}]}],
              output_format=Rows)
        out = r.parsed_output; rows += [x.model_dump() for x in out.rows]; notes.append(out.note or "")
    return rows, len(reader.pages), n, [x for x in notes if x]
def extract_text(txt, label):
    rows = []; notes = []
    chunks = [txt[i:i + 60000] for i in range(0, len(txt), 60000)][:8]
    for k, ch in enumerate(chunks):
        out = llm.parse(Rows, SYS_X, f"Source: {label}. Extract every excluded, terminated, suspended or sanctioned provider row from this text.\n\n{ch}", effort="medium")
        rows += [x.model_dump() for x in out.rows]; notes.append(out.note or "")
    return rows, [x for x in notes if x]
def extract_sheet(content, url):
    if url.lower().endswith(".csv") or content[:4] not in (b"PK\x03\x04", b"\xd0\xcf\x11\xe0"):
        df = pd.read_csv(io.BytesIO(content), dtype=str, header=None, encoding_errors="replace")
    else: df = pd.read_excel(io.BytesIO(content), dtype=str, header=None)
    df = df.fillna("")
    sample = df.head(12).to_csv(index=False, header=False)
    cm = llm.parse(ColMap, SYS_C, f"Sample rows (first 12, no header assumed):\n{sample}\n\nReturn the header text for each schema field and the 0-based index of the header row.", effort="low")
    hdr = df.iloc[cm.header_row_index].tolist(); body = df.iloc[cm.header_row_index + 1:]; body.columns = hdr
    def col(field):
        c = getattr(cm, field)
        return body[c] if c in body.columns else pd.Series([""] * len(body), index=body.index)
    rows = []
    for i in range(len(body)):
        nm = str(col("name").iloc[i]).strip() if cm.name else f"{col('first_name').iloc[i]} {col('last_name').iloc[i]}".strip()
        if not nm: continue
        rows.append(dict(name=nm, is_individual=None, npi=str(col("npi").iloc[i]).strip() or None, license=str(col("license").iloc[i]).strip() or None,
                         provider_type=str(col("provider_type").iloc[i]).strip() or None, city=str(col("city").iloc[i]).strip() or None, state=str(col("state").iloc[i]).strip() or None,
                         action=str(col("action").iloc[i]).strip() or None, effective_date=str(col("effective_date").iloc[i]).strip() or None, end_date=str(col("end_date").iloc[i]).strip() or None,
                         reason=str(col("reason").iloc[i]).strip() or None))
    return rows, cm.model_dump()
def run_state(row):
    st, url, fmt = row["state"], row["url"], row["format"]; t0 = time.time()
    status = dict(state=st, url=url, method=None, rows=0, with_npi=0, pages=None, error=None, file=None)
    try:
        r = fetch(url); ct = r.headers.get("content-type", "").lower(); content = r.content; used = url
        if "text/html" in ct and not url.lower().endswith((".pdf", ".xlsx", ".xls", ".csv")):
            links = find_file_links(r.text, url)
            if links:
                for l in links[:3]:
                    try: rr = fetch(l); content = rr.content; ct = rr.headers.get("content-type", "").lower(); used = l; break
                    except Exception as e: status["error"] = f"link {l}: {str(e)[:60]}"
        fname = f"{D}/{st}_{re.sub(r'[^A-Za-z0-9.]+', '_', used.split('/')[-1])[:60]}"
        open(fname, "wb").write(content); status["file"] = fname
        if content[:4] == b"%PDF":
            rows, total, done, notes = extract_pdf(content, a.max_pages); status.update(method="claude_pdf", pages=f"{done}/{total}", notes=notes)
        elif content[:4] == b"PK\x03\x04" or content[:4] == b"\xd0\xcf\x11\xe0" or used.lower().endswith((".csv", ".xlsx", ".xls")):
            rows, cm = extract_sheet(content, used); status.update(method="pandas_claude_colmap", colmap=cm)
        else:
            txt = html_to_text(content.decode("utf-8", "replace"))
            if len(txt) < 400: raise RuntimeError("page has no table text (likely a search portal or javascript)")
            rows, notes = extract_text(txt, f"{st} {used}"); status.update(method="claude_html", notes=notes)
        for x in rows:
            x["npi"] = luhn(re.sub(r"\D", "", str(x.get("npi") or ""))[:10]); x["source_state"] = st; x["source_url"] = used; x["method"] = status["method"]
        status["rows"] = len(rows); status["with_npi"] = sum(1 for x in rows if x["npi"])
        return rows, status
    except Exception as e:
        status["error"] = str(e)[:160]; return [], status
    finally: status["seconds"] = round(time.time() - t0, 1)
if __name__ == "__main__":
    src = list(csv.DictReader(open("ingest/sources/state_exclusion_lists.csv")))
    todo = [r for r in src if r["state"] not in ("CA", "NY", "TX", "MN") and (not want or r["state"] in want)]
    all_rows, statuses = [], []
    for r in todo:
        if a.dry: print("would fetch", r["state"], r["url"]); continue
        rows, st = run_state(r); all_rows += rows; statuses.append(st)
        print(f"{st['state']:<3} {st['method'] or '-':<20} rows={st['rows']:<6} npi={st['with_npi']:<5} {st.get('pages') or ''} {('ERROR ' + st['error']) if st['error'] else ''}", flush=True)
    if a.dry: sys.exit()
    df = pd.DataFrame(all_rows) if all_rows else pd.DataFrame(columns=["name","is_individual","npi","license","provider_type","city","state","action","effective_date","end_date","reason","source_state","source_url","method"])
    for c in ("effective_date", "end_date"): df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    df.to_parquet("data/state_exclusions/auto/state_exclusions_claude.parquet", index=False)
    con = None
    for _ in range(360):   # up to an hour: a detector may hold the write lock
        try: con = duckdb.connect("data/verity.duckdb"); break
        except Exception: time.sleep(10)
    if con is None: sys.exit("could not open the warehouse; rows saved to data/state_exclusions/auto/state_exclusions_claude.parquet")
    if want and con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='state_exclusions_claude'").fetchone()[0]:
        con.execute("DELETE FROM state_exclusions_claude WHERE source_state IN (" + ",".join(f"'{s}'" for s in want) + ")")
        con.execute("INSERT INTO state_exclusions_claude SELECT * FROM df")
    else: con.execute("CREATE OR REPLACE TABLE state_exclusions_claude AS SELECT * FROM df")
    print("state_exclusions_claude:", con.execute("SELECT source_state, COUNT(*), COUNT(npi) FROM state_exclusions_claude GROUP BY 1 ORDER BY 1").fetchall())
    con.execute("CHECKPOINT"); con.close()
    json.dump(statuses, open("data/state_exclusions/auto/status.json", "w"), indent=1, default=str)
    lines = ["# State exclusion list ingestion status", "", "Generated by ingest/07_state_exclusions_claude.py on " + time.strftime("%Y-%m-%d %H:%M") + ". California, New York and Texas are loaded by ingest/05 (native files); Minnesota's list sits behind a captcha and must be downloaded by hand.", "",
             "| state | method | rows | with NPI | pages | result |", "|---|---|---|---|---|---|"]
    for s in statuses: lines.append(f"| {s['state']} | {s['method'] or ''} | {s['rows']} | {s['with_npi']} | {s.get('pages') or ''} | {('error: ' + s['error']) if s['error'] else 'ok'} |")
    open("docs/state_lists_status.md", "w").write("\n".join(lines) + "\n"); print("wrote docs/state_lists_status.md")
