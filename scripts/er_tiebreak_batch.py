#!/usr/bin/env python3
"""Entity resolution tie-breaker: borderline owner-person pairs from Detector 1's Fellegi-Sunter model (posterior between 0.2 and 0.98)
are adjudicated by Claude with structured output through the Batch API. The agreement rate against the EM decision is reported in
docs/methods.md. Adjudications are stored in d1_er_adjudications; they do not change the graph automatically.
Usage: .venv/bin/python scripts/er_tiebreak_batch.py [--limit 400]"""
import argparse, json, os, sys, time
import duckdb
import pandas as pd, pandas as pd
from pydantic import BaseModel, Field
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "api"); sys.path.insert(0, "detectors")
import llm
from _methods import write_section, md_table
ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=400); a = ap.parse_args()
class Verdict(BaseModel):
    same_person: bool = Field(description="True if the two owner records almost certainly refer to the same individual")
    confidence: str = Field(description="high, medium or low")
    reason: str = Field(description="One sentence naming the agreeing and conflicting fields")
SYS = "You compare two owner records from CMS provider ownership files and decide whether they are the same individual. Fields: last name, first name, middle initial, ZIP5, city, state, street number (the address is the enrollment's address when the owner file has none). Same last name with a different first name is usually a relative, not the same person. Do not use em dashes."
con = duckdb.connect("data/verity.duckdb")
# two review sets: every pair the applied rule merged (posterior at or above 0.95 plus a locational agreement and real name agreement), and the
# highest-posterior pairs the rule rejected. The model's verdict is compared with the applied decision, not with the raw posterior.
half = max(50, a.limit // 2)
c_yes = con.execute(f"""SELECT * FROM d1_er_candidates WHERE matched ORDER BY posterior LIMIT {half}""").df()
c_no = con.execute(f"""SELECT * FROM d1_er_candidates WHERE NOT matched AND posterior >= 0.5 ORDER BY posterior DESC LIMIT {half}""").df()
c = pd.concat([c_yes, c_no], ignore_index=True)
print(f"borderline pairs sampled: {len(c):,}")
items = [(f"{int(r.i)}__{int(r.j)}", json.dumps({"record_a": dict(last=r.p_last_i, first=r.p_first_i, middle=r.p_mi_i, zip=r.zip5_i, city=r.city_i, state=r.state_i, street_number=r.street_i),
                                                 "record_b": dict(last=r.p_last_j, first=r.p_first_j, middle=r.p_mi_j, zip=r.zip5_j, city=r.city_j, state=r.state_j, street_number=r.street_j)})) for r in c.itertuples(index=False)]
results, batch_id = llm.batch_run(llm.batch_requests(items, Verdict, SYS, effort="low", max_tokens=400), poll_seconds=30)
c["model_same"] = [results.get(f"{int(r.i)}__{int(r.j)}", {}).get("same_person") for r in c.itertuples(index=False)]
c["model_conf"] = [results.get(f"{int(r.i)}__{int(r.j)}", {}).get("confidence") for r in c.itertuples(index=False)]
c["model_reason"] = [results.get(f"{int(r.i)}__{int(r.j)}", {}).get("reason") or results.get(f"{int(r.i)}__{int(r.j)}", {}).get("error") for r in c.itertuples(index=False)]
c["em_same"] = c.matched.astype(bool); c["batch_id"] = batch_id
con.execute("CREATE OR REPLACE TABLE d1_er_adjudications AS SELECT * FROM c")
valid = c[c.model_same.notna()]
agree = float((valid.model_same == valid.em_same).mean()) if len(valid) else float("nan")
hi = valid[valid.model_conf == "high"]; agree_hi = float((hi.model_same == hi.em_same).mean()) if len(hi) else float("nan")
band = valid.groupby("em_same", observed=True).agg(n=("model_same", "size"), model_same_rate=("model_same", "mean"), em_same_rate=("em_same", "mean")).reset_index().rename(columns={"em_same": "rule merged"})
body = f"""
**Method.** {len(valid):,} owner-person pairs were adjudicated: every pair the applied merge rule accepted (posterior at or above 0.95 plus a locational agreement and real name agreement) and the highest-posterior pairs it rejected. They were judged by Claude (claude-opus-5, structured output, Message Batches API, batch {batch_id}) from the same six fields the EM model sees. The model's verdict is compared with the applied decision, not the raw posterior: the EM posterior alone is miscalibrated for pairs that agree only on city, state and a name initial, which is exactly why the rule requires a locational agreement.

Agreement with the applied merge decision: {agree:.1%} over all adjudicated pairs, {agree_hi:.1%} over the {len(hi):,} pairs the model rated high confidence.

{md_table([("merged by the rule" if r['rule merged'] else "rejected by the rule", int(r['n']), f"{r['model_same_rate']:.2f}", f"{r['em_same_rate']:.2f}") for r in band.to_dict('records')], ["pairs","pairs","model says same","EM says same"])}

Adjudications are stored in `d1_er_adjudications` for human review and do not change the graph automatically; pairs where the model says same with high confidence and the EM said different are the review queue for the next matcher iteration.
"""
write_section("Entity resolution adjudication", body); con.execute("CHECKPOINT"); con.close(); print(f"agreement {agree:.3f} (high conf {agree_hi:.3f}); methods updated")
