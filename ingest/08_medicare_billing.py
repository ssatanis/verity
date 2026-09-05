"""Per-NPI Medicare billing by year from the CMS public use files already on disk: Part B (Physician and Other Practitioners, by provider),
Part D (prescribers, by NPI), DME (by referring provider) and post-acute care (hospice, home health, SNF, IRF, LTCH by provider, mapped from CCN to NPI
through the enrollment files). Writes medicare_billing(npi, year, program, services, beneficiaries, paid) in DuckDB."""
from __future__ import annotations
import glob, os, re, time
import duckdb
DB = os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"); con = duckdb.connect(DB); t0 = time.time()
def log(m): print(f"[{time.time()-t0:5.0f}s] {m}", flush=True)
con.execute("CREATE OR REPLACE TABLE medicare_billing (npi VARCHAR, year INTEGER, program VARCHAR, services DOUBLE, beneficiaries DOUBLE, paid DOUBLE)")
def year_of(path):
    m = re.search(r"(20\d\d)", os.path.basename(path)); return int(m.group(1)) if m else None
def load(files, program, npi_col, svc_col, bene_col, paid_col, extra_where=""):
    n = 0
    for f in sorted(files):
        y = year_of(f)
        if not y: continue
        try:
            con.execute(f"""INSERT INTO medicare_billing
                SELECT CAST("{npi_col}" AS VARCHAR), {y}, '{program}', SUM(TRY_CAST("{svc_col}" AS DOUBLE)), SUM(TRY_CAST("{bene_col}" AS DOUBLE)), SUM(TRY_CAST("{paid_col}" AS DOUBLE))
                FROM read_csv('{f}', header=true, all_varchar=true, ignore_errors=true, quote='"', escape='"')
                WHERE "{npi_col}" IS NOT NULL AND length("{npi_col}") = 10 {extra_where} GROUP BY 1""")
            n += con.execute("SELECT COUNT(*) FROM medicare_billing WHERE program = ? AND year = ?", (program, y)).fetchone()[0]
            log(f"{program} {y}: loaded")
        except Exception as e:
            log(f"{program} {os.path.basename(f)} skipped: {str(e)[:90]}")
    return n
log("Part B by provider"); load(glob.glob("data/cms_utilization/Physician_Other_Practitioners/*_Prov.csv"), "Medicare Part B", "Rndrng_NPI", "Tot_Srvcs", "Tot_Benes", "Tot_Mdcr_Pymt_Amt")
log("Part D by prescriber"); load([f for f in glob.glob("data/cms_utilization/Part_D_Prescribers/*.csv") if re.search(r"_npi\.csv$", f, re.I)], "Medicare Part D", "Prscrbr_NPI", "Tot_Clms", "Tot_Benes", "Tot_Drug_Cst")
log("DME by referring provider"); load([f for f in glob.glob("data/cms_utilization/Durable_Medical_Equipment_Devices_Supplies/*.csv") if re.search(r"_rfrr\.csv$", f, re.I)], "Medicare DME referrals", "Rfrg_NPI", "Tot_Suplr_Srvcs", "Tot_Suplr_Benes", "Suplr_Mdcr_Pymt_Amt")
# post-acute care by provider (CCN), mapped to NPI through the enrollment files
con.execute("""CREATE OR REPLACE TEMP TABLE ccn_npi AS
  SELECT DISTINCT ccn, npi FROM (
    SELECT CAST(ccn AS VARCHAR) AS ccn, CAST(npi AS VARCHAR) AS npi FROM hospice UNION ALL
    SELECT CAST(ccn AS VARCHAR), CAST(npi AS VARCHAR) FROM hha UNION ALL
    SELECT CAST(ccn AS VARCHAR), CAST(npi AS VARCHAR) FROM snf) WHERE ccn IS NOT NULL AND npi IS NOT NULL""")
prog = {"HOS": "Medicare hospice", "HH": "Medicare home health", "SNF": "Medicare skilled nursing", "IRF": "Medicare inpatient rehab", "LTC": "Medicare long-term care hospital"}
for f in sorted(glob.glob("data/cms_utilization/post_acute/*main*.csv")):
    y = year_of(f); key = next((k for k in prog if re.search(rf"_{k}_", f)), None)
    if not y or not key: continue
    try:
        con.execute(f"""INSERT INTO medicare_billing
            SELECT m.npi, {y}, '{prog[key]}', SUM(TRY_CAST(p."TOT_EPSD_STAY_CNT" AS DOUBLE)), SUM(TRY_CAST(p."BENE_DSTNCT_CNT" AS DOUBLE)), SUM(TRY_CAST(p."TOT_MDCR_PYMT_AMT" AS DOUBLE))
            FROM read_csv('{f}', header=true, all_varchar=true, ignore_errors=true) p JOIN ccn_npi m ON m.ccn = lpad(CAST(p."PRVDR_ID" AS VARCHAR), 6, '0')
            WHERE upper(p."SMRY_CTGRY") LIKE 'PROVIDER%' GROUP BY 1""")
        log(f"{prog[key]} {y}: loaded")
    except Exception as e: log(f"{os.path.basename(f)} skipped: {str(e)[:90]}")
print(con.execute("SELECT program, COUNT(DISTINCT npi), MIN(year), MAX(year), ROUND(SUM(paid)/1e9,1) AS billions FROM medicare_billing GROUP BY 1 ORDER BY 1").fetchall())
log("done")
