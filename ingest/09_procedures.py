"""Procedure-level evidence. Builds, in DuckDB:
  medicare_svc            per NPI, year, HCPCS from the Medicare Physician and Other Practitioners by-service files (2023, 2024): services, beneficiaries, average submitted charge, allowed and paid
  hcpcs_desc              code descriptions (from the Medicare file, plus the time-code table)
  medicare_code_norms     per code: median and 90th percentile of the submitted-to-allowed ratio across providers (2024)
  spend_npi_code          per NPI, role, HCPCS from T-MSIS Medicaid: paid, claim lines, months, patient-months (rebuilt with patients)
  medicaid_code_norms     per code: median and 95th percentile of Medicaid dollars per patient-month across providers billing it for 6 or more months
  provider_codes          per NPI: the eight largest Medicaid codes with share, dollars per patient-month and its percentile, whether the code is a high-risk vector, and the Medicare charge ratio versus peers
  procedure_trends        codes that recur among tier 1 and tier 2 providers far more often than among all providers (lift), with dollars
  provider_procedure_signal  per NPI: 0 to 8 points and a plain-language reason for the unified risk score"""
from __future__ import annotations
import glob, os, re, time
import duckdb
DB = os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"); con = duckdb.connect(DB); t0 = time.time()
def log(m): print(f"[{time.time()-t0:5.0f}s] {m}", flush=True)
have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}

# 1. Medicare by service (latest two years)
files = sorted(f for f in glob.glob("data/cms_utilization/Physician_Other_Practitioners/*Prov_Svc.csv") if re.search(r"(2023|2024)", os.path.basename(f)))
con.execute("CREATE OR REPLACE TABLE medicare_svc (npi VARCHAR, year INTEGER, hcpcs VARCHAR, description VARCHAR, drug_ind VARCHAR, place VARCHAR, beneficiaries DOUBLE, services DOUBLE, avg_submitted DOUBLE, avg_allowed DOUBLE, avg_paid DOUBLE)")
for f in files:
    y = int(re.search(r"(20\d\d)", os.path.basename(f)).group(1))
    con.execute(f"""INSERT INTO medicare_svc
        SELECT Rndrng_NPI, {y}, HCPCS_Cd, HCPCS_Desc, HCPCS_Drug_Ind, Place_Of_Srvc, TRY_CAST(Tot_Benes AS DOUBLE), TRY_CAST(Tot_Srvcs AS DOUBLE),
               TRY_CAST(Avg_Sbmtd_Chrg AS DOUBLE), TRY_CAST(Avg_Mdcr_Alowd_Amt AS DOUBLE), TRY_CAST(Avg_Mdcr_Pymt_Amt AS DOUBLE)
        FROM read_csv('{f}', header=true, all_varchar=true, ignore_errors=true)""")
    log(f"medicare_svc {y}: {con.execute('SELECT COUNT(*) FROM medicare_svc WHERE year = ?', (y,)).fetchone()[0]:,} rows")
con.execute("""CREATE OR REPLACE TABLE hcpcs_desc AS
  SELECT hcpcs, description FROM (
    SELECT hcpcs, arg_max(description, year) AS description FROM medicare_svc WHERE description IS NOT NULL GROUP BY 1
    UNION ALL
    SELECT t.hcpcs, t.description FROM timecodes t WHERE t.hcpcs NOT IN (SELECT hcpcs FROM medicare_svc)) GROUP BY 1, 2""")
con.execute("""CREATE OR REPLACE TABLE medicare_code_norms AS
  SELECT hcpcs, COUNT(*) AS n_providers, quantile_cont(avg_submitted / NULLIF(avg_allowed, 0), 0.5) AS ratio_median, quantile_cont(avg_submitted / NULLIF(avg_allowed, 0), 0.9) AS ratio_p90,
         quantile_cont(avg_allowed, 0.5) AS allowed_median
  FROM medicare_svc WHERE year = 2024 AND avg_allowed > 0 GROUP BY 1 HAVING COUNT(*) >= 20""")
log(f"hcpcs_desc {con.execute('SELECT COUNT(*) FROM hcpcs_desc').fetchone()[0]:,}, medicare_code_norms {con.execute('SELECT COUNT(*) FROM medicare_code_norms').fetchone()[0]:,}")

# 2. Medicaid per NPI and code, with patient-months
con.execute("""CREATE OR REPLACE TABLE spend_npi_code AS
  SELECT npi, role, hcpcs, SUM(paid) AS paid, SUM(lines) AS lines, COUNT(DISTINCT month) AS months, SUM(patients) AS patient_months FROM (
    SELECT SERVICING_PROVIDER_NPI_NUM AS npi, 'servicing' AS role, HCPCS_CODE AS hcpcs, CLAIM_FROM_MONTH AS month, TOTAL_PAID AS paid, TOTAL_CLAIM_LINES AS lines, TOTAL_PATIENTS AS patients
    FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet') WHERE regexp_matches(SERVICING_PROVIDER_NPI_NUM, '^[0-9]{10}$')
    UNION ALL
    SELECT BILLING_PROVIDER_NPI_NUM, 'billing', HCPCS_CODE, CLAIM_FROM_MONTH, TOTAL_PAID, TOTAL_CLAIM_LINES, TOTAL_PATIENTS
    FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet') WHERE regexp_matches(BILLING_PROVIDER_NPI_NUM, '^[0-9]{10}$') AND BILLING_PROVIDER_NPI_NUM <> SERVICING_PROVIDER_NPI_NUM)
  GROUP BY 1, 2, 3""")
log(f"spend_npi_code {con.execute('SELECT COUNT(*) FROM spend_npi_code').fetchone()[0]:,} rows")
con.execute("""CREATE OR REPLACE TABLE medicaid_code_norms AS
  SELECT hcpcs, COUNT(*) AS n_providers, quantile_cont(paid / patient_months, 0.5) AS dpm_median, quantile_cont(paid / patient_months, 0.95) AS dpm_p95
  FROM spend_npi_code WHERE role = 'servicing' AND months >= 6 AND patient_months > 0 GROUP BY 1 HAVING COUNT(*) >= 30""")
# percentile of each provider's dollars per patient-month within its code (servicing role, 6+ months)
con.execute("""CREATE OR REPLACE TABLE spend_npi_code_pct AS
  SELECT npi, hcpcs, PERCENT_RANK() OVER (PARTITION BY hcpcs ORDER BY paid / patient_months) AS dpm_pct
  FROM spend_npi_code WHERE role = 'servicing' AND months >= 6 AND patient_months > 0
    AND hcpcs IN (SELECT hcpcs FROM medicaid_code_norms)""")
log("code norms and percentiles built")

# 3. provider_codes: the eight largest Medicaid codes per NPI, for every NPI any detector reached plus every provider in the serving tables
con.execute("""CREATE OR REPLACE TABLE provider_codes AS
  WITH pool AS (SELECT DISTINCT npi FROM provider_risk UNION SELECT DISTINCT npi FROM cluster_members WHERE npi IS NOT NULL UNION SELECT DISTINCT npi FROM flags),
  agg AS (SELECT s.npi, s.hcpcs, SUM(s.paid) AS paid, SUM(s.lines) AS lines, MAX(s.months) AS months, SUM(s.patient_months) AS patient_months
          FROM spend_npi_code s JOIN pool USING (npi) GROUP BY 1, 2),
  tot AS (SELECT npi, SUM(paid) AS total FROM agg GROUP BY 1),
  ranked AS (SELECT a.*, t.total, ROW_NUMBER() OVER (PARTITION BY a.npi ORDER BY a.paid DESC) AS rk FROM agg a JOIN tot t USING (npi))
  SELECT r.npi, r.hcpcs, COALESCE(d.description, '') AS description, r.paid, r.paid / NULLIF(r.total, 0) AS share, r.lines, r.months, r.patient_months,
         r.paid / NULLIF(r.patient_months, 0) AS dpm, p.dpm_pct, n.dpm_median, n.dpm_p95,
         COALESCE(t.fraud_vector = 'HIGH', FALSE) AS high_vector, t.family AS code_family,
         m.avg_submitted, m.avg_allowed, m.avg_submitted / NULLIF(m.avg_allowed, 0) AS charge_ratio, mn.ratio_median AS peer_ratio_median, mn.ratio_p90 AS peer_ratio_p90, m.services AS medicare_services, r.rk
  FROM ranked r LEFT JOIN hcpcs_desc d USING (hcpcs) LEFT JOIN spend_npi_code_pct p ON p.npi = r.npi AND p.hcpcs = r.hcpcs
  LEFT JOIN medicaid_code_norms n ON n.hcpcs = r.hcpcs LEFT JOIN timecodes t ON t.hcpcs = r.hcpcs
  LEFT JOIN (SELECT npi, hcpcs, SUM(services) AS services, SUM(avg_submitted * services) / NULLIF(SUM(services), 0) AS avg_submitted, SUM(avg_allowed * services) / NULLIF(SUM(services), 0) AS avg_allowed
             FROM medicare_svc WHERE year = 2024 GROUP BY 1, 2) m ON m.npi = r.npi AND m.hcpcs = r.hcpcs
  LEFT JOIN medicare_code_norms mn ON mn.hcpcs = r.hcpcs
  WHERE r.rk <= 8""")
log(f"provider_codes {con.execute('SELECT COUNT(*) FROM provider_codes').fetchone()[0]:,} rows for {con.execute('SELECT COUNT(DISTINCT npi) FROM provider_codes').fetchone()[0]:,} NPIs")

# Medicare-only providers in the pool: their largest Medicare codes and charge ratios (so a provider page never lacks procedures)
con.execute("""CREATE OR REPLACE TABLE provider_codes_medicare AS
  WITH pool AS (SELECT DISTINCT npi FROM provider_risk UNION SELECT DISTINCT npi FROM cluster_members WHERE npi IS NOT NULL UNION SELECT DISTINCT npi FROM flags),
  agg AS (SELECT s.npi, s.hcpcs, arg_max(s.description, s.year) AS description, SUM(s.services) AS services, SUM(s.beneficiaries) AS beneficiaries,
                 SUM(s.avg_paid * s.services) AS paid, SUM(s.avg_submitted * s.services) / NULLIF(SUM(s.services), 0) AS avg_submitted, SUM(s.avg_allowed * s.services) / NULLIF(SUM(s.services), 0) AS avg_allowed
          FROM medicare_svc s JOIN pool USING (npi) WHERE s.year = 2024 GROUP BY 1, 2),
  tot AS (SELECT npi, SUM(paid) AS total FROM agg GROUP BY 1)
  SELECT a.npi, a.hcpcs, a.description, a.services, a.beneficiaries, a.paid, a.paid / NULLIF(t.total, 0) AS share, a.avg_submitted, a.avg_allowed,
         a.avg_submitted / NULLIF(a.avg_allowed, 0) AS charge_ratio, n.ratio_median AS peer_ratio_median, n.ratio_p90 AS peer_ratio_p90,
         ROW_NUMBER() OVER (PARTITION BY a.npi ORDER BY a.paid DESC) AS rk
  FROM agg a JOIN tot t USING (npi) LEFT JOIN medicare_code_norms n USING (hcpcs) QUALIFY rk <= 8""")
log(f"provider_codes_medicare {con.execute('SELECT COUNT(*) FROM provider_codes_medicare').fetchone()[0]:,} rows")

# 4. procedure trends: codes that recur among tier 1 and 2 providers
con.execute("""CREATE OR REPLACE TABLE procedure_trends AS
  WITH flagged AS (SELECT npi, tier FROM provider_risk WHERE tier <= 2),
  nf AS (SELECT COUNT(*) AS n FROM flagged), na AS (SELECT COUNT(DISTINCT npi) AS n FROM spend_npi_code WHERE role = 'servicing'),
  per_code AS (
    SELECT s.hcpcs, COUNT(DISTINCT s.npi) FILTER (WHERE f.npi IS NOT NULL) AS n_flagged, COUNT(DISTINCT s.npi) AS n_all,
           SUM(s.paid) FILTER (WHERE f.npi IS NOT NULL) AS paid_flagged, SUM(s.paid) AS paid_all,
           COUNT(DISTINCT s.npi) FILTER (WHERE f.tier = 1) AS n_tier1, COUNT(DISTINCT s.npi) FILTER (WHERE f.tier = 2) AS n_tier2
    FROM spend_npi_code s LEFT JOIN flagged f USING (npi) WHERE s.role = 'servicing' GROUP BY 1)
  SELECT p.hcpcs, COALESCE(d.description, '') AS description, p.n_flagged, p.n_all, p.n_tier1, p.n_tier2, p.paid_flagged, p.paid_all,
         (p.n_flagged::DOUBLE / (SELECT n FROM nf)) / NULLIF(p.n_all::DOUBLE / (SELECT n FROM na), 0) AS lift,
         COALESCE(t.fraud_vector, '') AS vector, t.family
  FROM per_code p LEFT JOIN hcpcs_desc d USING (hcpcs) LEFT JOIN timecodes t USING (hcpcs)
  WHERE p.n_flagged >= 8 ORDER BY lift DESC""")
log(f"procedure_trends {con.execute('SELECT COUNT(*) FROM procedure_trends').fetchone()[0]:,} codes")

# 5. procedure signal per NPI (0 to 8 points) for the unified score
con.execute("""CREATE OR REPLACE TABLE provider_procedure_signal AS
  WITH c AS (SELECT * FROM provider_codes WHERE rk <= 5),
  per AS (
    SELECT npi,
      MAX(CASE WHEN dpm_pct >= 0.95 AND months >= 12 AND patient_months >= 50 THEN 1 ELSE 0 END) AS intense,
      SUM(CASE WHEN high_vector THEN share ELSE 0 END) AS high_share,
      MAX(CASE WHEN charge_ratio IS NOT NULL AND peer_ratio_median IS NOT NULL AND charge_ratio >= 3 * peer_ratio_median AND medicare_services >= 50 THEN 1 ELSE 0 END) AS overcharge,
      arg_max(hcpcs, CASE WHEN dpm_pct >= 0.95 AND months >= 12 AND patient_months >= 50 THEN dpm_pct ELSE 0 END) AS intense_code,
      MAX(CASE WHEN dpm_pct >= 0.95 AND months >= 12 AND patient_months >= 50 THEN dpm ELSE NULL END) AS intense_dpm,
      arg_max(hcpcs, CASE WHEN charge_ratio IS NOT NULL AND peer_ratio_median IS NOT NULL AND charge_ratio >= 3 * peer_ratio_median AND medicare_services >= 50 THEN charge_ratio ELSE 0 END) AS overcharge_code,
      MAX(CASE WHEN charge_ratio IS NOT NULL AND peer_ratio_median IS NOT NULL AND charge_ratio >= 3 * peer_ratio_median AND medicare_services >= 50 THEN charge_ratio / peer_ratio_median ELSE NULL END) AS overcharge_x
    FROM c GROUP BY 1)
  SELECT p.npi, 4 * intense + CASE WHEN high_share >= 0.6 THEN 2 ELSE 0 END + 2 * overcharge AS points,
         concat_ws('; ',
           CASE WHEN intense = 1 THEN 'Medicaid dollars per patient on code ' || intense_code || ' ($' || CAST(ROUND(intense_dpm) AS BIGINT) || ' per patient-month) sit in the top 5% of every provider billing that code' END,
           CASE WHEN high_share >= 0.6 THEN CAST(ROUND(100 * high_share) AS INTEGER) || '% of Medicaid dollars are on codes with a history of abuse' END,
           CASE WHEN overcharge = 1 THEN 'Medicare submitted charges on code ' || overcharge_code || ' are ' || ROUND(overcharge_x, 1) || ' times the typical charge-to-allowed ratio for that code' END) AS reason
  FROM per p WHERE 4 * intense + CASE WHEN high_share >= 0.6 THEN 2 ELSE 0 END + 2 * overcharge > 0""")
print(con.execute("SELECT points, COUNT(*) FROM provider_procedure_signal GROUP BY 1 ORDER BY 1").fetchall())
print(con.execute("SELECT hcpcs, description[1:60], n_flagged, n_all, ROUND(lift,1), vector FROM procedure_trends WHERE n_all >= 200 ORDER BY lift DESC LIMIT 12").fetchall())
log("done")
