#!/usr/bin/env python3
"""Structured extraction of enforcement records (DOJ, OIG, state attorneys general) into parties and actions.

The model reads one public release and returns a schema: whether it concerns a health care provider or supplier billing a
program, the action type, the parties named (with role, kind, city, state, and any NPI literally printed), programs, scheme and
dollars. Everything downstream is deterministic:
  * the adjudication tier is a fixed mapping from action_type (sentenced, convicted, pleaded guilty, civil judgment = adjudicated;
    charged, indicted, arrested, complaint, settlement, suspension = alleged or administrative), never the model's opinion;
  * DOJ and OIG copies of one release collapse to one event by the originating URL;
  * with no API key a deterministic title-rule fallback runs so the pipeline never blocks, marked model='deterministic'.

Tables: enforcement_actions (one row per event), enforcement_parties (one row per named party). Idempotent on source_id; a stored
batch id is polled rather than resubmitted. Usage: .venv/bin/python scripts/enforcement_extract_claude.py [--limit N] [--sync]
"""
import argparse, concurrent.futures as cf, json, os, re, sys, time
from typing import List, Literal, Optional
import duckdb, pandas as pd
from pydantic import BaseModel, Field
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api")
import llm
ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--sync", action="store_true", help="parallel synchronous calls instead of the Batch API")
ap.add_argument("--workers", type=int, default=6); a = ap.parse_args()

class Party(BaseModel):
    name: str = Field(description="Name exactly as written in the release, without titles like Dr. or Mr.")
    kind: Literal["individual", "organization"]
    role: str = Field(description="owner, operator, physician, nurse practitioner, pharmacist, marketer, patient recruiter, billing company, executive, employee, or similar")
    provider_type: Optional[str] = Field(description="hospice, home health, durable medical equipment, pharmacy, laboratory, clinic, physician practice, behavioral health, telehealth, skilled nursing, personal care, other, or null")
    city: Optional[str]
    state: Optional[str] = Field(description="Two-letter USPS state code or null")
    is_provider: bool = Field(description="True if this party billed, or was enrolled to bill, Medicare, Medicaid or another payer as a provider or supplier; false for recruiters, launderers, straw owners without a billing entity")
    npi: Optional[str] = Field(description="A ten-digit National Provider Identifier only if it is printed in the text; otherwise null. Never guess.")

class Extraction(BaseModel):
    relevant: bool = Field(description="True only if the release concerns health care providers or suppliers and claims to Medicare, Medicaid, CHIP, TRICARE or a health insurer. Drug trafficking without billing, research grant fraud, and clinical misconduct without claims are not relevant.")
    action_type: Literal["sentenced", "convicted", "pleaded_guilty", "civil_judgment", "civil_settlement", "indicted", "charged", "arrested", "complaint", "exclusion", "payment_suspension", "license_action", "other"]
    programs: List[str] = Field(description="Subset of: Medicare, Medicaid, CHIP, TRICARE, private insurance")
    scheme: str = Field(description="One factual sentence describing what the release says was done, without adjectives")
    dollars_alleged: Optional[float] = Field(description="Dollar amount of claims or loss alleged, as a number, or null")
    dollars_ordered: Optional[float] = Field(description="Restitution, forfeiture, settlement or judgment amount as a number, or null")
    action_date: Optional[str] = Field(description="Date of the action in YYYY-MM-DD if the text states it; otherwise null")
    parties: List[Party]
    confidence: Literal["high", "medium", "low"]

ADJUDICATED = {"sentenced", "convicted", "pleaded_guilty", "civil_judgment"}
ALLEGED = {"indicted", "charged", "arrested", "complaint"}
def tier_of(action_type: str) -> str:
    if action_type in ADJUDICATED: return "adjudicated"
    if action_type in ALLEGED: return "alleged"
    return "administrative"      # settlement without admission, exclusion notice, suspension, license action, other

SYS = ("You extract structured facts from a public enforcement release about health care. Report only what the text states. Names exactly as written. "
       "A party is a provider only if the text says it billed or was enrolled with a payer. Never infer an NPI; only copy one that is printed. "
       "Use the release's own words for the scheme and keep it to one sentence. Do not use em dashes.")

# ------------------------------------------------------------------ deterministic fallback (no key, or a failed item)
TITLE_RULES = [("sentenced", r"\bsentenced\b"), ("pleaded_guilty", r"\bplead(?:s|ed)? guilty\b|\bguilty plea\b"), ("convicted", r"\bconvicted\b|\bfound guilty\b|\bjury (?:finds|found)\b"),
               ("civil_judgment", r"\bjudgment\b"), ("civil_settlement", r"\bagrees? to pay\b|\bsettle(?:s|d|ment)\b|\bto pay \$"), ("indicted", r"\bindict(?:ed|ment)\b"),
               ("arrested", r"\barrest(?:ed)?\b"), ("charged", r"\bcharged\b|\bcharges\b"), ("complaint", r"\bcomplaint\b"), ("exclusion", r"\bexclu(?:ded|sion)\b"),
               ("payment_suspension", r"\bsuspen(?:ded|sion)\b"), ("license_action", r"\blicense\b")]
HEALTH = re.compile(r"medicare|medicaid|health ?care|hospice|home health|pharmac|clinic|physician|durable medical|laborator|nursing|telehealth|behavioral|tricare", re.I)
ORG = re.compile(r"\b((?:[A-Z][A-Za-z&'.-]+\s){0,5}(?:Hospice|Home Health|Health ?Care|Healthcare|Medical|Pharmacy|Laboratory|Labs?|Clinic|Wellness|Therapy|Services|Supply|Supplies)(?:\s(?:[A-Z][A-Za-z&'.-]+)){0,3}(?:,?\s(?:LLC|Inc\.?|Corp\.?|P\.?C\.?|PLLC|Ltd\.?))?)\b")
def deterministic(title, body):
    text = f"{title}\n{body or ''}"
    act = next((k for k, pat in TITLE_RULES if re.search(pat, title, re.I)), None) or next((k for k, pat in TITLE_RULES if re.search(pat, text[:1500], re.I)), "other")
    orgs = []
    for m in ORG.finditer(text[:6000]):
        nm = re.sub(r"\s+", " ", m.group(1)).strip(" ,.")
        if 6 <= len(nm) <= 80 and nm not in orgs: orgs.append(nm)
    dollars = [float(x.replace(",", "")) * (1e6 if u.lower().startswith("m") else 1e9 if u.lower().startswith("b") else 1) for x, u in re.findall(r"\$([\d,]+(?:\.\d+)?)\s*(million|billion|m\b|b\b)?", text[:4000], re.I)]
    return dict(relevant=bool(HEALTH.search(text[:3000])), action_type=act, programs=[p for p in ("Medicare", "Medicaid", "CHIP", "TRICARE") if re.search(p, text, re.I)],
                scheme=title, dollars_alleged=(max(dollars) if dollars else None), dollars_ordered=None, action_date=None,
                parties=[dict(name=o, kind="organization", role="provider", provider_type=None, city=None, state=None, is_provider=True, npi=None) for o in orgs[:6]],
                confidence="low")

# ------------------------------------------------------------------ work list
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
con.execute("""CREATE TABLE IF NOT EXISTS enforcement_actions (
  event_key VARCHAR, source_id VARCHAR, source VARCHAR, url VARCHAR, source_url VARCHAR, title VARCHAR, published DATE, category VARCHAR, district VARCHAR, state VARCHAR,
  relevant BOOLEAN, action_type VARCHAR, tier VARCHAR, programs VARCHAR, scheme VARCHAR, dollars_alleged DOUBLE, dollars_ordered DOUBLE, action_date DATE,
  n_parties INTEGER, confidence VARCHAR, model VARCHAR, batch_id VARCHAR, extracted_at TIMESTAMP)""")
con.execute("""CREATE TABLE IF NOT EXISTS enforcement_parties (
  event_key VARCHAR, source_id VARCHAR, party_ix INTEGER, name VARCHAR, kind VARCHAR, role VARCHAR, provider_type VARCHAR, city VARCHAR, state VARCHAR, is_provider BOOLEAN, npi VARCHAR)""")
con.execute("CREATE TABLE IF NOT EXISTS enforcement_batches (batch_id VARCHAR, submitted_at TIMESTAMP, n INTEGER, status VARCHAR)")
# one event per originating release: DOJ record preferred as the text source when OIG mirrors it
work = con.execute(f"""
WITH r AS (SELECT *, lower(rtrim(COALESCE(source_url, url), '/')) AS event_key FROM enforcement_raw),
     pick AS (SELECT * FROM r QUALIFY row_number() OVER (PARTITION BY event_key ORDER BY CASE source WHEN 'DOJ' THEN 0 ELSE 1 END, length(COALESCE(body,'')) DESC) = 1)
SELECT p.* FROM pick p WHERE p.event_key NOT IN (SELECT event_key FROM enforcement_actions) AND length(COALESCE(p.body, '')) >= 80
ORDER BY p.published DESC {f'LIMIT {a.limit}' if a.limit else ''}""").df()
print(f"records to extract: {len(work):,} (of {con.execute('SELECT COUNT(*) FROM enforcement_raw').fetchone()[0]:,} raw)")
if work.empty: con.close(); sys.exit(0)

def user_text(r):
    return json.dumps(dict(source=r.source, published=str(r.published), district=r.district, category=r.category, title=r.title, text=(r.body or "")[:12000]), ensure_ascii=False)

results, batch_id, model_used = {}, None, llm.MODEL
if llm.ready():
    items = [(r.source_id, user_text(r)) for r in work.itertuples(index=False)]
    if a.sync:
        def one(it):
            cid, txt = it
            try: return cid, llm.parse(Extraction, SYS, txt, effort="medium", max_tokens=3000).model_dump()
            except Exception as e: return cid, {"error": str(e)[:200]}
        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, (cid, v) in enumerate(ex.map(one, items), 1):
                results[cid] = v
                if i % 50 == 0: print(f"  {i:,}/{len(items):,}", flush=True)
    else:
        reqs = llm.batch_requests(items, Extraction, SYS, effort="medium", max_tokens=3000)
        con.execute("INSERT INTO enforcement_batches VALUES (?, now(), ?, 'submitted')", ["pending", len(reqs)])
        print(f"submitting batch of {len(reqs):,} requests", flush=True)
        results, batch_id = llm.batch_run(reqs, poll_seconds=30)
        con.execute("UPDATE enforcement_batches SET batch_id = ?, status = 'ended' WHERE batch_id = 'pending'", [batch_id])
else:
    print("no ANTHROPIC_API_KEY: deterministic title rules only", flush=True); model_used = "deterministic"

rows, parties, n_fallback = [], [], 0
now = pd.Timestamp.now()
for r in work.itertuples(index=False):
    v = results.get(r.source_id) if results else None
    model = model_used
    if not v or "error" in v:
        v = deterministic(r.title, r.body); model = "deterministic"; n_fallback += 1
    act = v.get("action_type") or "other"
    ps = v.get("parties") or []
    rows.append(dict(event_key=r.event_key, source_id=r.source_id, source=r.source, url=r.url, source_url=r.source_url, title=r.title, published=r.published, category=r.category,
                     district=r.district, state=r.state, relevant=bool(v.get("relevant")), action_type=act, tier=tier_of(act), programs=",".join(v.get("programs") or []),
                     scheme=(v.get("scheme") or "")[:600], dollars_alleged=v.get("dollars_alleged"), dollars_ordered=v.get("dollars_ordered"),
                     action_date=(pd.to_datetime(v.get("action_date"), errors="coerce").date() if v.get("action_date") else None),
                     n_parties=len(ps), confidence=v.get("confidence") or "low", model=model, batch_id=batch_id, extracted_at=now))
    for i, p in enumerate(ps):
        npi = re.sub(r"\D", "", str(p.get("npi") or "")); npi = npi if len(npi) == 10 else None
        st = (p.get("state") or "").strip().upper()[:2] or None
        parties.append(dict(event_key=r.event_key, source_id=r.source_id, party_ix=i, name=(p.get("name") or "").strip()[:200], kind=p.get("kind") or "organization", role=(p.get("role") or "")[:80],
                            provider_type=(p.get("provider_type") or None), city=(p.get("city") or None), state=st, is_provider=bool(p.get("is_provider")), npi=npi))
A = pd.DataFrame(rows); P = pd.DataFrame(parties) if parties else pd.DataFrame(columns=["event_key","source_id","party_ix","name","kind","role","provider_type","city","state","is_provider","npi"])
con.execute("INSERT INTO enforcement_actions SELECT * FROM A"); con.execute("INSERT INTO enforcement_parties SELECT * FROM P")
n_rel = int(A.relevant.sum()); n_adj = int((A.tier == "adjudicated").sum()); n_all = int((A.tier == "alleged").sum())
print(f"extracted {len(A):,} events ({n_fallback} by deterministic fallback): {n_rel:,} relevant, {n_adj:,} adjudicated, {n_all:,} alleged, {len(P):,} parties, {int(P.npi.notna().sum()) if len(P) else 0} with a printed NPI")
print(A[A.relevant].groupby(["tier", "action_type"]).size().to_string() if n_rel else "no relevant events")
con.execute("CHECKPOINT"); con.close()
