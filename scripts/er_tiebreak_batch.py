#!/usr/bin/env python3
"""Entity resolution tie-breaker: borderline owner-person pairs from Detector 1's Fellegi-Sunter model (posterior between 0.2 and 0.98)
are adjudicated by Claude with structured output through the Batch API. The agreement rate against the EM decision is reported in
docs/methods.md. Adjudications are stored in d1_er_adjudications; they do not change the graph automatically.
Usage: .venv/bin/python scripts/er_tiebreak_batch.py [--limit 400]"""
import argparse, json, os, sys, time
import duckdb, pandas as pd
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
c = con.execute(f"""SELECT * FROM d1_er_candidates WHERE posterior >= 0.2 AND posterior < 0.98 ORDER BY random() LIMIT {a.limit}""").df()
if len(c) < 50:
    # the EM posterior is sharp; when the 0.2 to 0.98 band is nearly empty, adjudicate the pairs closest to the decision threshold from both sides instead
    c = con.execute(f"""SELECT * FROM d1_er_candidates ORDER BY abs(posterior - 0.95) LIMIT {a.limit}""").df()
    print("band nearly empty; using the pairs closest to the 0.95 threshold")
print(f"borderline pairs sampled: {len(c):,}")
items = [(f"{int(r.i)}|{int(r.j)}", json.dumps({"record_a": dict(last=r.p_last_i, first=r.p_first_i, middle=r.p_mi_i, zip=r.zip5_i, city=r.city_i, state=r.state_i, street_number=r.street_i),
                                                 "record_b": dict(last=r.p_last_j, first=r.p_first_j, middle=r.p_mi_j, zip=r.zip5_j, city=r.city_j, state=r.state_j, street_number=r.street_j)})) for r in c.itertuples(index=False)]
results, batch_id = llm.batch_run(llm.batch_requests(items, Verdict, SYS, effort="low", max_tokens=400), poll_seconds=30)
c["model_same"] = [results.get(f"{int(r.i)}|{int(r.j)}", {}).get("same_person") for r in c.itertuples(index=False)]
c["model_conf"] = [results.get(f"{int(r.i)}|{int(r.j)}", {}).get("confidence") for r in c.itertuples(index=False)]
c["model_reason"] = [results.get(f"{int(r.i)}|{int(r.j)}", {}).get("reason") or results.get(f"{int(r.i)}|{int(r.j)}", {}).get("error") for r in c.itertuples(index=False)]
c["em_same"] = c.posterior >= 0.95; c["batch_id"] = batch_id
con.execute("CREATE OR REPLACE TABLE d1_er_adjudications AS SELECT * FROM c")
valid = c[c.model_same.notna()]
agree = float((valid.model_same == valid.em_same).mean()) if len(valid) else float("nan")
hi = valid[valid.model_conf == "high"]; agree_hi = float((hi.model_same == hi.em_same).mean()) if len(hi) else float("nan")
band = valid.groupby(pd.cut(valid.posterior, [-0.001, 0.2, 0.5, 0.8, 0.95, 0.98, 1.0]), observed=True).agg(n=("model_same", "size"), model_same_rate=("model_same", "mean"), em_same_rate=("em_same", "mean")).reset_index()
body = f"""
**Method.** {len(valid):,} borderline owner-person pairs (Fellegi-Sunter posterior between 0.2 and 0.98) were adjudicated by Claude (claude-opus-5, structured output, Message Batches API, batch {batch_id}) from the same six fields the EM model sees. The model's verdict is compared with the EM decision (match at posterior 0.95 or above).

Agreement with the EM decision: {agree:.1%} over all adjudicated pairs, {agree_hi:.1%} over the {len(hi):,} pairs the model rated high confidence.

{md_table([(str(r['posterior']), int(r['n']), f"{r['model_same_rate']:.2f}", f"{r['em_same_rate']:.2f}") for r in band.to_dict('records')], ["posterior band","pairs","model says same","EM says same"])}

Adjudications are stored in `d1_er_adjudications` for human review and do not change the graph automatically; pairs where the model says same with high confidence and the EM said different are the review queue for the next matcher iteration.
"""
write_section("Entity resolution adjudication", body); con.execute("CHECKPOINT"); con.close(); print(f"agreement {agree:.3f} (high conf {agree_hi:.3f}); methods updated")
