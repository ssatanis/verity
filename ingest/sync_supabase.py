#!/usr/bin/env python3
"""Apply ingest/supabase_schema.sql and load the reference tables into Supabase Postgres.
Reads the raw files through an in-memory DuckDB (so it does not need the warehouse build to be finished) and COPYs into Postgres.
Usage: .venv/bin/python ingest/sync_supabase.py [--only timecodes,revoked,...] [--schema-only]"""
import argparse, io, json, os, sys, time, duckdb, psycopg
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); load_dotenv()
DB = os.environ.get("DATABASE_URL") or sys.exit("DATABASE_URL is empty; run ingest/find_pooler.py first")
E = "data/clean/cms_enrollment"

def d(x): return f"COALESCE(TRY_CAST({x} AS DATE), CAST(try_strptime({x}, '%m/%d/%Y') AS DATE))"
ENR_COLS = 'enrollment_id, ptype, enrollment_state, provider_type_code, provider_type_text, npi, multiple_npi_flag, ccn, associate_id, org_name, dba_name, inc_date, inc_state, org_structure, proprietary_nonprofit, address1, address2, city, state, zip5, zip9'
def enr(ptype, f):
    cols = [c[0] for c in duckdb.sql(f"DESCRIBE SELECT * FROM read_csv_auto('{E}/{f}', all_varchar=true, header=true)").fetchall()]
    def col(*names):  # first matching header, else NULL (CMS files differ: PROPRIETARY_NONPROFIT vs PROPRIETARY NONPROFIT, CCN missing in some)
        for n in names:
            if n in cols: return f'"{n}"'
        return "NULL"
    return f'''SELECT "ENROLLMENT ID", '{ptype}', {col("ENROLLMENT STATE")}, {col("PROVIDER TYPE CODE")}, {col("PROVIDER TYPE TEXT")}, "NPI", {col("MULTIPLE NPI FLAG")}, {col("CCN")}, {col("ASSOCIATE ID")},
      {col("ORGANIZATION NAME")}, {col("DOING BUSINESS AS NAME")}, {d(col("INCORPORATION DATE"))}, {col("INCORPORATION STATE")}, {col("ORGANIZATION TYPE STRUCTURE")}, {col("PROPRIETARY_NONPROFIT", "PROPRIETARY NONPROFIT")},
      {col("ADDRESS LINE 1")}, {col("ADDRESS LINE 2")}, {col("CITY")}, {col("STATE")}, substr({col("ZIP CODE")},1,5), {col("ZIP CODE")} FROM read_csv_auto('{E}/{f}', all_varchar=true, header=true)'''
OWN_COLS = 'ptype, enrollment_id, associate_id, org_name, owner_associate_id, owner_type, role_code, role_text, association_date, first_name, middle_name, last_name, title, owner_org_name, owner_dba, address1, address2, city, state, zip, pct_ownership, flags, other_type_text'
FLAGS = ["CREATED FOR ACQUISITION - OWNER","CORPORATION - OWNER","LLC - OWNER","MEDICAL PROVIDER SUPPLIER - OWNER","MANAGEMENT SERVICES COMPANY - OWNER","MEDICAL STAFFING COMPANY - OWNER","HOLDING COMPANY - OWNER","INVESTMENT FIRM - OWNER","FINANCIAL INSTITUTION - OWNER","CONSULTING FIRM - OWNER","FOR PROFIT - OWNER","NON PROFIT - OWNER","PRIVATE EQUITY COMPANY - OWNER","REIT - OWNER","CHAIN HOME OFFICE - OWNER","OTHER TYPE - OWNER","OTHER TYPE TEXT - OWNER","OWNED BY ANOTHER ORG OR IND - OWNER"]
def own(ptype, f):
    cols = [c[0] for c in duckdb.sql(f"DESCRIBE SELECT * FROM read_csv_auto('{E}/{f}', all_varchar=true, header=true)").fetchall()]
    marks = [k for k in FLAGS if k in cols and k != "OTHER TYPE TEXT - OWNER"]
    js = "'{' || array_to_string(list_filter([" + ", ".join(f"CASE WHEN \"{k}\"='Y' THEN '{k.replace(' - OWNER','').lower().replace(' ','_')}' END" for k in marks) + "], x -> x IS NOT NULL), ',') || '}'"
    other = '"OTHER TYPE TEXT - OWNER"' if "OTHER TYPE TEXT - OWNER" in cols else "NULL"
    return f'''SELECT '{ptype}', "ENROLLMENT ID", "ASSOCIATE ID", "ORGANIZATION NAME", "ASSOCIATE ID - OWNER", "TYPE - OWNER", "ROLE CODE - OWNER", "ROLE TEXT - OWNER",
      {d('"ASSOCIATION DATE - OWNER"')}, "FIRST NAME - OWNER", "MIDDLE NAME - OWNER", "LAST NAME - OWNER", "TITLE - OWNER", "ORGANIZATION NAME - OWNER", "DOING BUSINESS AS NAME - OWNER",
      "ADDRESS LINE 1 - OWNER", "ADDRESS LINE 2 - OWNER", "CITY - OWNER", "STATE - OWNER", "ZIP CODE - OWNER", TRY_CAST("PERCENTAGE OWNERSHIP" AS DOUBLE),
      {js}, {other} FROM read_csv_auto('{E}/{f}', all_varchar=true, header=true)'''

SAT = "data/clean/cms_program_integrity/MSATMarket_Saturation_and_Utilization_State_County_Dataset_Release_R23_2026-04-23.csv"
def num(c): return f"TRY_CAST(replace(replace(replace(trim({c}),',',''),'$',''),'%','') AS DOUBLE)"
LOADS = {
  "timecodes": ("hcpcs, description, minutes_per_unit, unit_basis, group_divisor, family, fraud_vector, mn_rate_per_unit, mn_daily_cap_hours, source, notes, personal_service",
     "SELECT hcpcs, description, TRY_CAST(minutes_per_unit AS DOUBLE), unit_basis, COALESCE(TRY_CAST(group_divisor AS INT),1), family, fraud_vector, TRY_CAST(mn_rate_per_unit AS DOUBLE), TRY_CAST(mn_daily_cap_hours AS DOUBLE), source, notes, personal_service = 'Y' FROM read_csv_auto('ingest/02_timecodes.csv', all_varchar=true, header=true)"),
  "revoked": ("enrlmt_id, npi, first_name, mdl_name, last_name, org_name, state, provider_type_desc, revocation_rsn, revoked_dt, reenroll_bar_dt",
     f"SELECT ENRLMT_ID, NPI, FIRST_NAME, MDL_NAME, LAST_NAME, ORG_NAME, STATE_CD, PROVIDER_TYPE_DESC, REVOCATION_RSN, CAST(try_strptime(REVOCATION_EFCTV_DT,'%m/%d/%Y') AS DATE), CAST(try_strptime(REENROLLMENT_BAR_EXPRTN_DT,'%m/%d/%Y') AS DATE) FROM read_csv_auto('{E}/Revocation_Extract_2026.07.30.csv', all_varchar=true, header=true)"),
  "leie": ("lastname, firstname, midname, busname, general, specialty, upin, npi, dob, address, city, state, zip, excltype, excl_dt, rein_dt, waiver_dt, wvrstate",
     """SELECT LASTNAME, FIRSTNAME, MIDNAME, BUSNAME, GENERAL, SPECIALTY, UPIN, NULLIF(NULLIF(NPI,'0000000000'),''),
        CASE WHEN DOB IN ('00000000','') THEN NULL ELSE CAST(try_strptime(DOB,'%Y%m%d') AS DATE) END, ADDRESS, CITY, STATE, ZIP, EXCLTYPE,
        CASE WHEN EXCLDATE IN ('00000000','') THEN NULL ELSE CAST(try_strptime(EXCLDATE,'%Y%m%d') AS DATE) END,
        CASE WHEN REINDATE IN ('00000000','') THEN NULL ELSE CAST(try_strptime(REINDATE,'%Y%m%d') AS DATE) END,
        CASE WHEN WAIVERDATE IN ('00000000','') THEN NULL ELSE CAST(try_strptime(WAIVERDATE,'%Y%m%d') AS DATE) END, WVRSTATE
        FROM read_csv_auto('data/clean/oig_leie/LEIE_UPDATED.csv', all_varchar=true, header=true)"""),
  "enrollments": (ENR_COLS, " UNION ALL ".join([enr("HOSPICE","Hospice_Enrollments_2026.07.17.csv"), enr("HHA","HHA_Enrollments_2026.07.17.csv"), enr("SNF","SNF_Enrollments_2026.07.31.csv"), enr("HOSPITAL","Hospital_Enrollments_2026.07.31.csv"), enr("FQHC","FQHC_Enrollments_2026.07.17.csv"), enr("RHC","RHC_Enrollments_2026.07.17.csv")])),
  "owners": (OWN_COLS, " UNION ALL ".join([own("HOSPICE","Hospice_All_Owners_2026.07.17.csv"), own("HHA","HHA_All_Owners_2026.07.17.csv"), own("SNF","SNF_All_Owners_2026.07.31.csv"), own("HOSPITAL","Hospital_All_Owners_2026.07.31.csv")])),
  "chow": ("ptype, buyer_enrollment_id, buyer_npi, buyer_ccn, buyer_org_name, chow_type, effective_dt, seller_enrollment_id, seller_npi, seller_ccn, seller_org_name",
     " UNION ALL ".join(f'''SELECT '{p}', "ENROLLMENT ID - BUYER", "NPI - BUYER", "CCN - BUYER", "ORGANIZATION NAME - BUYER", "CHOW TYPE TEXT", CAST(try_strptime("EFFECTIVE DATE",'%m/%d/%Y') AS DATE), "ENROLLMENT ID - SELLER", "NPI - SELLER", "CCN - SELLER", "ORGANIZATION NAME - SELLER" FROM read_csv_auto('{E}/{f}', all_varchar=true, header=true)''' for p, f in [("SNF","SNF_CHOW_2026.07.17.csv"),("HOSPITAL","Hospital_CHOW_2026.07.17.csv")])),
  "saturation_county": ("reference_period, period_year, type_of_service, aggregation_level, state, county, state_fips, county_fips, ffs_beneficiaries, providers, users_per_provider, pct_users_of_ffs, users, providers_per_county, dual_users, total_payment, moratorium, providers_per_10k_ffs",
     f"""SELECT reference_period, substr(reference_period,1,4), type_of_service, aggregation_level, state, county, trim(state_fips), trim(county_fips),
        {num('number_of_fee_for_service_beneficiaries')}::BIGINT, {num('number_of_providers')}::BIGINT, {num('average_number_of_users_per_provider')}, {num('percentage_of_users_out_of_ffs_beneficiaries')},
        {num('number_of_users')}::BIGINT, {num('average_number_of_providers_per_county')}, {num('number_of_dual_eligible_users')}::BIGINT, {num('total_payment')},
        CASE WHEN upper(trim(moratorium)) IN ('Y','YES','TRUE','1') THEN TRUE WHEN trim(moratorium)='' THEN NULL ELSE FALSE END,
        CASE WHEN {num('number_of_fee_for_service_beneficiaries')} > 0 THEN 10000.0 * {num('number_of_providers')} / {num('number_of_fee_for_service_beneficiaries')} END
        FROM read_csv_auto('{SAT}', all_varchar=true, header=true, normalize_names=false)
        WHERE aggregation_level IN ('COUNTY','STATE','NATION + TERRITORIES','NATION') AND reference_period >= '2023'"""),
}

def copy_table(pg, ddb, table, cols, sql):
    t = time.time(); buf = io.StringIO()
    ddb.execute(f"COPY ({sql}) TO '/dev/stdout' (FORMAT CSV, HEADER false, NULL '')") if False else None
    tmp = f"demo/cache/{table}.csv"; ddb.execute(f"COPY ({sql}) TO '{tmp}' (FORMAT CSV, HEADER false, NULL '', QUOTE '\"', ESCAPE '\"')")
    n = ddb.execute(f"SELECT COUNT(*) FROM read_csv_auto('{tmp}', header=false, all_varchar=true)").fetchone()[0]
    with pg.cursor() as cur:
        cur.execute(f"TRUNCATE public.{table}"); pg.commit()  # commit first: frees the old file before the reload (small Supabase disks)
        with open(tmp, "rb") as f, cur.copy(f"COPY public.{table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')") as cp:
            for chunk in iter(lambda: f.read(1 << 20), b""): cp.write(chunk)
    pg.commit(); print(f"synced {table:<20} {n:>9,} rows {time.time()-t:6.1f}s", flush=True); return n

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--only", default=""); ap.add_argument("--schema-only", action="store_true"); a = ap.parse_args()
    only = {s for s in a.only.split(",") if s}; os.makedirs("demo/cache", exist_ok=True)
    pg = psycopg.connect(DB, autocommit=False)
    with pg.cursor() as cur: cur.execute(open("ingest/supabase_schema.sql").read())
    pg.commit(); print("schema applied")
    if a.schema_only: sys.exit(0)
    ddb = duckdb.connect(); ddb.execute("SET threads=4"); ddb.execute("SET memory_limit='3GB'")
    src = {}
    try: src = {os.path.basename(k): v for k, v in json.load(open("data/manifest.json")).items()} if isinstance(json.load(open("data/manifest.json")), dict) else {}
    except Exception: pass
    counts = {}
    for table, (cols, sql) in LOADS.items():
        if only and table not in only: continue
        counts[table] = copy_table(pg, ddb, table, cols, sql)
    with pg.cursor() as cur:
        for table, n in counts.items():
            cur.execute("INSERT INTO public.datasets (id, name, rows, notes, loaded_at) VALUES (%s, %s, %s, %s, now()) ON CONFLICT (id) DO UPDATE SET rows = excluded.rows, loaded_at = now()",
                        (table, f"public.{table}", n, "loaded by ingest/sync_supabase.py from the raw CMS/OIG files"))
    pg.commit(); pg.close(); print("done", counts)
