#!/usr/bin/env python3
"""SAM.gov exclusions -> `sam` table in the warehouse (the shape detectors/d3_revoked_but_paid.py expects).

Two sources, both keyed by SAM_API_KEY in .env:
  1. The daily PUBLIC exclusions extract (all ~170k active and inactive exclusions, with NPI where SAM has one), fetched through
     the Data Services extract API. This is the bulk source and is what the `sam` table is built from.
  2. The Exclusions API v4 (entity-information/v4/exclusions) for live, on-demand lookups by name/UEI (api/verify.py uses it).

Usage:
  python3 ingest/06_sam_exclusions.py            # refresh today's extract if possible, then (re)build the `sam` table
  python3 ingest/06_sam_exclusions.py --no-fetch # build from whatever extract is already in data/sam_exclusions/
"""
import argparse, datetime as dt, glob, io, os, sys, zipfile, urllib.request, urllib.parse
import duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
try:
    from dotenv import load_dotenv; load_dotenv(".env")
except ImportError:
    pass
ap = argparse.ArgumentParser(); ap.add_argument("--no-fetch", action="store_true"); a = ap.parse_args()
D = "data/sam_exclusions"; os.makedirs(D, exist_ok=True)
KEY = os.environ.get("SAM_API_KEY", "")

def fetch_extract():
    """The extract is named by 2-digit year + Julian day. Try today, then walk back a week."""
    if not KEY: print("SAM_API_KEY not set; skipping fetch"); return
    for back in range(0, 8):
        day = dt.date.today() - dt.timedelta(days=back)
        fn = f"SAM_Exclusions_Public_Extract_V2_{day.strftime('%y%j')}.ZIP"
        if os.path.exists(os.path.join(D, fn.replace(".ZIP", ".CSV"))): print("already have", fn); return
        url = ("https://api.sam.gov/data-services/v1/extracts?" +
               urllib.parse.urlencode(dict(api_key=KEY, fileType="EXCLUSION", sensitivity="PUBLIC", fileName=fn)))
        try:
            with urllib.request.urlopen(url, timeout=180) as r: blob = r.read()
            if not blob[:2] == b"PK": print("not a zip for", fn); continue
            open(os.path.join(D, fn), "wb").write(blob)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                for m in z.namelist():
                    if m.upper().endswith(".CSV"):
                        out = os.path.join(D, m)
                        if not os.path.exists(out): open(out, "wb").write(z.read(m))
            open(os.path.join(D, "source_url.txt"), "w").write(url.replace(KEY, "<SAM_API_KEY>"))
            print("fetched", fn, f"{len(blob)/1e6:.1f} MB"); return
        except Exception as e:
            print("no extract for", fn, "->", str(e)[:80])
    print("WARNING: could not fetch a fresh extract; using what is on disk")

if not a.no_fetch: fetch_extract()
csvs = sorted(glob.glob(os.path.join(D, "SAM_Exclusions_Public_Extract_V2_*.CSV")))
if not csvs: sys.exit("no SAM extract CSV in data/sam_exclusions")
src = csvs[-1]; print("building sam from", src)

con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
con.execute(f"""
CREATE OR REPLACE TABLE sam AS
SELECT "Classification" AS classification,
       NULLIF(trim("Name"),'') AS name, NULLIF(trim("First"),'') AS first_name, NULLIF(trim("Middle"),'') AS middle_name, NULLIF(trim("Last"),'') AS last_name,
       NULLIF(trim("Address 1"),'') AS address1, NULLIF(trim("City"),'') AS city, NULLIF(trim("State / Province"),'') AS state, NULLIF(trim("Country"),'') AS country,
       substr(NULLIF(trim("Zip Code"),''),1,5) AS zip5,
       NULLIF(trim("Unique Entity ID"),'') AS uei, NULLIF(trim("CAGE"),'') AS cage, NULLIF(trim("SAM Number"),'') AS sam_number,
       NULLIF(trim("Exclusion Program"),'') AS exclusion_program, NULLIF(trim("Excluding Agency"),'') AS excluding_agency,
       NULLIF(trim("CT Code"),'') AS ct_code, NULLIF(trim("Exclusion Type"),'') AS exclusion_type, NULLIF(trim("Additional Comments"),'') AS additional_comments,
       TRY_CAST("Active Date" AS DATE) AS active_dt,
       CASE WHEN TRY_CAST("Termination Date" AS DATE) > DATE '2100-01-01' THEN NULL ELSE TRY_CAST("Termination Date" AS DATE) END AS termination_dt,
       TRY_CAST("Termination Date" AS DATE) > DATE '2100-01-01' AS indefinite,
       NULLIF(trim("Record Status"),'') AS record_status, NULLIF(trim("Cross-Reference"),'') AS cross_reference,
       CASE WHEN regexp_matches(trim("NPI"), '^[12][0-9]{{9}}$') THEN trim("NPI") END AS npi,
       TRY_CAST("Creation_Date" AS DATE) AS creation_dt,
       '{os.path.basename(src)}' AS source_file
FROM read_csv('{src}', header=true, all_varchar=true, quote='"', escape='"', strict_mode=false)
""")
print(con.execute("""SELECT COUNT(*) AS rows, COUNT(npi) AS with_npi, COUNT(DISTINCT npi) AS npis,
  SUM(record_status='Active') AS active, SUM(excluding_agency='HHS') AS hhs, SUM(excluding_agency<>'HHS' AND npi IS NOT NULL) AS non_hhs_with_npi,
  MIN(active_dt), MAX(active_dt) FROM sam""").fetchdf().to_string(index=False))
print(con.execute("SELECT excluding_agency, COUNT(*) n, COUNT(npi) with_npi FROM sam GROUP BY 1 ORDER BY 2 DESC LIMIT 12").fetchdf().to_string(index=False))
con.execute("CHECKPOINT"); con.close(); print("ok: table sam written")
