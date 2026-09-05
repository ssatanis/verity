#!/usr/bin/env python3
"""Run ingest/01_build_warehouse.sql against data/verity.duckdb one statement at a time, logging timings.
Usage: .venv/bin/python ingest/build_warehouse.py [--only nppes,spend] [--skip nppes]
Waits for the NPPES unzip to finish before the nppes statement (checks the CSV size against the zip listing)."""
import argparse, os, re, sys, time, duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
NPPES_CSV = "data/nppes/npidata_pfile_20050523-20260809.csv"; NPPES_BYTES = 11632650533

ap = argparse.ArgumentParser(); ap.add_argument("--only", default=""); ap.add_argument("--skip", default=""); ap.add_argument("--db", default=os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
a = ap.parse_args()
only = {s for s in a.only.split(",") if s}; skip = {s for s in a.skip.split(",") if s}

sql = open("ingest/01_build_warehouse.sql").read()
stmts = [s.strip() for s in re.split(r";\s*\n", sql) if s.strip() and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines())]
def name_of(s):
    m = re.search(r"CREATE OR REPLACE (?:TABLE|VIEW) (\w+)", s); return m.group(1) if m else s[:30]

os.makedirs("data/tmp_duckdb", exist_ok=True)
con = duckdb.connect(a.db)
con.execute("SET memory_limit='9GB'"); con.execute("SET threads=8"); con.execute("SET temp_directory='data/tmp_duckdb'"); con.execute("SET preserve_insertion_order=false")
log = open("logs/build_warehouse.log", "a")
def say(*x):
    m = time.strftime("%H:%M:%S") + " " + " ".join(str(i) for i in x); print(m, flush=True); log.write(m + "\n"); log.flush()

say(f"== build start db={a.db} statements={len(stmts)}")
for s in stmts:
    n = name_of(s)
    if only and n not in only: continue
    if n in skip: say(f"skip {n}"); continue
    if n == "nppes":
        while not (os.path.exists(NPPES_CSV) and os.path.getsize(NPPES_CSV) >= NPPES_BYTES):
            say(f"waiting for NPPES unzip ({os.path.getsize(NPPES_CSV) if os.path.exists(NPPES_CSV) else 0}/{NPPES_BYTES})"); time.sleep(30)
    t = time.time()
    try:
        con.execute(s)
        rows = con.execute(f"SELECT COUNT(*) FROM {n}").fetchone()[0] if re.match(r"\w+$", n) else None
        say(f"ok   {n:<20} rows={rows:<12} {time.time()-t:7.1f}s")
    except Exception as e:
        say(f"FAIL {n}: {e}"); 
        if n in ("timecodes", "spend"): sys.exit(1)
con.execute("CHECKPOINT"); con.close(); say("== build done")
