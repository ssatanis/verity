#!/usr/bin/env python3
"""Recover NPIs for exclusion entries that carry none. LEIE and SAM (HHS) rows without an NPI are matched to NPPES candidates by
deterministic blocking (same state; individuals on exact last name and first name, businesses on the normalised organisation name),
then Claude judges each candidate pair (structured output, Batch API) with a confidence and a reason. Only 'yes' with high confidence
becomes a name-matched event, and Detector 3 reports those separately as tier B. Writes sam_npi_matches in DuckDB and docs/name_matching.md.
Usage: .venv/bin/python scripts/sam_match_claude.py [--limit 600]"""
import argparse, json, os, re, sys, time
import duckdb
from pydantic import BaseModel, Field
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api")
import llm
ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=600); a = ap.parse_args()
class Judgement(BaseModel):
    same_entity: bool = Field(description="True only if the exclusion entry and the NPPES record are the same person or organisation")
    confidence: str = Field(description="high, medium or low")
    reason: str = Field(description="One sentence citing the fields that agree or conflict")
SYS = "You decide whether a health care exclusion list entry (name, address) and an NPPES provider record (name, practice address, taxonomy) refer to the same person or organisation. Common names in large cities need address agreement; a name-only match is low confidence. Do not use em dashes."
con = duckdb.connect("data/verity.duckdb")
con.execute("CREATE OR REPLACE MACRO okey(n) AS trim(regexp_replace(regexp_replace(upper(COALESCE(n,'')), '\\b(LLC|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|PC|LP|LLP|PLLC|THE)\\b', ' ', 'g'), '[^A-Z0-9 ]| +', ' ', 'g'))")
cands = con.execute(f"""
WITH src AS (
  SELECT 'OIG_LEIE' AS source, 'leie:' || ROW_NUMBER() OVER () AS source_id, lastname, firstname, busname, address, city, state, zip, excltype AS reason, excl_dt AS event_dt
  FROM leie WHERE npi IS NULL AND excl_dt >= DATE '2015-01-01'),
ind AS (
  SELECT s.*, n.npi, COALESCE(n.org_name, n.first_name || ' ' || n.last_name) AS nppes_name, n.addr1 AS nppes_addr, n.city AS nppes_city, n.state AS nppes_state, n.zip5 AS nppes_zip, n.taxonomy
  FROM src s JOIN nppes n ON n.entity_type = '1' AND upper(n.last_name) = upper(s.lastname) AND upper(n.first_name) = upper(s.firstname) AND n.state = s.state
  WHERE COALESCE(s.busname, '') = '' AND s.lastname <> '' AND s.firstname <> ''),
org AS (
  SELECT s.*, n.npi, n.org_name AS nppes_name, n.addr1, n.city, n.state, n.zip5, n.taxonomy
  FROM src s JOIN nppes n ON n.entity_type = '2' AND okey(n.org_name) = okey(s.busname) AND n.state = s.state
  WHERE COALESCE(s.busname, '') <> ''),
u AS (SELECT * FROM ind UNION ALL SELECT * FROM org),
counted AS (SELECT *, COUNT(*) OVER (PARTITION BY source_id) AS n_cand FROM u)
SELECT * FROM counted WHERE n_cand <= 3 ORDER BY event_dt DESC LIMIT {a.limit}""").df()
print(f"candidate pairs: {len(cands):,} for {cands.source_id.nunique():,} exclusion entries")
items = []
for r in cands.itertuples(index=False):
    ex = dict(name=r.busname or f"{r.firstname} {r.lastname}", address=r.address, city=r.city, state=r.state, zip=r.zip, exclusion_type=r.reason, exclusion_date=str(r.event_dt))
    np_ = dict(npi=r.npi, name=r.nppes_name, practice_address=r.nppes_addr, city=r.nppes_city, state=r.nppes_state, zip=r.nppes_zip, taxonomy=r.taxonomy)
    items.append((f"{r.source_id}__{r.npi}", json.dumps({"exclusion_entry": ex, "nppes_record": np_}, default=str)))
results, batch_id = llm.batch_run(llm.batch_requests(items, Judgement, SYS, effort="low", max_tokens=600), poll_seconds=30)
rows = []
for cid, v in results.items():
    sid, npi = cid.rsplit("__", 1); rows.append(dict(source_id=sid, npi=npi, same_entity=v.get("same_entity"), confidence=v.get("confidence"), reason=v.get("reason") or v.get("error"), batch_id=batch_id))
import pandas as pd
df = pd.DataFrame(rows).merge(cands[["source_id", "npi", "source", "lastname", "firstname", "busname", "state", "reason", "event_dt"]].rename(columns={"reason": "exclusion_type"}), on=["source_id", "npi"], how="left")
con.execute("CREATE OR REPLACE TABLE sam_npi_matches AS SELECT * FROM df")
yes = df[(df.same_entity == True) & (df.confidence == "high")]
print("matches:", df.same_entity.value_counts().to_dict(), "| high-confidence yes:", len(yes))
lines = [f"# Name matching of exclusion entries without an NPI (batch {batch_id}, {time.strftime('%Y-%m-%d')})", "",
         f"{cands.source_id.nunique():,} LEIE entries (excluded 2015 or later, no NPI on the list) had one to three NPPES candidates by exact name and state. Claude judged {len(df):,} candidate pairs: {int((df.same_entity == True).sum())} same, {int((df.same_entity == False).sum())} different; {len(yes)} high-confidence matches recovered an NPI. High-confidence matches feed Detector 3 as tier B (name-matched) events and never as tier A.", "",
         "| exclusion entry | NPI | NPPES | verdict | confidence | reason |", "|---|---|---|---|---|---|"]
for r in df.sort_values(["same_entity", "confidence"], ascending=[False, True]).head(40).itertuples(index=False):
    lines.append(f"| {(r.busname or (str(r.firstname) + ' ' + str(r.lastname))).strip()} ({r.state}) | {r.npi} | | {r.same_entity} | {r.confidence} | {str(r.reason).replace('|', '/')} |")
open("docs/name_matching.md", "w").write("\n".join(lines) + "\n"); con.execute("CHECKPOINT"); con.close(); print("wrote docs/name_matching.md")
