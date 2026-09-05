#!/usr/bin/env python3
"""Enforcement feed: primary-source federal and state enforcement records, fetched daily and backfilled to 2024.

Sources (public records, never journalism):
  DOJ      Department of Justice press releases, official JSON API (https://www.justice.gov/api/v1/press_releases.json).
           Kept when the release carries the "Healthcare Fraud" topic tag or the title names a health program or setting.
  OIG      HHS Office of Inspector General enforcement actions listing (https://oig.hhs.gov/fraud/enforcement/), which also
           carries State Enforcement Agencies (state attorneys general and Medicaid fraud control units).

Writes data/enforcement/raw.jsonl (append-only, one record per source id, resumable) and loads it into DuckDB table
enforcement_raw. Network work never holds the warehouse lock: the DuckDB load is a single short transaction at the end.

Usage:
  .venv/bin/python ingest/10_enforcement_feed.py                 # backfill from 2024-01-01, or resume from the newest stored record
  .venv/bin/python ingest/10_enforcement_feed.py --since 2026-08-01
  .venv/bin/python ingest/10_enforcement_feed.py --daily          # last 7 days only, for the scheduled run
  .venv/bin/python ingest/10_enforcement_feed.py --load-only      # skip the network, just load raw.jsonl into DuckDB
"""
import argparse, concurrent.futures as cf, datetime as dt, html, json, os, re, ssl, sys, time
import urllib.parse, urllib.request
import certifi
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
SSL_CTX = ssl.create_default_context(cafile=certifi.where())   # the bundled macOS Python has no CA store; curl uses the keychain, urllib does not
RAW_DIR = "data/enforcement"; RAW = os.path.join(RAW_DIR, "raw.jsonl"); os.makedirs(RAW_DIR, exist_ok=True)
UA = "Mozilla/5.0 (compatible; Verity provider-integrity research; contact via repository)"
DOJ_API = "https://www.justice.gov/api/v1/press_releases.json"
OIG_LIST = "https://oig.hhs.gov/fraud/enforcement/"
HEALTH_TITLE = re.compile(r"\b(medicare|medicaid|health ?care|hospice|home health|nursing|pharmac|physician|doctor|clinic|hospital|"
                          r"laborator|dme|durable medical|telemedicine|telehealth|genetic test|opioid|prescri|kickback|"
                          r"behavioral health|mental health|autism|substance|addiction|ambulance|dental|chiropract|optometr|"
                          r"skilled nursing|assisted living|personal care|caregiver|hhs|cms)\b", re.I)
HEALTH_TOPICS = {"healthcare fraud", "health care fraud"}

def log(*a): print(time.strftime("%H:%M:%S"), *a, flush=True)

def get(url, retries=5, timeout=40):
    """GET with retries and backoff. Returns text or raises after the last attempt."""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json,text/html;q=0.9,*/*;q=0.8"})
            with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r: return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e; time.sleep(min(30, 1.5 * (2 ** i)))
    raise RuntimeError(f"GET failed after {retries} attempts: {url}: {last}")

def strip_html(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s or "", flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("—", ", ").replace("–", " to ").replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", re.sub(r"[ \t]{2,}", " ", s)).strip()

# ------------------------------------------------------------------ existing records (resume)
def load_existing():
    ids, newest = set(), None
    if os.path.exists(RAW):
        with open(RAW, encoding="utf-8") as f:
            for line in f:
                try: r = json.loads(line)
                except Exception: continue
                ids.add(r["source_id"])
                if r.get("published") and (newest is None or r["published"] > newest): newest = r["published"]
    return ids, newest

def append(records):
    with open(RAW, "a", encoding="utf-8") as f:
        for r in records: f.write(json.dumps(r, ensure_ascii=False) + "\n")

# ------------------------------------------------------------------ DOJ
STATE_ABBR = {"alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA","colorado":"CO","connecticut":"CT","delaware":"DE","district of columbia":"DC",
  "florida":"FL","georgia":"GA","hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS","kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD",
  "massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS","missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ",
  "new mexico":"NM","new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK","oregon":"OR","pennsylvania":"PA","puerto rico":"PR","rhode island":"RI",
  "south carolina":"SC","south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT","virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI","wyoming":"WY"}
def district_state(component_names):
    """'USAO - Florida, Southern' -> 'FL'. Main Justice components (Criminal Division, Civil Division) have no state."""
    for c in component_names:
        m = re.match(r"USAO\s*-\s*([A-Za-z .]+?)(?:,|$)", c or "")
        if m:
            st = STATE_ABBR.get(m.group(1).strip().lower())
            if st: return st
    return None

def doj_is_health(rec):
    topics = {t.get("name", "").strip().lower() for t in (rec.get("topic") or []) if isinstance(t, dict)}
    if topics & HEALTH_TOPICS: return True
    return bool(HEALTH_TITLE.search(rec.get("title") or ""))

def fetch_doj(since, existing):
    """Page the DOJ API newest-first until the page's oldest release is before `since`. Returns new health records."""
    out, page, seen_pages = [], 0, 0
    while True:
        url = f"{DOJ_API}?pagesize=50&page={page}&sort=date&direction=DESC"
        data = json.loads(get(url)); rows = data.get("results") or []
        if not rows: break
        oldest = None
        for r in rows:
            d = dt.datetime.fromtimestamp(int(r["date"]), dt.UTC).date()
            oldest = d if oldest is None or d < oldest else oldest
            if d < since: continue
            sid = f"doj:{r['uuid']}"
            if sid in existing or not doj_is_health(r): continue
            comps = [c.get("name", "") for c in (r.get("component") or []) if isinstance(c, dict)]
            out.append(dict(source="DOJ", source_id=sid, url=r.get("url"), source_url=r.get("url"), title=strip_html(r.get("title")), published=d.isoformat(),
                            category=", ".join(t.get("name", "") for t in (r.get("topic") or []) if isinstance(t, dict)) or None,
                            district=", ".join(comps) or None, state=district_state(comps), body=strip_html(r.get("body"))[:14000],
                            fetched_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds")))
            existing.add(sid)
        seen_pages += 1
        if seen_pages % 20 == 0: log(f"DOJ page {page}: oldest {oldest}, kept {len(out):,} so far")
        if oldest is not None and oldest < since: break
        page += 1
    return out

# ------------------------------------------------------------------ OIG
MONTHS = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"sept":9,"oct":10,"nov":11,"dec":12}
def parse_ap_date(s):
    """'Sept. 3, 2026', 'March 12, 2025', 'Aug. 27, 2026' -> date"""
    m = re.match(r"\s*([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})", s or "")
    if not m: return None
    mon = MONTHS.get(m.group(1).lower()[:4]) or MONTHS.get(m.group(1).lower()[:3])
    return dt.date(int(m.group(3)), mon, int(m.group(2))) if mon else None

CARD = re.compile(r'<li class="usa-card[^"]*">(.*?)</li>\s*(?=<li class="usa-card|</ul>)', re.S)
CARD_LINK = re.compile(r'<h2 class="usa-card__heading">\s*<a href="([^"]+)">(.*?)</a>', re.S)
CARD_DATE = re.compile(r'<span class="text-base-dark[^"]*">([^<]+)</span>')
CARD_TAG = re.compile(r'<li class="[^"]*usa-tag[^"]*">([^<]+)')   # the card capture ends at the tag's own </li>, so do not require it
ARTICLE = re.compile(r"<article[^>]*>(.*?)</article>", re.S)
MAIN = re.compile(r"<main[^>]*>(.*?)</main>", re.S)
READ_MORE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>\s*Read more on', re.I)

def fetch_oig_detail(rec):
    """OIG detail pages are a summary paragraph plus a 'Read more on <domain>' link to the originating release (DOJ, a state attorney
    general, a Medicaid fraud control unit). Follow it for the full text; keep the OIG summary if the source is unreachable."""
    try:
        h = get(rec["url"], retries=3)
        m = ARTICLE.search(h)
        stub = strip_html(m.group(1) if m else h)
        rec["body"] = stub[:14000]
        rm = READ_MORE.search(m.group(1) if m else h)
        if rm:
            src = html.unescape(rm.group(1)); rec["source_url"] = src
            try:
                h2 = get(src, retries=2, timeout=30)
                m2 = ARTICLE.search(h2) or MAIN.search(h2)
                full = strip_html(m2.group(1) if m2 else h2)
                if len(full) > len(stub): rec["body"] = (stub + "\n\n" + full)[:14000]
            except Exception as e:
                rec["fetch_error"] = f"source: {str(e)[:150]}"
    except Exception as e:
        rec["body"] = ""; rec["fetch_error"] = str(e)[:200]
    return rec

def fetch_oig(since, existing):
    out, page = [], 1
    while True:
        h = get(f"{OIG_LIST}?page={page}")
        cards = CARD.findall(h)
        if not cards: break
        oldest = None
        for c in cards:
            lk = CARD_LINK.search(c); dm = CARD_DATE.search(c)
            if not lk or not dm: continue
            d = parse_ap_date(html.unescape(dm.group(1)))
            if d is None: continue
            oldest = d if oldest is None or d < oldest else oldest
            if d < since: continue
            href = html.unescape(lk.group(1)); url = href if href.startswith("http") else "https://oig.hhs.gov" + href
            sid = "oig:" + url.rstrip("/").rsplit("/", 1)[-1]
            if sid in existing: continue
            tags = [html.unescape(t).strip() for t in CARD_TAG.findall(c)]
            out.append(dict(source="OIG", source_id=sid, url=url, source_url=None, title=strip_html(lk.group(2)), published=d.isoformat(),
                            category=", ".join(tags) or None, district=None, state=None, body=None,
                            fetched_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds")))
            existing.add(sid)
        if page % 10 == 0: log(f"OIG page {page}: oldest {oldest}, kept {len(out):,} so far")
        if oldest is not None and oldest < since: break
        page += 1; time.sleep(0.25)
    # detail pages in a small pool: polite and much faster than serial
    if out:
        log(f"OIG: fetching {len(out):,} detail pages")
        with cf.ThreadPoolExecutor(max_workers=4) as ex:
            for i, _ in enumerate(ex.map(fetch_oig_detail, out), 1):
                if i % 200 == 0: log(f"OIG detail {i:,}/{len(out):,}")
    return out

# ------------------------------------------------------------------ load into DuckDB
def load_duckdb():
    import duckdb
    con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
    con.execute(f"""
    CREATE OR REPLACE TABLE enforcement_raw AS
    SELECT source, source_id, url, source_url, title, CAST(published AS DATE) AS published, category, district, state, body, fetched_at
    FROM read_json('{RAW}', format='newline_delimited', columns={{source:'VARCHAR', source_id:'VARCHAR', url:'VARCHAR', source_url:'VARCHAR', title:'VARCHAR', published:'VARCHAR',
                    category:'VARCHAR', district:'VARCHAR', state:'VARCHAR', body:'VARCHAR', fetched_at:'VARCHAR', fetch_error:'VARCHAR'}})
    QUALIFY row_number() OVER (PARTITION BY source_id ORDER BY fetched_at DESC) = 1""")
    n, lo, hi, ns = con.execute("SELECT COUNT(*), MIN(published), MAX(published), COUNT(*) FILTER (WHERE source='DOJ') FROM enforcement_raw").fetchone()
    con.execute("CHECKPOINT"); con.close()
    log(f"enforcement_raw: {n:,} records ({ns:,} DOJ, {n-ns:,} OIG), {lo} to {hi}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="YYYY-MM-DD; default = newest stored record minus 3 days, or 2024-01-01")
    ap.add_argument("--daily", action="store_true", help="fetch only the last 7 days")
    ap.add_argument("--load-only", action="store_true"); ap.add_argument("--skip-doj", action="store_true"); ap.add_argument("--skip-oig", action="store_true")
    a = ap.parse_args()
    if not a.load_only:
        existing, newest = load_existing()
        if a.daily: since = dt.date.today() - dt.timedelta(days=7)
        elif a.since: since = dt.date.fromisoformat(a.since)
        elif newest: since = dt.date.fromisoformat(newest) - dt.timedelta(days=3)   # overlap so a late-posted record is not missed
        else: since = dt.date(2024, 1, 1)
        log(f"since {since}; {len(existing):,} records already stored")
        if not a.skip_doj:
            t = time.time(); rows = fetch_doj(since, existing); append(rows); log(f"DOJ: {len(rows):,} new health-related releases in {time.time()-t:.0f}s")
        if not a.skip_oig:
            t = time.time(); rows = fetch_oig(since, existing); append(rows); log(f"OIG: {len(rows):,} new enforcement actions in {time.time()-t:.0f}s")
    load_duckdb()
