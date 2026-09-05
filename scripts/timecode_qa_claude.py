#!/usr/bin/env python3
"""QA of ingest/02_timecodes.csv: for each code, Claude checks minutes per unit, unit basis, group divisor and the personal-service
attribute against the CPT/HCPCS descriptor it knows, and flags disagreements for a human. Runs through the Message Batches API.
Writes docs/timecode_qa.md and data/qa/timecode_qa.json. Nothing in the pipeline changes automatically; a human edits the CSV."""
import csv, json, os, sys, time
from typing import Optional
from pydantic import BaseModel, Field
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api")
import llm
class Check(BaseModel):
    agrees: bool = Field(description="True if minutes_per_unit, unit_basis, group_divisor and personal_service are all consistent with the code's official descriptor and typical use")
    descriptor: str = Field(description="The official CPT or HCPCS short descriptor as you know it")
    expected_minutes_per_unit: Optional[float] = Field(description="Minutes one billed unit represents per the descriptor; null for per-diem, per-session-untimed or per-encounter codes")
    expected_unit_basis: str = Field(description="one of per_15min, per_30min, per_hour, per_session, per_diem, per_encounter, per_month, per_half_day")
    expected_group: bool = Field(description="True if the code is a group service")
    expected_personal_service: bool = Field(description="True if the rendering clinician must personally deliver the service (E/M, psychotherapy, evaluations); False if technicians, aides or agency staff deliver it under a supervising or agency NPI")
    disagreement: Optional[str] = Field(description="What is wrong and the correct value, or null")
    confidence: str = Field(description="high, medium or low")
SYS = "You are a coding QA reviewer for CPT and HCPCS time-based codes used in Medicaid. Compare the table row to the official descriptor. Be precise about units; when a code is untimed, say so. Do not use em dashes."
rows = list(csv.DictReader(open("ingest/02_timecodes.csv")))
items = [(r["hcpcs"], json.dumps({k: r[k] for k in ("hcpcs", "description", "minutes_per_unit", "unit_basis", "group_divisor", "family", "personal_service", "notes")})) for r in rows]
print(f"submitting {len(items)} codes to the Batch API")
results, batch_id = llm.batch_run(llm.batch_requests(items, Check, SYS, effort="low", max_tokens=1200), poll_seconds=30)
os.makedirs("data/qa", exist_ok=True); json.dump(results, open("data/qa/timecode_qa.json", "w"), indent=1)
dis = [(k, v) for k, v in results.items() if isinstance(v, dict) and not v.get("agrees", True) and "error" not in v]
errs = [k for k, v in results.items() if "error" in v]
lines = [f"# Time-code table QA (Claude batch {batch_id}, {time.strftime('%Y-%m-%d')})", "",
         f"{len(results)} codes reviewed, {len(dis)} disagreements flagged for a human, {len(errs)} errors. A disagreement is a prompt to check the descriptor, not an automatic edit.", "",
         "| code | table minutes | table basis | personal | model expected minutes | model basis | model personal | disagreement | confidence |", "|---|---|---|---|---|---|---|---|---|"]
byc = {r["hcpcs"]: r for r in rows}
for k, v in sorted(dis):
    r = byc[k]; lines.append(f"| {k} | {r['minutes_per_unit']} | {r['unit_basis']} | {r['personal_service']} | {v.get('expected_minutes_per_unit')} | {v.get('expected_unit_basis')} | {v.get('expected_personal_service')} | {(v.get('disagreement') or '').replace('|', '/')} | {v.get('confidence')} |")
open("docs/timecode_qa.md", "w").write("\n".join(lines) + "\n"); print(f"done: {len(dis)} disagreements, {len(errs)} errors; docs/timecode_qa.md")
