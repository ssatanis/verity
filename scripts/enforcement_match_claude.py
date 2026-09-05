#!/usr/bin/env python3
"""Resolve parties named in enforcement releases to NPIs. Same discipline as scripts/sam_match_claude.py: deterministic blocking
first (organizations on the normalized name, individuals on exact last and first name, both within the party's state or the
release's district state), at most five NPPES candidates per party, then Claude judges each candidate pair with the release
context (role, provider type, city, scheme) against the NPPES record (name, taxonomy, practice city, enumeration and
deactivation dates). Only same_entity with high confidence becomes an event; Detector 3 and Detector 1 read nothing else.

An enforcement release never carries an NPI, so every match here is a name match by construction and is reported as such
(id_match = name_match_model_high). Table: enforcement_npi_matches. Idempotent on (source_id, party_ix).
Usage: .venv/bin/python scripts/enforcement_match_claude.py [--limit N] [--sync]
"""
import argparse, concurrent.futures as cf, json, os, re, sys
import duckdb, pandas as pd
from pydantic import BaseModel, Field
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api")
import llm
ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--sync", action="store_true"); ap.add_argument("--workers", type=int, default=6); a = ap.parse_args()

class Judgement(BaseModel):
    same_entity: bool = Field(description="True only if the party named in the release and the NPPES record are the same person or organization")
    confidence: str = Field(description="high, medium or low")
    reason: str = Field(description="One sentence citing the fields that agree or conflict")
SYS = ("You decide whether a party named in a public health care enforcement release and an NPPES provider record are the same person or organization. "
       "Agreement on a distinctive organization name plus state is strong; add city or provider type for high confidence. For individuals, a common name needs "
       "city or a taxonomy consistent with the role described; a name-only match in a large state is low confidence. An NPPES record enumerated years after the "
       "conduct, or a taxonomy unrelated to the provider type in the release, argues against. Do not use em dashes.")

def reconnect(wait_minutes=20):
    """Open the writer; if a detector holds the single-writer lock, wait for it rather than fail (or lose a finished batch)."""
    import time
    for _ in range(wait_minutes * 6):
        try: return duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
        except duckdb.IOException as e:
            if "lock" not in str(e).lower(): raise
            time.sleep(10)
    raise RuntimeError("warehouse lock not released in time")
con = reconnect()
con.execute("ALTER TABLE enforcement_actions ADD COLUMN IF NOT EXISTS event_state VARCHAR")
con.execute("CREATE OR REPLACE MACRO okey(n) AS trim(regexp_replace(regexp_replace(upper(COALESCE(n,'')), '\\b(LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|PC|LP|LLP|PLLC|THE|DBA)\\b', ' ', 'g'), '[^A-Z0-9 ]| +', ' ', 'g'))")
con.execute("""CREATE TABLE IF NOT EXISTS enforcement_npi_matches (
  source_id VARCHAR, event_key VARCHAR, party_ix INTEGER, npi VARCHAR, same_entity BOOLEAN, confidence VARCHAR, reason VARCHAR, batch_id VARCHAR,
  name VARCHAR, kind VARCHAR, role VARCHAR, tier VARCHAR, action_type VARCHAR, event_dt DATE, state VARCHAR, source VARCHAR, url VARCHAR, title VARCHAR, is_subject BOOLEAN)""")
# a party is the subject of the action unless the model's role says otherwise: an employer whose employee was charged, a relator, an insurer or a
# victim is named in the release but is not the provider the action concerns. Deterministic from the role text; applied by every reader.
NON_SUBJECT = r"\b(employer|relator|whistleblower|insurer|managed care|victim|payer|payor|witness|patient|predecessor|informant)\b"
con.execute("ALTER TABLE enforcement_npi_matches ADD COLUMN IF NOT EXISTS is_subject BOOLEAN")
con.execute(f"UPDATE enforcement_npi_matches SET is_subject = NOT regexp_matches(lower(COALESCE(role, '')), '{NON_SUBJECT}') WHERE is_subject IS NULL")

# parties of relevant events not yet judged; individuals split into first and last for blocking (suffixes dropped, middle ignored)
cands = con.execute(f"""
WITH p AS (
  -- the party's own npi column is the one printed in the release (almost always null); exclude it so the NPPES npi from the join is the only 'npi'
  SELECT p.* EXCLUDE (npi), p.npi AS printed_npi, a.tier, a.action_type, COALESCE(a.action_date, a.published) AS event_dt,
         COALESCE(p.state, a.event_state, a.state) AS block_state,   -- the party's own state, else the state the release describes, else the DOJ district state
         a.source, a.url, a.title, a.scheme, a.published,
         regexp_replace(upper(p.name), '\\b(JR|SR|II|III|IV|MD|DO|RN|NP|PA|DDS|PHD|ESQ)\\b\\.?', '', 'g') AS nm
  FROM enforcement_parties p JOIN enforcement_actions a USING (source_id)
  WHERE a.relevant AND length(p.name) >= 4
    -- an anti-join, not a two-column NOT IN: DuckDB does not treat (a, b) NOT IN (SELECT x, y) as a row comparison, and the wrong form skipped every
    -- party on an event that already had some other party judged
    AND NOT EXISTS (SELECT 1 FROM enforcement_npi_matches m WHERE m.source_id = p.source_id AND m.party_ix = p.party_ix)),
ind AS (
  SELECT p.*, n.npi, COALESCE(n.org_name, trim(n.first_name || ' ' || n.last_name)) AS nppes_name, n.entity_type, n.taxonomy, n.addr1 AS nppes_addr, n.city AS nppes_city,
         n.state AS nppes_state, n.zip5 AS nppes_zip, n.enum_date, n.deact_date
  FROM p JOIN nppes n ON n.entity_type = '1'
    AND upper(n.last_name) = trim(regexp_extract(trim(p.nm), '(\\S+)$', 1))
    AND upper(n.first_name) = trim(regexp_extract(trim(p.nm), '^(\\S+)', 1))
    AND (p.block_state IS NULL OR n.state = p.block_state)
  WHERE p.kind = 'individual' AND length(trim(p.nm)) - length(replace(trim(p.nm), ' ', '')) >= 1),
org AS (
  SELECT p.*, n.npi, n.org_name AS nppes_name, n.entity_type, n.taxonomy, n.addr1 AS nppes_addr, n.city AS nppes_city, n.state AS nppes_state, n.zip5 AS nppes_zip, n.enum_date, n.deact_date
  FROM p JOIN nppes n ON n.entity_type = '2' AND (p.block_state IS NULL OR n.state = p.block_state)
    AND (okey(n.org_name) = okey(p.name)
         -- containment within the state, for a release that shortens the name ("Smart Therapy" for SMART THERAPY CENTER LLC) or a registry
         -- entry with the spaces dropped (FALADCARELLC); eight or more characters so short names do not explode, and the model still judges each pair
         OR (p.block_state IS NOT NULL AND length(replace(okey(p.name), ' ', '')) >= 8
             AND (replace(okey(n.org_name), ' ', '') LIKE '%' || replace(okey(p.name), ' ', '') || '%'
                  OR (length(replace(okey(n.org_name), ' ', '')) >= 8 AND replace(okey(p.name), ' ', '') LIKE '%' || replace(okey(n.org_name), ' ', '') || '%'))))   -- both directions need eight characters: a three-letter registry name would sit inside too many release names
  WHERE p.kind = 'organization' AND length(okey(p.name)) >= 5),
u AS (SELECT * FROM ind UNION ALL SELECT * FROM org),
counted AS (SELECT *, COUNT(*) OVER (PARTITION BY source_id, party_ix) AS n_cand FROM u)
SELECT * FROM counted WHERE n_cand <= 5 ORDER BY published DESC, source_id, party_ix {f'LIMIT {a.limit}' if a.limit else ''}""").df()
n_parties = con.execute("SELECT COUNT(*) FROM enforcement_parties p JOIN enforcement_actions a USING (source_id) WHERE a.relevant").fetchone()[0]
print(f"candidate pairs: {len(cands):,} for {cands[['source_id','party_ix']].drop_duplicates().shape[0] if len(cands) else 0:,} parties (of {n_parties:,} parties on relevant events)")
if cands.empty: con.close(); sys.exit(0)
con.close()   # release the single-writer lock during the model wait

items = []
for r in cands.itertuples(index=False):
    party = dict(name=r.name, kind=r.kind, role=r.role, provider_type=r.provider_type, city=r.city, state=r.state or r.block_state, release_title=r.title,
                 release_date=str(r.published), what_the_release_says=r.scheme, action=r.action_type)
    rec = dict(npi=r.npi, name=r.nppes_name, entity_type=("individual" if r.entity_type == "1" else "organization"), taxonomy=r.taxonomy, practice_address=r.nppes_addr,
               city=r.nppes_city, state=r.nppes_state, zip=r.nppes_zip, enumerated=str(r.enum_date), deactivated=(str(r.deact_date) if pd.notna(r.deact_date) else None))
    items.append((f"{r.source_id}__{r.party_ix}__{r.npi}", json.dumps({"party_in_release": party, "nppes_record": rec}, default=str, ensure_ascii=False)))

results, batch_id = {}, None
if llm.ready():
    if a.sync:
        def one(it):
            cid, txt = it
            try: return cid, llm.parse(Judgement, SYS, txt, effort="low", max_tokens=500).model_dump()
            except Exception as e: return cid, {"error": str(e)[:200]}
        with cf.ThreadPoolExecutor(max_workers=a.workers) as ex:
            for cid, v in ex.map(one, items): results[cid] = v
    else:
        results, batch_id = llm.batch_run(llm.batch_requests(items, Judgement, SYS, effort="low", max_tokens=500), poll_seconds=30)
else:
    print("no ANTHROPIC_API_KEY: nothing is matched (no deterministic fallback for identity, by design)")

rows = []
for r in cands.itertuples(index=False):
    v = results.get(f"{r.source_id}__{r.party_ix}__{r.npi}", {"error": "no result"})
    rows.append(dict(source_id=r.source_id, event_key=r.event_key, party_ix=int(r.party_ix), npi=r.npi, same_entity=bool(v.get("same_entity")) if "error" not in v else False,
                     confidence=(v.get("confidence") or "low") if "error" not in v else "error", reason=(v.get("reason") or v.get("error") or "")[:300], batch_id=batch_id,
                     name=r.name, kind=r.kind, role=r.role, tier=r.tier, action_type=r.action_type, event_dt=r.event_dt, state=r.state or r.block_state, source=r.source, url=r.url, title=r.title,
                     is_subject=not re.search(NON_SUBJECT, (r.role or "").lower())))
M = pd.DataFrame(rows)
con = reconnect()   # reopen only for the short write
con.execute("INSERT INTO enforcement_npi_matches SELECT * FROM M")
yes = M[(M.same_entity) & (M.confidence == "high")]
print(f"judged {len(M):,} pairs: same={int(M.same_entity.sum())}, high-confidence matches={len(yes)} ({yes.npi.nunique()} NPIs; {int((yes.tier=='adjudicated').sum())} adjudicated, {int((yes.tier=='alleged').sum())} alleged; {int((~yes.is_subject).sum())} set aside as employer, relator or other non-subject)")
for r in yes.head(12).itertuples(index=False): print(f"  {r.npi} {r.name[:40]:<40} {r.tier:<12} {r.action_type:<16} {str(r.event_dt)} | {r.reason[:90]}")
con.execute("CHECKPOINT"); con.close()
