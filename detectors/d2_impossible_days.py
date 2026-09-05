#!/usr/bin/env python3
"""Detector 2: impossible days.

For every rendering (servicing) NPI and month, convert Medicaid time-based codes into implied clinician hours and test them
against physical and regulatory limits. Three independent estimates of the money-to-time conversion are kept side by side:

  hours_lb    lines-based lower bound: every claim line is at least one unit, so lines x minutes_per_unit is a floor that needs no
              rate at all. If hours_lb/day > 24 the month is impossible under any rate assumption.
  hours_pt    point estimate: paid / rate_pt x minutes_per_unit, where rate_pt is the per-unit price estimated from the data
              (or the Minnesota published rate where one exists), chosen by validation against Minnesota's published fee schedule.
  hours_cons  conservative: paid / rate_cons, rate_cons = the highest plausible unit price (max of the estimators and published
              variants), so hours_cons <= hours_pt. "Impossible" requires hours_cons/day > 24 (or hours_lb).

Rate estimators per (state, code, year), from NPI-code-month cells:
  T-MSIS suppresses cells under 12 lines or 12 patients, so paid/lines is an average over 12+ lines and sits at or above the unit price.
  r_p05_trim  5th percentile of paid/lines after dropping stray partial-payment cells (an upper bound on the unit price for HCBS codes)
  r_p50       median of paid/lines, used for Medicare-covered session codes where crossover lines pay only coinsurance
Group codes divide clinician time by the assumed participant count in timecodes.group_divisor.
"""
import argparse, json, os, sys, time, duckdb, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "detectors")
from _methods import write_section, md_table
ap = argparse.ArgumentParser(); ap.add_argument("--skip-implied", action="store_true"); a = ap.parse_args()
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
con.execute("SET memory_limit='9GB'"); con.execute("SET threads=8"); con.execute("SET temp_directory='data/tmp_duckdb'"); con.execute("SET preserve_insertion_order=false")
def run(name, sql):
    t = time.time(); con.execute(sql); n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]; print(f"ok {name:<22} {n:>12,} rows {time.time()-t:6.1f}s", flush=True)
def q(sql): return con.execute(sql).fetchall()

# ---------------- 1. rate estimation ----------------
# T-MSIS suppresses every NPI-code-month cell with fewer than 12 claim lines or 12 patients (minimum observed: 12), so no cell is a single
# line and paid/lines is an average over 12+ lines. Because paid_line = units_line x rate under full payment, paid/lines = rate x mean
# units per line >= rate: the lower envelope of paid/lines across cells is an upper bound on the unit price, and hours computed with it are
# lower bounds. Codes Medicare also covers (E/M, psychotherapy, psych testing, PT/OT, speech) carry crossover lines where Medicaid pays
# only coinsurance, which breaks the bound from below; for those the median is used (session codes bill one unit per line).
CROSSOVER = "('em_office','em_hospital','em_nursing_facility','em_home','prolonged','psychotherapy','psych_testing','health_behavior','pt_ot','speech','counseling','telehealth','nutrition','acupuncture')"
run("d2_rate_base", f"""
CREATE OR REPLACE TABLE d2_rate_base AS
WITH cells AS (
  SELECT ps.state, s.hcpcs, substr(s.month,1,4) AS year, s.paid / s.lines AS ppl, t.family
  FROM spend s JOIN provider_state ps ON ps.npi = s.billing_npi JOIN timecodes t ON t.hcpcs = s.hcpcs AND t.minutes_per_unit IS NOT NULL
  WHERE s.lines > 0 AND s.paid > 0),
med AS (SELECT state, hcpcs, year, median(ppl) AS p50 FROM cells GROUP BY 1,2,3)
SELECT c.state, c.hcpcs, c.year, c.family IN {CROSSOVER} AS crossover, COUNT(*) AS n_cells,
       quantile_cont(c.ppl, 0.05) AS r_p05,
       quantile_cont(c.ppl, 0.05) FILTER (WHERE c.ppl >= 0.2 * m.p50) AS r_p05_trim,   -- drops stray partial-payment cells
       quantile_cont(c.ppl, 0.25) AS r_p25, m.p50 AS r_p50, quantile_cont(c.ppl, 0.75) AS r_p75
FROM cells c JOIN med m USING (state, hcpcs, year)
GROUP BY 1,2,3,4,m.p50 HAVING COUNT(*) >= 30""")

# Minnesota published rates: point = version matched to the service year (2022 file for 2018-2023, 2026 file for 2024), conservative = highest
# non-supervision variant across versions. Supervision (UA) and remote/telehealth modifiers are excluded from the base rate.
run("d2_mn_published", """
CREATE OR REPLACE TABLE d2_mn_published AS
WITH r AS (SELECT hcpcs, COALESCE(modifiers, '') AS modifiers, program, rate, version, unit_minutes FROM mn_rates WHERE rate > 0 AND COALESCE(modifiers, '') NOT LIKE '%UA%'),
     base AS (SELECT hcpcs, version, min(rate) FILTER (WHERE modifiers = '' OR modifiers = 'UC' OR modifiers = 'UB' OR modifiers = 'U9') AS base_rate, max(rate) AS max_rate, min(rate) AS min_rate, COUNT(*) AS n_variants
              FROM r GROUP BY 1,2)
SELECT hcpcs, version, COALESCE(base_rate, min_rate) AS base_rate, max_rate, min_rate, n_variants FROM base""")

run("d2_rate", """
CREATE OR REPLACE TABLE d2_rate AS
WITH mn AS (
  SELECT b.state, b.hcpcs, b.year,
         (SELECT base_rate FROM d2_mn_published p WHERE p.hcpcs = b.hcpcs AND p.version = CASE WHEN b.year >= '2024' THEN '2026-04' ELSE '2022-01' END LIMIT 1) AS mn_pt_v,
         (SELECT base_rate FROM d2_mn_published p WHERE p.hcpcs = b.hcpcs ORDER BY version DESC LIMIT 1) AS mn_pt_any,
         (SELECT MAX(max_rate) FROM d2_mn_published p WHERE p.hcpcs = b.hcpcs) AS mn_max
  FROM d2_rate_base b WHERE b.state = 'MN')
SELECT b.*, COALESCE(mn.mn_pt_v, mn.mn_pt_any) AS mn_published, mn.mn_max AS mn_published_max,
       CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END AS rate_est,
       NULLIF(GREATEST(COALESCE(mn.mn_max, CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END), 0), 0) AS rate_pt_raw,
       CASE WHEN COALESCE(mn.mn_max, CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END) >= 1.0 THEN COALESCE(mn.mn_max, CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END) END AS rate_pt,
       CASE WHEN COALESCE(mn.mn_pt_v, mn.mn_pt_any) IS NOT NULL THEN 'published_MN' WHEN COALESCE(CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END, 0) < 1.0 THEN 'no_rate_bundled_or_zero_paid' WHEN b.crossover THEN 'p50_per_line' ELSE 'p05_per_line_trimmed' END AS rate_source,
       -- conservative unit price: 1.5x the point rate (and never below the published maximum variant), so conservative hours are at most two thirds of the point hours
       CASE WHEN COALESCE(mn.mn_max, CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END) >= 1.0 THEN 1.5 * COALESCE(mn.mn_max, CASE WHEN b.crossover THEN b.r_p50 ELSE COALESCE(b.r_p05_trim, b.r_p05) END) END AS rate_cons
FROM d2_rate_base b LEFT JOIN mn USING (state, hcpcs, year)""")

# validation: the data-driven estimators against Minnesota's published base rates (year-matched). Expect estimates at or above the published
# rate (paid/lines >= rate); the ratio tells how many units an average line carries.
run("d2_rate_validation", """
CREATE OR REPLACE TABLE d2_rate_validation AS
SELECT r.hcpcs, r.year, r.n_cells, r.crossover, r.mn_published AS published, r.mn_published_max AS published_max,
       ROUND(r.r_p05, 2) AS p05, ROUND(r.r_p05_trim, 2) AS p05_trim, ROUND(r.r_p25, 2) AS p25, ROUND(r.r_p50, 2) AS p50,
       ROUND(100.0 * (r.r_p05 - r.mn_published) / r.mn_published, 1) AS err_p05_pct,
       ROUND(100.0 * (r.r_p05_trim - r.mn_published) / r.mn_published, 1) AS err_p05_trim_pct,
       ROUND(100.0 * (r.r_p50 - r.mn_published) / r.mn_published, 1) AS err_p50_pct,
       ROUND(r.r_p05_trim / r.mn_published, 2) AS units_per_line_at_p05, ROUND(r.r_p50 / r.mn_published, 2) AS units_per_line_at_p50,
       (r.rate_est >= 0.9 * r.mn_published) AS estimate_is_upper_bound
FROM d2_rate r WHERE r.state = 'MN' AND r.mn_published IS NOT NULL ORDER BY 1, 2""")
val = q("""SELECT 'p05', ROUND(median(err_p05_pct),1), ROUND(median(abs(err_p05_pct)),1), COUNT(*) FROM d2_rate_validation
           UNION ALL SELECT 'p05 trimmed', ROUND(median(err_p05_trim_pct),1), ROUND(median(abs(err_p05_trim_pct)),1), COUNT(*) FROM d2_rate_validation
           UNION ALL SELECT 'p50', ROUND(median(err_p50_pct),1), ROUND(median(abs(err_p50_pct)),1), COUNT(*) FROM d2_rate_validation
           UNION ALL SELECT 'chosen estimator is >= 0.9 x published', NULL, NULL, COUNT(*) FILTER (WHERE estimate_is_upper_bound) FROM d2_rate_validation""")
print("MN validation (median signed error %, median |error| %, n):"); [print("  ", r) for r in val]

# ---------------- 2. implied hours per servicing NPI x billing NPI x code x month ----------------
if not a.skip_implied:
    run("d2_implied", """
CREATE OR REPLACE TABLE d2_implied AS
SELECT s.servicing_npi, s.billing_npi, ps.state, s.hcpcs, s.month, s.month_start, s.patients, s.lines, s.paid,
       t.minutes_per_unit, t.group_divisor, t.family, t.fraud_vector, t.mn_daily_cap_hours, t.personal_service,
       r.rate_pt, r.rate_cons, r.rate_source, r.rate_est,
       s.lines * t.minutes_per_unit / 60.0 / t.group_divisor AS hours_lb,
       s.paid / NULLIF(r.rate_pt, 0) * t.minutes_per_unit / 60.0 / t.group_divisor AS hours_pt,
       s.paid / NULLIF(r.rate_cons, 0) * t.minutes_per_unit / 60.0 / t.group_divisor AS hours_cons,
       s.paid / NULLIF(r.rate_pt, 0) AS units_pt,
       date_diff('day', s.month_start, s.month_start + INTERVAL 1 MONTH) AS days_in_month,
       (SELECT COUNT(*) FROM generate_series(s.month_start, s.month_start + INTERVAL 1 MONTH - INTERVAL 1 DAY, INTERVAL 1 DAY) g(d) WHERE dayofweek(g.d) BETWEEN 1 AND 5) AS workdays_in_month
FROM spend s
JOIN provider_state ps ON ps.npi = s.billing_npi
JOIN timecodes t ON t.hcpcs = s.hcpcs AND t.minutes_per_unit IS NOT NULL
JOIN d2_rate r ON r.state = ps.state AND r.hcpcs = s.hcpcs AND r.year = substr(s.month,1,4)
WHERE s.paid > 0 AND s.lines > 0""")

# ---------------- 3. per rendering NPI and month ----------------
run("d2_npi_month", """
CREATE OR REPLACE TABLE d2_npi_month AS
SELECT i.servicing_npi, i.state, i.month, i.month_start, MAX(i.days_in_month) AS days_in_month, MAX(i.workdays_in_month) AS workdays_in_month,
       SUM(i.hours_lb) AS hours_lb, SUM(i.hours_pt) AS hours_pt, SUM(i.hours_cons) AS hours_cons,
       COALESCE(SUM(i.hours_lb) FILTER (WHERE i.personal_service), 0) AS hours_lb_personal, COALESCE(SUM(i.hours_pt) FILTER (WHERE i.personal_service), 0) AS hours_pt_personal,
       COALESCE(SUM(i.hours_cons) FILTER (WHERE i.personal_service), 0) AS hours_cons_personal, COALESCE(SUM(i.paid) FILTER (WHERE i.personal_service), 0) AS paid_personal,
       SUM(i.paid) AS paid, SUM(i.lines) AS lines, MAX(i.patients) AS max_patients_one_code, SUM(i.patients) AS patients_sum_codes,
       COUNT(DISTINCT i.billing_npi) AS n_billing_orgs, COUNT(DISTINCT i.hcpcs) AS n_codes,
       bool_or(i.rate_source = 'published_MN') AS any_published_rate, bool_or(i.fraud_vector = 'HIGH') AS any_high_vector,
       -- Minnesota per-patient daily caps: the most hours a provider could bill in the month if every patient got the cap every day
       SUM(CASE WHEN i.state = 'MN' AND i.mn_daily_cap_hours IS NOT NULL THEN i.hours_cons END) AS mn_capped_hours_cons,
       SUM(CASE WHEN i.state = 'MN' AND i.mn_daily_cap_hours IS NOT NULL THEN i.mn_daily_cap_hours * i.patients * i.days_in_month END) AS mn_cap_allowance_hours,
       SUM(i.hours_lb) / MAX(i.days_in_month) AS hours_lb_per_day, SUM(i.hours_pt) / MAX(i.days_in_month) AS hours_pt_per_day, SUM(i.hours_cons) / MAX(i.days_in_month) AS hours_cons_per_day
FROM d2_implied i GROUP BY 1,2,3,4""")

run("d2_npi_month_x", """
CREATE OR REPLACE TABLE d2_npi_month_x AS
SELECT m.*, n.entity_type, COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))) AS name, n.city, n.state AS nppes_state, n.taxonomy, n.deact_date,
       m.hours_lb_personal / m.days_in_month AS hours_lb_personal_per_day, m.hours_pt_personal / m.days_in_month AS hours_pt_personal_per_day, m.hours_cons_personal / m.days_in_month AS hours_cons_personal_per_day,
       m.hours_cons_personal / m.workdays_in_month AS hours_cons_personal_per_workday, m.hours_lb_personal / m.workdays_in_month AS hours_lb_personal_per_workday,
       CASE WHEN n.entity_type = '1' THEN m.hours_cons_personal / m.days_in_month ELSE m.hours_cons / NULLIF(m.patients_sum_codes, 0) / m.days_in_month END AS test_hours_per_day,
       CASE WHEN n.entity_type = '1' THEN 'per_clinician_calendar_day_personal_services' ELSE 'per_patient_calendar_day' END AS test_basis,
       -- individuals are tested on personal-service codes only (psychotherapy, E/M, evaluations): technician, aide and HCBS codes are
       -- billed under a supervising NPI by design, so their volume under one individual is reported as UMBRELLA_VOLUME, not impossibility
       CASE WHEN n.entity_type = '1' AND m.hours_lb_personal / m.days_in_month > 24 THEN 'IMPOSSIBLE_BY_LINE_COUNT'
            WHEN n.entity_type = '1' AND m.hours_cons_personal / m.days_in_month > 24 THEN 'IMPOSSIBLE_CONSERVATIVE_RATE'
            WHEN m.hours_cons / NULLIF(m.patients_sum_codes, 0) / m.days_in_month > 24 THEN 'IMPOSSIBLE_PER_PATIENT'
            WHEN m.mn_cap_allowance_hours IS NOT NULL AND m.mn_capped_hours_cons > m.mn_cap_allowance_hours THEN 'EXCEEDS_MN_DAILY_CAP'
            WHEN n.entity_type = '1' AND m.hours_cons_personal / m.days_in_month > 16 THEN 'IMPLAUSIBLE_OVER_16H'
            WHEN n.entity_type = '1' AND m.hours_lb_per_day > 24 THEN 'UMBRELLA_VOLUME'
            WHEN n.entity_type = '1' AND m.hours_pt_personal / m.days_in_month > 12 THEN 'ELEVATED_OVER_12H' END AS label
FROM d2_npi_month m LEFT JOIN nppes n ON n.npi = m.servicing_npi""")

# robust z-scores of monthly point-estimate hours within (state, taxonomy) for individual clinicians, falling back to state when the group is small
run("d2_baseline", """
CREATE OR REPLACE TABLE d2_baseline AS
WITH ind AS (SELECT state, taxonomy, servicing_npi, hours_pt FROM d2_npi_month_x WHERE entity_type = '1' AND hours_pt IS NOT NULL),
     gm AS (SELECT state, taxonomy, COUNT(DISTINCT servicing_npi) AS n_npi, median(hours_pt) AS med FROM ind GROUP BY 1,2 HAVING COUNT(DISTINCT servicing_npi) >= 200),
     g  AS (SELECT i.state, i.taxonomy, MAX(m.n_npi) AS n_npi, MAX(m.med) AS med, median(abs(i.hours_pt - m.med)) AS mad FROM ind i JOIN gm m USING (state, taxonomy) GROUP BY 1,2),
     sm AS (SELECT state, COUNT(DISTINCT servicing_npi) AS n_npi, median(hours_pt) AS med FROM ind GROUP BY 1),
     s  AS (SELECT i.state, MAX(m.n_npi) AS n_npi, MAX(m.med) AS med, median(abs(i.hours_pt - m.med)) AS mad FROM ind i JOIN sm m USING (state) GROUP BY 1)
SELECT state, taxonomy, n_npi, med, mad, 'state_taxonomy' AS level FROM g
UNION ALL SELECT state, NULL, n_npi, med, mad, 'state' FROM s""")

run("d2_scored", """
CREATE OR REPLACE TABLE d2_scored AS
SELECT x.*, COALESCE(bt.level, bs.level) AS baseline_level, COALESCE(bt.med, bs.med) AS baseline_median, COALESCE(bt.mad, bs.mad) AS baseline_mad,
       0.6745 * (x.hours_pt - COALESCE(bt.med, bs.med)) / NULLIF(COALESCE(bt.mad, bs.mad), 0) AS robust_z
FROM d2_npi_month_x x
LEFT JOIN d2_baseline bt ON bt.level = 'state_taxonomy' AND bt.state = x.state AND bt.taxonomy = x.taxonomy
LEFT JOIN d2_baseline bs ON bs.level = 'state' AND bs.state = x.state""")
run("d2_scored_codes", """
CREATE OR REPLACE TABLE d2_scored_codes AS
SELECT i.servicing_npi, i.month, list(DISTINCT i.hcpcs ORDER BY i.hcpcs) AS codes, string_agg(DISTINCT i.rate_source, ',') AS rate_sources
FROM d2_implied i JOIN (SELECT DISTINCT servicing_npi, month FROM d2_scored WHERE label IS NOT NULL) f USING (servicing_npi, month) GROUP BY 1,2""")
con.execute("""CREATE OR REPLACE TABLE d2_scored AS
SELECT s.*, c.codes, c.rate_sources FROM d2_scored s LEFT JOIN d2_scored_codes c USING (servicing_npi, month)""")

# ---------------- 4. per rendering NPI: ranking ----------------
run("d2_top", """
CREATE OR REPLACE TABLE d2_top AS
WITH yr AS (SELECT servicing_npi, substr(month,1,4) AS year, SUM(paid) AS paid, MAX(patients_sum_codes) AS patients FROM d2_npi_month GROUP BY 1,2),
     growth AS (SELECT servicing_npi, MAX(CASE WHEN year='2022' THEN paid END) AS paid_2022, MAX(CASE WHEN year='2024' THEN paid END) AS paid_2024,
                       MAX(CASE WHEN year='2022' THEN patients END) AS patients_2022, MAX(CASE WHEN year='2024' THEN patients END) AS patients_2024 FROM yr GROUP BY 1)
SELECT s.servicing_npi, s.state, s.entity_type, s.name, s.city, s.taxonomy, s.test_basis,
       COUNT(*) AS months_observed,
       COUNT(*) FILTER (WHERE label = 'IMPOSSIBLE_BY_LINE_COUNT') AS months_impossible_by_lines,
       COUNT(*) FILTER (WHERE label IN ('IMPOSSIBLE_BY_LINE_COUNT','IMPOSSIBLE_CONSERVATIVE_RATE','IMPOSSIBLE_PER_PATIENT')) AS months_impossible,
       COUNT(*) FILTER (WHERE label = 'EXCEEDS_MN_DAILY_CAP') AS months_over_mn_cap,
       COUNT(*) FILTER (WHERE label IN ('IMPLAUSIBLE_OVER_16H')) AS months_implausible,
       COUNT(*) FILTER (WHERE label = 'UMBRELLA_VOLUME') AS months_umbrella,
       COUNT(*) FILTER (WHERE label IS NOT NULL) AS months_flagged,
       MAX(test_hours_per_day) AS peak_hours_per_day, MAX(hours_lb_per_day) AS peak_hours_lb_per_day, MAX(hours_pt_per_day) AS peak_hours_pt_per_day,
       MAX(robust_z) AS peak_robust_z, MAX(n_billing_orgs) AS max_billing_orgs, MAX(patients_sum_codes) AS max_patients,
       SUM(paid) AS paid_total, SUM(paid) FILTER (WHERE label IS NOT NULL) AS paid_flagged_months,
       MIN(month) AS first_month, MAX(month) AS last_month, bool_or(any_published_rate) AS any_published_rate,
       g.paid_2022, g.paid_2024, g.paid_2024 / NULLIF(g.paid_2022, 0) AS growth_paid_24_22, g.patients_2024 / NULLIF(g.patients_2022, 0) AS growth_patients_24_22,
       -- score: physical impossibility dominates, then MN cap breaches, then statistical outliers and concurrency
       3.0 * LEAST(COUNT(*) FILTER (WHERE label IN ('IMPOSSIBLE_BY_LINE_COUNT','IMPOSSIBLE_CONSERVATIVE_RATE','IMPOSSIBLE_PER_PATIENT')), 12) / 12.0
       + 1.5 * LEAST(COUNT(*) FILTER (WHERE label = 'EXCEEDS_MN_DAILY_CAP'), 12) / 12.0
       + 1.0 * LEAST(COUNT(*) FILTER (WHERE label = 'IMPLAUSIBLE_OVER_16H'), 12) / 12.0
       + 0.5 * LEAST(GREATEST(MAX(robust_z), 0), 20) / 20.0
       + 0.3 * LEAST(COUNT(*) FILTER (WHERE label = 'UMBRELLA_VOLUME'), 12) / 12.0
       + 1.5 * CASE WHEN MAX(n_billing_orgs) FILTER (WHERE label LIKE 'IMPOSSIBLE%') >= 3 THEN 1 ELSE 0 END + 0.5 * CASE WHEN MAX(n_billing_orgs) FILTER (WHERE label LIKE 'IMPOSSIBLE%') >= 5 THEN 1 ELSE 0 END
       + 0.5 * CASE WHEN g.paid_2024 / NULLIF(g.paid_2022, 0) >= 4 AND g.paid_2024 >= 250000 THEN 1 ELSE 0 END
       + 0.5 * LOG10(SUM(paid) + 1) / 8.0 AS score
FROM d2_scored s LEFT JOIN growth g USING (servicing_npi)
GROUP BY s.servicing_npi, s.state, s.entity_type, s.name, s.city, s.taxonomy, s.test_basis, g.paid_2022, g.paid_2024, g.patients_2022, g.patients_2024""")

# ---------------- 4b. growth and concentration indicator (billing NPI level) ----------------
# Medicaid-only HCBS billers (housing stabilization, EIDBI, personal care) never appear in CMS enrollment files, so the network detector cannot
# see them, and services billed under the agency NPI are tested per patient, not per clinician. This indicator ranks billing NPIs by how
# new, how concentrated in a single high-vector code, and how intense per patient they are, against the state and code distribution.
run("d2_growth", """
CREATE OR REPLACE TABLE d2_growth AS
WITH by_code AS (
  SELECT s.billing_npi, ps.state, substr(s.month,1,4) AS year, s.hcpcs, t.fraud_vector, SUM(s.paid) AS paid, SUM(s.patients) AS patient_months, MAX(s.patients) AS max_patients, COUNT(*) AS months
  FROM spend s JOIN provider_state ps ON ps.npi = s.billing_npi JOIN timecodes t USING (hcpcs) WHERE s.paid > 0 GROUP BY 1,2,3,4,5),
tot AS (SELECT billing_npi, state, year, SUM(paid) AS paid_year, SUM(patient_months) AS patient_months_year FROM by_code GROUP BY 1,2,3),
dom AS (SELECT billing_npi, state, year, hcpcs AS dominant_code, fraud_vector AS dominant_vector, paid AS dominant_paid, patient_months AS dominant_patient_months
        FROM by_code QUALIFY ROW_NUMBER() OVER (PARTITION BY billing_npi, year ORDER BY paid DESC) = 1),
base AS (
  SELECT t.billing_npi, t.state, t.year, t.paid_year, t.patient_months_year, d.dominant_code, d.dominant_vector, d.dominant_paid / t.paid_year AS concentration,
         d.dominant_paid / NULLIF(d.dominant_patient_months, 0) AS dollars_per_patient_month, n.enum_date, n.entity_type, COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))) AS name,
         LAG(t.paid_year) OVER (PARTITION BY t.billing_npi ORDER BY t.year) AS paid_prev_year
  FROM tot t JOIN dom d USING (billing_npi, state, year) LEFT JOIN nppes n ON n.npi = t.billing_npi),
ref AS (   -- state x dominant code x year distribution of dollars per patient-month (billers with at least 12 patient-months)
  SELECT state, dominant_code, year, median(dollars_per_patient_month) AS med, median(abs(dollars_per_patient_month - (SELECT median(b2.dollars_per_patient_month) FROM base b2 WHERE b2.state = b.state AND b2.dominant_code = b.dominant_code AND b2.year = b.year AND b2.patient_months_year >= 12))) AS mad, COUNT(*) AS n
  FROM base b WHERE patient_months_year >= 12 GROUP BY 1,2,3 HAVING COUNT(*) >= 20)
SELECT b.*, r.med AS ref_median, r.mad AS ref_mad, r.n AS ref_n,
       CASE WHEN r.mad > 0 THEN 0.6745 * (b.dollars_per_patient_month - r.med) / r.mad END AS intensity_z,
       CASE WHEN b.paid_prev_year > 0 THEN b.paid_year / b.paid_prev_year END AS growth_yoy,
       (b.enum_date >= CAST(b.year || '-01-01' AS DATE) - INTERVAL 3 YEAR) AS new_npi
FROM base b LEFT JOIN ref r ON r.state = b.state AND r.dominant_code = b.dominant_code AND r.year = b.year""")
run("d2_growth_flags", """
CREATE OR REPLACE TABLE d2_growth_flags AS
SELECT *, PERCENT_RANK() OVER (PARTITION BY state, dominant_code, year ORDER BY dollars_per_patient_month) AS intensity_pct,
       -- informational label: new billing NPI, at least $500k in the year, 80%+ of dollars in one high-vector code, and either a first full year at that size or 3x growth, and intensity in the top decile of its state and code
       CASE WHEN new_npi AND paid_year >= 500000 AND dominant_vector = 'HIGH' AND concentration >= 0.8 AND (paid_prev_year IS NULL OR growth_yoy >= 3)
                 AND PERCENT_RANK() OVER (PARTITION BY state, dominant_code, year ORDER BY dollars_per_patient_month) >= 0.9 THEN 'GROWTH_ANOMALY' END AS label
FROM d2_growth WHERE patient_months_year >= 12""")
print("growth anomalies:", q("SELECT year, COUNT(*) FROM d2_growth_flags WHERE label IS NOT NULL GROUP BY 1 ORDER BY 1"))

# ---------------- 5. flags for the app ----------------
con.execute("""CREATE TABLE IF NOT EXISTS flags (id BIGINT, detector VARCHAR, npi VARCHAR, billing_npi VARCHAR, state VARCHAR, month DATE, hcpcs VARCHAR,
               metric VARCHAR, value DOUBLE, threshold DOUBLE, score DOUBLE, dollars DOUBLE, tier VARCHAR, evidence JSON, created_at TIMESTAMP)""")
con.execute("DELETE FROM flags WHERE detector = 'D2'")
con.execute("""INSERT INTO flags
SELECT CAST(hash('D2' || servicing_npi || month) >> 1 AS BIGINT), 'D2', servicing_npi, NULL, state, month_start, NULL,
       CASE WHEN label LIKE 'IMPOSSIBLE%' THEN 'implied_hours_per_day' WHEN label = 'EXCEEDS_MN_DAILY_CAP' THEN 'hours_over_mn_cap_allowance' ELSE 'implied_hours_per_day' END,
       CASE WHEN label = 'EXCEEDS_MN_DAILY_CAP' THEN mn_capped_hours_cons / NULLIF(mn_cap_allowance_hours,0) ELSE test_hours_per_day END,
       CASE WHEN label LIKE 'IMPOSSIBLE%' THEN 24 WHEN label = 'EXCEEDS_MN_DAILY_CAP' THEN 1 WHEN label = 'IMPLAUSIBLE_OVER_16H' THEN 16 WHEN label = 'UMBRELLA_VOLUME' THEN 24 ELSE 12 END,
       CASE WHEN label LIKE 'IMPOSSIBLE%' THEN 3 WHEN label = 'EXCEEDS_MN_DAILY_CAP' THEN 2 WHEN label = 'IMPLAUSIBLE_OVER_16H' THEN 1 WHEN label = 'UMBRELLA_VOLUME' THEN 0.7 ELSE 0.5 END + LEAST(GREATEST(COALESCE(robust_z,0),0),20)/20.0,
       paid, CASE WHEN label = 'EXCEEDS_MN_DAILY_CAP' THEN 'A' WHEN label = 'IMPOSSIBLE_PER_PATIENT' THEN 'A'
                  WHEN label LIKE 'IMPOSSIBLE%' AND n_billing_orgs >= 3 THEN 'A'      -- impossible personal hours rendered for 3+ unrelated billers
                  WHEN label LIKE 'IMPOSSIBLE%' THEN 'B' ELSE 'C' END,                -- single-organisation impossibility can be a supervisory umbrella
       to_json(struct_pack(label := label, test_basis := test_basis, entity_type := entity_type, name := name, city := city, taxonomy := taxonomy, days_in_month := days_in_month,
                           hours_lb := hours_lb, hours_pt := hours_pt, hours_cons := hours_cons, hours_lb_per_day := hours_lb_per_day, hours_pt_per_day := hours_pt_per_day,
                           hours_lb_personal_per_day := hours_lb_personal_per_day, hours_pt_personal_per_day := hours_pt_personal_per_day, hours_cons_personal_per_day := hours_cons_personal_per_day, paid_personal := paid_personal,
                           hours_cons_personal_per_workday := hours_cons_personal_per_workday, hours_lb_personal_per_workday := hours_lb_personal_per_workday, workdays_in_month := workdays_in_month,
                           hours_cons_per_day := hours_cons_per_day, paid := paid, lines := lines, patients := patients_sum_codes, n_billing_orgs := n_billing_orgs,
                           codes := codes, rate_sources := rate_sources, robust_z := robust_z, baseline_level := baseline_level, baseline_median := baseline_median,
                           mn_capped_hours_cons := mn_capped_hours_cons, mn_cap_allowance_hours := mn_cap_allowance_hours)),
       now()
FROM d2_scored WHERE label IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY CAST(hash('D2' || servicing_npi || month) >> 1 AS BIGINT) ORDER BY test_hours_per_day DESC NULLS LAST, paid DESC NULLS LAST) = 1""")
con.execute("""INSERT INTO flags
SELECT CAST(hash('D2G' || billing_npi || year) >> 1 AS BIGINT), 'D2', billing_npi, billing_npi, state, CAST(year || '-01-01' AS DATE), dominant_code,
       'growth_and_concentration', dollars_per_patient_month, ref_median, 0.5 + LEAST(GREATEST(COALESCE(intensity_z, 0), 0), 20) / 20.0, paid_year, 'C',
       to_json(struct_pack(label := label, name := name, entity_type := entity_type, year := year, paid_year := paid_year, paid_prev_year := paid_prev_year, growth_yoy := growth_yoy,
                           dominant_code := dominant_code, concentration := concentration, patient_months := patient_months_year, dollars_per_patient_month := dollars_per_patient_month,
                           ref_median := ref_median, intensity_z := intensity_z, intensity_pct := intensity_pct, enum_date := enum_date, new_npi := new_npi)),
       now()
FROM d2_growth_flags WHERE label IS NOT NULL
QUALIFY row_number() OVER (PARTITION BY CAST(hash('D2G' || billing_npi || year) >> 1 AS BIGINT) ORDER BY paid_year DESC NULLS LAST) = 1""")
print("D2 flags:", q("SELECT tier, COUNT(*), COUNT(DISTINCT npi) FROM flags WHERE detector='D2' GROUP BY 1"))

# ---------------- 6. summaries and methods ----------------
S = {}
S["labels"] = q("SELECT label, COUNT(*) AS npi_months, COUNT(DISTINCT servicing_npi) AS npis, ROUND(SUM(paid)/1e6,2) AS millions FROM d2_scored WHERE label IS NOT NULL GROUP BY 1 ORDER BY 2 DESC")
S["impossible_npis"] = q("""SELECT COUNT(*) FILTER (WHERE months_impossible > 0), COUNT(*) FILTER (WHERE months_impossible_by_lines > 0), COUNT(*) FILTER (WHERE months_impossible >= 3),
                            ROUND(SUM(paid_flagged_months) FILTER (WHERE months_impossible > 0)/1e6,2), COUNT(*) FILTER (WHERE months_over_mn_cap > 0),
                            COUNT(*) FILTER (WHERE months_impossible > 0 AND (max_billing_orgs >= 3 OR entity_type = '2')) FROM d2_top""")
S["tiers"] = q("SELECT tier, COUNT(*), COUNT(DISTINCT npi), ROUND(SUM(dollars)/1e6,2) FROM flags WHERE detector='D2' GROUP BY 1 ORDER BY 1")
S["denominator"] = q("""SELECT 'calendar days (used for labels)', COUNT(DISTINCT servicing_npi) FILTER (WHERE hours_cons_personal_per_day > 24), COUNT(DISTINCT servicing_npi) FILTER (WHERE hours_cons_personal_per_day > 16) FROM d2_scored WHERE entity_type='1'
                       UNION ALL SELECT 'working days (Mon to Fri)', COUNT(DISTINCT servicing_npi) FILTER (WHERE hours_cons_personal_per_workday > 24), COUNT(DISTINCT servicing_npi) FILTER (WHERE hours_cons_personal_per_workday > 16) FROM d2_scored WHERE entity_type='1'""")
S["by_state"] = q("SELECT state, COUNT(*) FILTER (WHERE months_impossible > 0) npis_impossible, ROUND(SUM(paid_flagged_months) FILTER (WHERE months_impossible > 0)/1e6,2) millions FROM d2_top GROUP BY 1 ORDER BY 2 DESC LIMIT 12")
S["national_top"] = q("""SELECT servicing_npi, name, entity_type, state, taxonomy, months_impossible, months_impossible_by_lines, months_umbrella, ROUND(peak_hours_per_day,1), ROUND(peak_hours_lb_per_day,1), max_billing_orgs, max_patients, ROUND(paid_total), ROUND(score,2)
                          FROM d2_top WHERE entity_type = '1' ORDER BY score DESC, peak_hours_per_day DESC LIMIT 30""")
S["org_top"] = q("""SELECT servicing_npi, name, state, taxonomy, months_impossible, ROUND(peak_hours_per_day,2), max_patients, ROUND(paid_total), ROUND(score,2) FROM d2_top WHERE entity_type = '2' AND months_impossible > 0 ORDER BY score DESC LIMIT 15""")
S["mn_top"] = q("""SELECT servicing_npi, name, entity_type, taxonomy, months_impossible, months_over_mn_cap, months_implausible, ROUND(peak_hours_per_day,1), ROUND(peak_hours_lb_per_day,1), max_billing_orgs, max_patients, ROUND(paid_total), ROUND(growth_paid_24_22,1), ROUND(score,2)
                   FROM d2_top WHERE state = 'MN' ORDER BY score DESC, peak_hours_per_day DESC LIMIT 30""")
S["mn_codes"] = q("""SELECT hcpcs, COUNT(DISTINCT servicing_npi) npis, ROUND(SUM(paid)/1e6,2) millions, ROUND(SUM(hours_pt)/1e6,2) million_hours_pt, string_agg(DISTINCT rate_source, ',') FROM d2_implied WHERE state='MN' AND hcpcs IN ('97151','97152','97153','97154','97155','97156','97157','97158','0362T','0373T','H2014','H2015','T1019') GROUP BY 1 ORDER BY 3 DESC""")
S["validation"] = val
S["validation_rows"] = q("SELECT hcpcs, year, n_cells, crossover, published, published_max, p05, p05_trim, p50, err_p05_trim_pct, err_p50_pct, units_per_line_at_p05, units_per_line_at_p50 FROM d2_rate_validation ORDER BY 1,2")
S["rate_sources"] = q("SELECT rate_source, COUNT(*) FROM d2_rate GROUP BY 1 ORDER BY 2 DESC")
for k, v in S.items(): print(f"\n== {k}"); [print("  ", r) for r in v[:32]]
json.dump({k: [[str(x) for x in r] for r in v] for k, v in S.items()}, open("demo/cache/d2_summary.json", "w"), indent=1)
imp = S["impossible_npis"][0]
body = f"""
**Conversion.** For each rendering NPI, billing NPI, HCPCS code and service month in the T-MSIS spending file, implied clinician hours are computed three ways: a rate-free lower bound (each claim line is at least one unit, so `lines x minutes_per_unit`), a point estimate (`paid / rate_pt x minutes_per_unit`), and a conservative estimate (`paid / rate_cons` with `rate_cons = 1.5 x rate_pt`). Because the data-driven rate is itself an upper bound on the unit price, both dollar-based figures understate hours; the label `IMPOSSIBLE` therefore means impossible under every assumption the method makes. Group codes are divided by the assumed participant count. Minutes per unit come from `ingest/02_timecodes.csv` (CPT/HCPCS unit definitions; untimed session codes use the low end of the CPT time range).

**Unit price estimation.** T-MSIS suppresses every NPI-code-month cell with fewer than 12 claim lines or 12 patients (the smallest cell in the file has 12 of each), so no single-line payments exist and `paid / lines` is an average over 12 or more lines. Under full payment a line pays `units x rate`, so `paid / lines = rate x mean units per line >= rate`: the lower envelope of `paid / lines` across a state's cells is an upper bound on the unit price, and hours computed from it are lower bounds. The estimator is the 5th percentile of `paid / lines` per state, code and year after dropping cells below 20 percent of the median (stray partial payments); for codes Medicare also covers, where crossover lines pay only coinsurance, the median is used instead (session codes bill one unit per line). Where Minnesota publishes the rate (DHS-3945 January 2022 and April 2026, EIDBI billing grid January 2026, MH procedure grid) the highest published non-supervision variant of the code replaces the estimate (several programs share a code at different prices, and the highest keeps hours conservative). The conservative rate is 1.5 times the point rate.

**Validation against Minnesota's published rates** (signed error is positive when the estimate sits above the published unit price, which is the expected direction; `units per line` is the estimate divided by the published rate):

{md_table(S["validation"], ["estimator","median signed error %","median |error| %","code-years"])}

{md_table(S["validation_rows"], ["code","year","cells","crossover","published","published max","p05","p05 trimmed","p50","err p05 trimmed %","err p50 %","units/line at p05","units/line at p50"])}

Rate sources used nationally: {", ".join(f"{r[0]} {r[1]:,}" for r in S["rate_sources"])}.

**Tests.** Every code carries a `personal_service` attribute: psychotherapy, E/M, prolonged services, evaluations, professional psychological testing, health-behavior, counseling, telehealth, nutrition and acupuncture must be delivered by the rendering clinician; technician, aide, personal-care, habilitation and other HCBS codes are billed under a supervising or agency NPI by design. Individual NPIs (NPPES entity type 1) are tested on personal-service hours only: `IMPOSSIBLE_BY_LINE_COUNT` when even the rate-free lower bound exceeds 24 hours per calendar day; `IMPOSSIBLE_CONSERVATIVE_RATE` when the conservative estimate exceeds 24; `IMPLAUSIBLE_OVER_16H`; `ELEVATED_OVER_12H`. Supervision-billable volume above 24 hours per day under one individual NPI is reported as `UMBRELLA_VOLUME` (tier B): it can be a legitimate agency structure or a ghost clinician, and only records can tell. Any NPI: `IMPOSSIBLE_PER_PATIENT` when conservative hours per patient exceed 24 per calendar day. Minnesota: `EXCEEDS_MN_DAILY_CAP` when conservative hours on capped EIDBI codes exceed `cap x patients x days`, i.e. more than every patient receiving the state's own daily maximum every day of the month (97153 and 0373T 8 h, 97155 6 h, 97154 4.5 h, 97156 4 h, 97151 8 h). Robust z-scores (median/MAD, 0.6745 scaling) are computed within state and NPPES taxonomy (state-only when fewer than 200 NPIs) and feed the ranking, never a label on their own.

**Results.** {imp[0]:,} rendering NPIs have at least one impossible month ({imp[1]:,} impossible by line count alone, {imp[2]:,} with three or more impossible months), with ${imp[3]:,.2f}M paid in those months; {imp[5]:,} of them are tier A (an individual whose impossible personal-service hours were billed by three or more different organisations in the same month, or an organisation with more than 24 hours per patient per day); {imp[4]:,} Minnesota providers exceed the state's own daily cap allowance. The most common drivers are office E/M codes (99213, 99214) and psychotherapy (90837, 90791), which several states let clinics bill under a supervising physician's or psychologist's NPI; a single-organisation impossibility is therefore tier B and reads as "verify the state's supervisory billing rule and pull records", not as a finding.

{md_table(S["tiers"], ["tier","NPI-months","NPIs","$M"])}

**Denominator sensitivity.** Labels divide monthly hours by calendar days, the strictest physical bound. Dividing by Monday-to-Friday working days instead moves the counts as follows (individual NPIs, conservative personal-service hours):

{md_table(S["denominator"], ["denominator","NPIs over 24 h/day","NPIs over 16 h/day"])}

**Growth and concentration indicator.** Medicaid-only home and community-based billers (housing stabilization, EIDBI, personal care) never appear in the CMS enrollment files, so the network detector cannot see them, and services billed under the agency NPI are tested per patient. For every billing NPI and year the indicator records the dominant code, the share of dollars in it, dollars per patient-month, the year-over-year growth and whether the NPI was enumerated within three years. `GROWTH_ANOMALY` (tier C, informational) marks new NPIs with at least $500k in the year, 80 percent or more of dollars in one high-vector code, a first year at that size or three-fold growth, and dollars per patient-month in the top decile of their state and code. It is a queue for records review; many new providers grow quickly for legitimate reasons.

**Convention caveat.** In several states the T-MSIS rendering NPI is the supervising clinician or the group by convention, and telehealth and locum tenens arrangements can concentrate volume under one NPI legitimately. Every label here is a screening indicator to be checked against the state's supervisory-billing rules and the provider's records; none is a finding.

{md_table(S["labels"], ["label","NPI-months","NPIs","$M in flagged months"])}

{md_table(S["by_state"], ["state","NPIs with impossible months","$M"])}

**Minnesota EIDBI, CTSS, HSS and PCA codes** (rendering NPIs, dollars, implied hours, rate source):

{md_table(S["mn_codes"], ["code","NPIs","$M","implied hours (M)","rate source"])}

Tables: `d2_rate`, `d2_rate_validation`, `d2_implied`, `d2_npi_month`, `d2_scored`, `d2_top`; app rows in `flags` (detector D2). Code: `detectors/d2_impossible_days.py`.
"""
write_section("Detector 2: impossible days", body)
con.execute("CHECKPOINT"); con.close(); print("done")
