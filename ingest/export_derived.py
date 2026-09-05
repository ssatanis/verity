#!/usr/bin/env python3
"""Export the mid-sized warehouse tables as parquet and upload them to the public verity-derived bucket, so the API,
notebooks and the front end can load them straight from Supabase Storage (DuckDB: read_parquet('<public url>')).
The 56.7M-row spend table stays local; detectors run on DuckDB and push results to Postgres.
Usage: .venv/bin/python ingest/export_derived.py [--only spend_totals,provider_state]"""
import argparse, hashlib, json, os, time, duckdb, httpx
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); load_dotenv()
URL = os.environ["SUPABASE_URL"]; KEY = os.environ["SUPABASE_SECRET_KEY"]; H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
BUCKET = "verity-derived"; OUT = "demo/cache/derived"; os.makedirs(OUT, exist_ok=True)

EXPORTS = {
  "timecodes": "SELECT * FROM timecodes",
  "revoked": "SELECT * FROM revoked",
  "leie": "SELECT * FROM leie",
  "hospice": "SELECT * FROM hospice", "hha": "SELECT * FROM hha", "snf": "SELECT * FROM snf", "hospital": "SELECT * FROM hospital",
  "owners": "SELECT * FROM owners", "chow": "SELECT * FROM chow", "optout": "SELECT * FROM optout",
  "saturation_county": "SELECT * FROM saturation_county WHERE reference_period >= '2019'",
  "spend_totals": "SELECT * FROM spend_totals",
  "provider_state": "SELECT * FROM provider_state",
  "drops": "SELECT * FROM drops",
  # NPPES rows for every NPI that appears in a CMS facility enrollment file, the revoked list or LEIE (small, joinable)
  "nppes_facilities": """SELECT n.* FROM nppes n WHERE n.npi IN (SELECT "NPI" FROM hospice UNION SELECT "NPI" FROM hha UNION SELECT "NPI" FROM snf
                         UNION SELECT "NPI" FROM hospital UNION SELECT npi FROM revoked UNION SELECT npi FROM leie WHERE npi IS NOT NULL)""",
}
def sha(p):
    h = hashlib.sha256(); f = open(p, "rb")
    for c in iter(lambda: f.read(1 << 20), b""): h.update(c)
    return h.hexdigest()
if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=""); a = ap.parse_args(); only = {s for s in a.only.split(",") if s}
    con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"), read_only=True); manifest = []
    for name, sql in EXPORTS.items():
        if only and name not in only: continue
        t = time.time(); p = f"{OUT}/{name}.parquet"
        con.execute(f"COPY ({sql}) TO '{p}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{p}')").fetchone()[0]; size = os.path.getsize(p)
        if size > 49 * 1024 * 1024: print(f"skip    {name} {size/1e6:.0f} MB exceeds the 50 MB object limit"); continue
        r = httpx.post(f"{URL}/storage/v1/object/{BUCKET}/{name}.parquet", headers={**H, "Content-Type": "application/octet-stream", "x-upsert": "true"}, content=open(p, "rb").read(), timeout=600)
        print(f"{'upload' if r.status_code < 300 else 'FAIL ' + str(r.status_code):<8}{name:<20} {rows:>10,} rows {size/1e6:6.1f} MB {time.time()-t:5.1f}s", flush=True)
        if r.status_code < 300: manifest.append(dict(obj=f"{name}.parquet", rows=rows, bytes=size, sha256=sha(p), sql=sql.strip()))
    if only:  # partial run: merge into the manifest already in the bucket instead of replacing it
        try:
            prev = httpx.get(f"{URL}/storage/v1/object/public/{BUCKET}/manifest.json", timeout=60).json().get("objects", [])
            done = {m["obj"] for m in manifest}; manifest = [m for m in prev if m["obj"] not in done] + manifest
        except Exception as e: print("could not merge previous manifest:", e)
    body = json.dumps({"bucket": BUCKET, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "public_base": f"{URL}/storage/v1/object/public/{BUCKET}/", "objects": sorted(manifest, key=lambda m: m["obj"])}, indent=1).encode()
    r = httpx.post(f"{URL}/storage/v1/object/{BUCKET}/manifest.json", headers={**H, "Content-Type": "application/json", "x-upsert": "true"}, content=body, timeout=60)
    print("manifest", r.status_code, len(manifest), "objects")
