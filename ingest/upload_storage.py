#!/usr/bin/env python3
"""Upload the small public source files (and derived extracts) to Supabase Storage, and write a manifest.
Files over 45 MB are gzipped first (Supabase's default per-file limit is 50 MB). Re-runnable: skips unchanged files.
Usage: .venv/bin/python ingest/upload_storage.py [--bucket verity-raw] [--only pattern]"""
import argparse, gzip, hashlib, json, os, shutil, sys, time
import httpx
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); load_dotenv()
URL = os.environ["SUPABASE_URL"]; KEY = os.environ["SUPABASE_SECRET_KEY"]
H = {"apikey": KEY, "Authorization": f"Bearer {KEY}"}
LIMIT = 45 * 1024 * 1024

# (local path, object path in bucket). Large files get a .gz suffix automatically.
RAW = [
  ("ingest/02_timecodes.csv", "reference/timecodes.csv"),
  ("data/manifest.json", "reference/download_manifest.json"),
  ("data/oig_leie/LEIE_UPDATED.csv", "oig_leie/LEIE_UPDATED.csv"),
  ("data/medicaid_tmsis/medicare-revoked-providers-and-suppliers.parquet", "medicaid_tmsis/medicare-revoked-providers-and-suppliers.parquet"),
  ("data/nppes/NPPES Deactivated NPI Report 20260810.xlsx", "nppes/NPPES_Deactivated_NPI_Report_20260810.xlsx"),
] + [(f"data/cms_enrollment/{f}", f"cms_enrollment/{f}") for f in [
  "Hospice_Enrollments_2026.07.17.csv","Hospice_All_Owners_2026.07.17.csv","HHA_Enrollments_2026.07.17.csv","HHA_All_Owners_2026.07.17.csv",
  "SNF_Enrollments_2026.07.31.csv","SNF_All_Owners_2026.07.31.csv","SNF_CHOW_2026.07.17.csv","SNF_CHOW_Owners_2026.07.17.csv",
  "Hospital_Enrollments_2026.07.31.csv","Hospital_All_Owners_2026.07.31.csv","Hospital_CHOW_2026.07.17.csv","Hospital_CHOW_Owners_2026.07.17.csv",
  "FQHC_Enrollments_2026.07.17.csv","FQHC_All_Owners_2026.07.17.csv","RHC_Enrollments_2026.07.17.csv","RHC_All_Owners_2026.07.17.csv",
  "Revocation_Extract_2026.07.30.csv","OptOut_July2026.csv","Chain_Performance_20260812.csv","OrderReferring_20260831.csv"]] + [
  (f"data/care_compare/{f}", f"care_compare/{f}") for f in [
  "Hospice_General-Information_Aug2026_2.csv","Hospice_Provider_Aug2026.csv","Hospice_State_Aug2026.csv","Hospice_National_Aug2026.csv",
  "HH_Provider_Jul2026.csv","HH_State_Jul2026.csv","Hospital_General_Information.csv","NH_ProviderInfo_Aug2026.csv","NH_Ownership_Aug2026.csv","NH_Penalties_Aug2026.csv",
  "Long-Term_Care_Hospital-Provider_Data_Jun2026.csv","Inpatient_Rehabilitation_Facility-Provider_Data_Jun2026_b.csv"]] + [
  ("data/openfda/drug_shortages.json", "openfda/drug_shortages.json"),
  ("data/open_payments/OP_DTL_OWNRSHP_PGYR2025_P06302026_06032026.csv", "open_payments/OP_DTL_OWNRSHP_PGYR2025.csv"),
  ("data/open_payments/PBLCTN_RPTG_ORG_SMRY_P06302026_06032026.csv", "open_payments/PBLCTN_RPTG_ORG_SMRY.csv"),
]

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def existing(bucket):
    out = {}; offset = 0
    while True:
        r = httpx.post(f"{URL}/storage/v1/object/list/{bucket}", headers=H, json={"prefix": "", "limit": 1000, "offset": offset, "sortBy": {"column": "name", "order": "asc"}}, timeout=60)
        r.raise_for_status(); items = r.json()
        if not items: break
        for it in items: out[it["name"]] = it
        offset += len(items)
    return out

def list_recursive(bucket, prefix=""):
    out = {}
    r = httpx.post(f"{URL}/storage/v1/object/list/{bucket}", headers=H, json={"prefix": prefix, "limit": 1000, "offset": 0}, timeout=60); r.raise_for_status()
    for it in r.json():
        name = f"{prefix}/{it['name']}" if prefix else it["name"]
        if it.get("id") is None: out.update(list_recursive(bucket, name))
        else: out[name] = it
    return out

def upload(bucket, local, obj, have):
    if not os.path.exists(local): print(f"missing {local}"); return None
    size = os.path.getsize(local); send = local; content_type = "application/octet-stream"
    if local.endswith(".csv"): content_type = "text/csv"
    if local.endswith(".json"): content_type = "application/json"
    if size > LIMIT:
        gz = os.path.join("demo/cache", os.path.basename(local) + ".gz")
        if not os.path.exists(gz) or os.path.getmtime(gz) < os.path.getmtime(local):
            with open(local, "rb") as fi, gzip.open(gz, "wb", compresslevel=6) as fo: shutil.copyfileobj(fi, fo, 1 << 20)
        send = gz; obj = obj + ".gz"; content_type = "application/gzip"
    digest = sha256(send); meta = have.get(obj, {}).get("metadata") or {}
    if meta.get("size") == os.path.getsize(send) and have.get(obj, {}).get("user_metadata", {}).get("sha256") == digest:
        print(f"same    {obj}"); return dict(obj=obj, bytes=os.path.getsize(send), sha256=digest, local=local)
    with open(send, "rb") as f:
        r = httpx.post(f"{URL}/storage/v1/object/{bucket}/{obj}", headers={**H, "Content-Type": content_type, "x-upsert": "true", "x-metadata": json.dumps({"sha256": digest, "source_path": local}).encode().hex() if False else ""}, content=f.read(), timeout=600)
    if r.status_code >= 300: print(f"FAIL    {obj} {r.status_code} {r.text[:200]}"); return None
    print(f"upload  {obj} {os.path.getsize(send)/1e6:.1f} MB"); return dict(obj=obj, bytes=os.path.getsize(send), sha256=digest, local=local)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--bucket", default="verity-raw"); ap.add_argument("--only", default=""); a = ap.parse_args()
    os.makedirs("demo/cache", exist_ok=True)
    have = list_recursive(a.bucket); manifest = []; src = json.load(open("data/manifest.json")) if os.path.exists("data/manifest.json") else {}
    for local, obj in RAW:
        if a.only and a.only not in local: continue
        m = upload(a.bucket, local, obj, have)
        if m: manifest.append(m)
    body = json.dumps({"bucket": a.bucket, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "public_base": f"{URL}/storage/v1/object/public/{a.bucket}/", "objects": manifest}, indent=1).encode()
    r = httpx.post(f"{URL}/storage/v1/object/{a.bucket}/manifest.json", headers={**H, "Content-Type": "application/json", "x-upsert": "true"}, content=body, timeout=60)
    print("manifest", r.status_code, len(manifest), "objects")
