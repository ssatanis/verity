#!/usr/bin/env python3
"""Detector 3: dead in Medicare, alive in Medicaid.

Sources of "should not be paid" events, each with an event date and (where the source gives one) a window end:
  MEDICARE_REVOKED   CMS Revoked Providers and Suppliers (42 CFR 424.535 grounds; tier A = integrity grounds, tier B = administrative)
  OIG_LEIE           OIG List of Excluded Individuals/Entities (payment prohibition, 42 CFR 1001.1901); rows with a state waiver are dropped
  STATE_EXCL_xx      California S&I list, New York OMIG list, Texas OIG list (with NPI)
  SAM_<agency>       SAM.gov exclusions from agencies other than HHS that carry an NPI (informational, tier B)
  NPPES_DEACTIVATED  NPI deactivated in NPPES and not reactivated (tier B)
  TMSIS_DECEASED     Medicaid enrollment terminated with status 80 "provider deceased" (tier A)
  TMSIS_TERM_xx      Medicaid termination for cause in one state (used only for the cross-state test)
"Paid after" = T-MSIS Medicaid provider spending in service months strictly after the event month and before the window end,
counted once per NPI-month whether the NPI was the billing or the servicing provider.
"""
import argparse, json, os, time, duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
ap = argparse.ArgumentParser(); ap.add_argument("--rebuild-spend", action="store_true"); a = ap.parse_args()
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
con.execute("SET memory_limit='9GB'"); con.execute("SET threads=8"); con.execute("SET temp_directory='data/tmp_duckdb'")
def run(name, sql):
    t = time.time(); con.execute(sql); n = con.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]; print(f"ok {name:<20} {n:>12,} rows {time.time()-t:6.1f}s", flush=True)

PARQ = "data/medicaid_tmsis/medicaid-provider-spending.parquet"
have = con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name='spend_any_month'").fetchone()[0]
if a.rebuild_spend or not have:
    # rows where billing == servicing sit in both monthly role tables; subtract them once so an NPI-month is never double counted
    run("spend_self_month", f"""
CREATE OR REPLACE TABLE spend_self_month AS
SELECT BILLING_PROVIDER_NPI_NUM AS npi, CLAIM_FROM_MONTH AS month, SUM(TOTAL_PAID) AS paid, SUM(TOTAL_CLAIM_LINES) AS lines
FROM read_parquet('{PARQ}') WHERE BILLING_PROVIDER_NPI_NUM = SERVICING_PROVIDER_NPI_NUM AND regexp_matches(BILLING_PROVIDER_NPI_NUM, '^[0-9]{{10}}$') AND TOTAL_PAID BETWEEN 0 AND 50000000
GROUP BY 1,2""")
    run("spend_any_month", """
CREATE OR REPLACE TABLE spend_any_month AS
SELECT COALESCE(b.npi, s.npi) AS npi, COALESCE(b.month, s.month) AS month, COALESCE(b.month_start, s.month_start) AS month_start,
       COALESCE(b.paid, 0) + COALESCE(s.paid, 0) - COALESCE(x.paid, 0) AS paid,
       COALESCE(b.lines, 0) + COALESCE(s.lines, 0) - COALESCE(x.lines, 0) AS lines,
       GREATEST(COALESCE(b.max_patients, 0), COALESCE(s.max_patients, 0)) AS max_patients,
       COALESCE(b.paid, 0) AS paid_as_billing, COALESCE(s.paid, 0) - COALESCE(x.paid, 0) AS paid_as_servicing,
       COALESCE(s.n_billing, 0) AS n_counterparties
FROM spend_bill_month b FULL OUTER JOIN spend_srv_month s ON s.npi = b.npi AND s.month = b.month
LEFT JOIN spend_self_month x ON x.npi = COALESCE(b.npi, s.npi) AND x.month = COALESCE(b.month, s.month)""")


# NPI check digit (Luhn over the 9-digit base with the 80840 prefix, which contributes 24 to the sum). Every NPI-bearing list is filtered by it.
con.execute("""CREATE OR REPLACE MACRO npi_luhn_ok(n) AS (
  n IS NOT NULL AND regexp_matches(n, '^[12][0-9]{9}$') AND
  CAST(n[10] AS INTEGER) = (10 - ((24
    + (CASE WHEN CAST(n[1] AS INTEGER)*2 > 9 THEN CAST(n[1] AS INTEGER)*2 - 9 ELSE CAST(n[1] AS INTEGER)*2 END) + CAST(n[2] AS INTEGER)
    + (CASE WHEN CAST(n[3] AS INTEGER)*2 > 9 THEN CAST(n[3] AS INTEGER)*2 - 9 ELSE CAST(n[3] AS INTEGER)*2 END) + CAST(n[4] AS INTEGER)
    + (CASE WHEN CAST(n[5] AS INTEGER)*2 > 9 THEN CAST(n[5] AS INTEGER)*2 - 9 ELSE CAST(n[5] AS INTEGER)*2 END) + CAST(n[6] AS INTEGER)
    + (CASE WHEN CAST(n[7] AS INTEGER)*2 > 9 THEN CAST(n[7] AS INTEGER)*2 - 9 ELSE CAST(n[7] AS INTEGER)*2 END) + CAST(n[8] AS INTEGER)
    + (CASE WHEN CAST(n[9] AS INTEGER)*2 > 9 THEN CAST(n[9] AS INTEGER)*2 - 9 ELSE CAST(n[9] AS INTEGER)*2 END)) % 10)) % 10)""")
# name agreement: any shared token of three or more letters after dropping corporate and generic words
con.execute("""CREATE OR REPLACE MACRO name_tokens(s) AS list_filter(string_split(regexp_replace(upper(COALESCE(s, '')), '[^A-Z ]', ' ', 'g'), ' '),
  x -> length(x) >= 3 AND x NOT IN ('INC','LLC','THE','AND','CORP','LTD','LLP','PLLC','DDS','GROUP','MEDICAL','HEALTH','CARE','SERVICES','SERVICE','CENTER','CLINIC','HOME','DBA','COMPANY','ASSOCIATES','PROFESSIONAL','CORPORATION'))""")
con.execute("CREATE OR REPLACE MACRO names_agree(a, b) AS list_has_any(name_tokens(a), name_tokens(b))")
ok, tot = con.execute("SELECT COUNT(*) FILTER (WHERE npi_luhn_ok(npi)), COUNT(*) FROM (SELECT npi FROM nppes USING SAMPLE 200000)").fetchone()
print(f"NPI check-digit self-test on NPPES sample: {ok}/{tot} valid ({100*ok/tot:.2f}%)")
assert ok / tot > 0.999, "check-digit macro is wrong"

TIER_A_CFR = "(2|3|4|5|7|8|10|12|13|14|18|19|20|22|23)"
TIER_A_TMSIS = "('60','62','65','66','67','70','71','72','74','75','78','81')"
ACTIVE = "('02','03','04','05','06')"
# exclusion rows without an NPI that scripts/sam_match_claude.py matched to an NPPES record by name (model, high confidence): tier B, reported separately, never in the headline
NAME_MATCH_UNION = ""
if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name = 'sam_npi_matches'").fetchone()[0]:
    NAME_MATCH_UNION = """UNION ALL
  SELECT CAST(m.npi AS VARCHAR), CAST(m.source AS VARCHAR) || '_NAME', CAST(m.event_dt AS DATE), NULL::DATE, 'name-matched by model at high confidence: ' || COALESCE(CAST(m.exclusion_type AS VARCHAR), ''), CAST(m.state AS VARCHAR), 'B',
         COALESCE(NULLIF(CAST(m.busname AS VARCHAR), ''), trim(COALESCE(CAST(m.firstname AS VARCHAR), '') || ' ' || COALESCE(CAST(m.lastname AS VARCHAR), ''))), 'name_match'
  FROM sam_npi_matches m WHERE m.same_entity AND m.confidence = 'high' AND m.event_dt IS NOT NULL AND npi_luhn_ok(m.npi)"""
run("d3_events", f"""
CREATE OR REPLACE TABLE d3_events AS
WITH latest AS (   -- latest enrollment status per NPI and state (a later active segment means the termination was resolved)
  SELECT npi, state, status_cd, start_dt FROM enroll QUALIFY ROW_NUMBER() OVER (PARTITION BY npi, state ORDER BY start_dt DESC, COALESCE(end_dt, DATE '9999-01-01') DESC) = 1),
ev AS (
  SELECT npi, 'MEDICARE_REVOKED' AS source, revoked_dt AS event_dt, reenroll_bar_dt AS window_end, revocation_rsn AS reason, state AS source_state,
         CASE WHEN regexp_matches(revocation_rsn, '\\(A\\)\\({TIER_A_CFR}\\)') THEN 'A' ELSE 'B' END AS tier,
         COALESCE(org_name, trim(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) AS source_name, provider_type_desc AS source_type
  FROM revoked WHERE npi_luhn_ok(npi) AND revoked_dt IS NOT NULL
  UNION ALL
  SELECT npi, 'OIG_LEIE', excl_dt, rein_dt, 'LEIE ' || excltype || ' (' || COALESCE(general,'') || ')', state, 'A',
         COALESCE(NULLIF(busname,''), trim(COALESCE(firstname,'') || ' ' || COALESCE(lastname,''))), specialty
  FROM leie WHERE npi_luhn_ok(npi) AND excl_dt IS NOT NULL AND waiver_dt IS NULL
  UNION ALL
  SELECT npi, 'STATE_EXCL_' || state, excl_dt, COALESCE(reinstated_dt, eligible_dt), source, state,
         CASE WHEN state = 'TX' AND reinstated_dt IS NULL AND eligible_dt IS NULL AND excl_dt < DATE '2018-01-01' THEN 'B' ELSE 'A' END,  -- Texas lists everyone ever excluded
         name, provider_type
  FROM state_exclusions WHERE npi_luhn_ok(npi) AND excl_dt IS NOT NULL
  UNION ALL
  SELECT npi, 'SAM_' || COALESCE(excluding_agency,'UNKNOWN'), active_dt, termination_dt, exclusion_type || ' / ' || COALESCE(ct_code,''), state, 'B',
         COALESCE(NULLIF(name,''), trim(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))), classification
  FROM sam WHERE npi_luhn_ok(npi) AND excluding_agency <> 'HHS' AND active_dt IS NOT NULL
  UNION ALL
  SELECT npi, 'NPPES_DEACTIVATED', deact_date, react_date, 'NPI deactivated in NPPES', state, 'B',
         COALESCE(org_name, trim(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))), taxonomy
  FROM nppes WHERE deact_date IS NOT NULL AND (react_date IS NULL OR react_date <= deact_date)
  UNION ALL
  SELECT e.npi, 'TMSIS_DECEASED', MIN(e.start_dt), NULL::DATE,
         'Medicaid enrollment terminated: provider deceased (T-MSIS status 80)' || CASE WHEN n.deact_date IS NOT NULL THEN '; NPI deactivated in NPPES ' || CAST(n.deact_date AS VARCHAR) ELSE '' END,
         e.state, CASE WHEN n.deact_date IS NOT NULL THEN 'A' ELSE 'B' END, NULL, e.prvdr_type_desc
  FROM enroll e JOIN nppes n ON n.npi = e.npi AND n.entity_type = '1'          -- individuals only: organizations cannot be deceased
  JOIN latest l ON l.npi = e.npi AND l.state = e.state AND l.status_cd = '80'   -- deceased must be the latest status in that state
  WHERE e.status_cd = '80' AND e.start_dt >= DATE '2015-01-01' GROUP BY e.npi, e.state, e.prvdr_type_desc, n.deact_date
  UNION ALL
  SELECT e.npi, 'TMSIS_TERM_' || e.status_cd, MIN(e.start_dt), NULL::DATE, e.status_desc, e.state, 'A', NULL, e.prvdr_type_desc
  FROM enroll e JOIN latest l ON l.npi = e.npi AND l.state = e.state AND l.status_cd = e.status_cd
  WHERE e.status_cd IN {TIER_A_TMSIS} GROUP BY e.npi, e.state, e.status_cd, e.status_desc, e.prvdr_type_desc
  {NAME_MATCH_UNION}
)
SELECT DISTINCT ev.npi, ev.source, ev.event_dt, ev.window_end, ev.reason, ev.source_state,
       -- a state-list NPI whose NPPES name shares no token with the list entry is downgraded: the NPI field on those lists can carry an employer's NPI
       -- any list row whose name shares no token with the NPPES record for that NPI is set aside as tier C, whatever the source:
       -- the identifier alone is not enough to name a provider in a referral
       CASE WHEN n.npi IS NOT NULL AND ev.source_name IS NOT NULL
                 AND NOT names_agree(ev.source_name, COALESCE(n.org_name, '') || ' ' || COALESCE(n.first_name, '') || ' ' || COALESCE(n.last_name, ''))
            THEN 'C' ELSE ev.tier END AS tier,
       ev.source_name, ev.source_type,
       CASE WHEN n.npi IS NULL OR ev.source_name IS NULL THEN NULL
            ELSE names_agree(ev.source_name, COALESCE(n.org_name, '') || ' ' || COALESCE(n.first_name, '') || ' ' || COALESCE(n.last_name, '')) END AS name_agrees_with_nppes,
       -- identity match tier: every event here carries the NPI itself (exact match); the tier records how far the identity could be verified
       CASE WHEN ev.source_type = 'name_match' THEN 'name_match_model_high'
            WHEN n.npi IS NULL THEN 'exact_npi_not_in_nppes'
            WHEN ev.source_name IS NULL THEN 'exact_npi_unnamed_source'
            WHEN names_agree(ev.source_name, COALESCE(n.org_name, '') || ' ' || COALESCE(n.first_name, '') || ' ' || COALESCE(n.last_name, '')) THEN 'exact_npi_name_verified'
            ELSE 'exact_npi_name_conflict' END AS id_match
FROM ev LEFT JOIN nppes n ON n.npi = ev.npi""")

run("d3_paid_after", """
CREATE OR REPLACE TABLE d3_paid_after AS
WITH after AS (
  SELECT e.npi, e.source, e.event_dt, e.window_end, e.reason, e.tier, e.source_state, e.source_name, e.source_type, e.id_match,
         COUNT(*) AS months_paid_after, MIN(s.month) AS first_month_after, MAX(s.month) AS last_month_after,
         SUM(s.paid) AS paid_after, SUM(s.paid_as_billing) AS paid_after_as_billing, SUM(s.paid_as_servicing) AS paid_after_as_servicing,
         MAX(s.max_patients) AS max_patients_after, SUM(s.lines) AS lines_after, MAX(s.n_counterparties) AS max_counterparties_after
  FROM d3_events e JOIN spend_any_month s ON s.npi = e.npi
  WHERE e.source NOT LIKE 'TMSIS_TERM_%'
    AND s.month_start >= date_trunc('month', e.event_dt) + INTERVAL 1 MONTH
    AND (e.window_end IS NULL OR s.month_start < date_trunc('month', e.window_end))
  GROUP BY ALL),
before AS (
  SELECT e.npi, e.source, e.event_dt, SUM(s.paid) AS paid_before_12m, COUNT(*) AS months_paid_before_12m
  FROM d3_events e JOIN spend_any_month s ON s.npi = e.npi
  WHERE s.month_start >= date_trunc('month', e.event_dt) - INTERVAL 12 MONTH AND s.month_start < date_trunc('month', e.event_dt)
  GROUP BY ALL)
SELECT a.*, COALESCE(b.paid_before_12m, 0) AS paid_before_12m, COALESCE(b.months_paid_before_12m, 0) AS months_paid_before_12m,
       date_diff('month', date_trunc('month', a.event_dt), CAST(a.last_month_after || '-01' AS DATE)) AS months_span_after
FROM after a LEFT JOIN before b USING (npi, source, event_dt)
-- one row per NPI, source and action date: list files can repeat an action with a different window end or spelling of the name
QUALIFY row_number() OVER (PARTITION BY a.npi, a.source, a.event_dt ORDER BY a.tier, a.paid_after DESC) = 1""")

run("d3_enrolled_after", f"""
CREATE OR REPLACE TABLE d3_enrolled_after AS
SELECT e.npi, e.source, e.event_dt, e.tier, en.state AS medicaid_state, en.status_cd, en.status_desc,
       MIN(en.start_dt) AS seg_start, MAX(COALESCE(en.end_dt, DATE '2024-12-31')) AS seg_end,
       date_diff('day', e.event_dt, MAX(COALESCE(en.end_dt, DATE '2024-12-31'))) AS days_active_after_event
FROM d3_events e JOIN enroll en ON en.npi = e.npi
WHERE e.source NOT LIKE 'TMSIS_%' AND en.status_cd IN {ACTIVE}
  AND COALESCE(en.end_dt, DATE '2024-12-31') > e.event_dt + INTERVAL 90 DAY
  AND (e.window_end IS NULL OR en.start_dt < e.window_end)
GROUP BY e.npi, e.source, e.event_dt, e.tier, en.state, en.status_cd, en.status_desc""")

STRICT_TMSIS = "('60','65','66','67','70','72','75','78','81')"
run("d3_crossstate", f"""
CREATE OR REPLACE TABLE d3_crossstate AS
WITH latest AS (SELECT npi, state, status_cd FROM enroll QUALIFY ROW_NUMBER() OVER (PARTITION BY npi, state ORDER BY start_dt DESC, COALESCE(end_dt, DATE '9999-01-01') DESC) = 1),
     bulk AS (SELECT state, status_cd, COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY state) AS share FROM enroll WHERE status_cd BETWEEN '60' AND '83' GROUP BY 1,2),
     term AS (SELECT e.npi, e.state AS term_state, e.status_cd AS term_code, e.status_desc AS term_reason, MIN(e.start_dt) AS term_dt
              FROM enroll e JOIN latest l ON l.npi = e.npi AND l.state = e.state AND l.status_cd = e.status_cd
              JOIN bulk b ON b.state = e.state AND b.status_cd = e.status_cd AND b.share <= 0.20
              WHERE e.status_cd IN {STRICT_TMSIS} AND e.start_dt >= DATE '2018-01-01' GROUP BY 1,2,3,4),
     act AS (SELECT npi, state AS active_state, MIN(start_dt) AS active_start, MAX(COALESCE(end_dt, DATE '2024-12-31')) AS active_end
             FROM enroll WHERE status_cd IN {ACTIVE} GROUP BY 1,2),
     footprint AS (SELECT npi, COUNT(DISTINCT state) AS n_states FROM enroll GROUP BY 1),
     x AS (SELECT t.*, a.active_state, a.active_start, a.active_end, n.entity_type, f.n_states,
                  COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))) AS nppes_name
           FROM term t JOIN act a ON a.npi = t.npi AND a.active_state <> t.term_state
           JOIN nppes n ON n.npi = t.npi JOIN footprint f ON f.npi = t.npi
           WHERE a.active_end > t.term_dt + INTERVAL 90 DAY AND a.active_start < DATE '2024-12-31'
             AND (n.entity_type = '1' OR f.n_states <= 3)),
     paid AS (SELECT x.npi, x.term_state, x.term_code, x.active_state, SUM(s.paid) AS paid_after_term, COUNT(*) AS months_after_term
              FROM x JOIN spend_any_month s ON s.npi = x.npi AND s.month_start >= date_trunc('month', x.term_dt) + INTERVAL 1 MONTH GROUP BY ALL),
     corr AS (SELECT npi, string_agg(DISTINCT source, ',') AS federal_sources FROM d3_events WHERE tier='A' AND source NOT LIKE 'TMSIS_%' GROUP BY 1)
SELECT x.*, COALESCE(p.paid_after_term, 0) AS paid_after_term, COALESCE(p.months_after_term, 0) AS months_after_term, c.federal_sources
FROM x LEFT JOIN paid p USING (npi, term_state, term_code, active_state) LEFT JOIN corr c USING (npi)""")

# ranked list with identity from NPPES and the Medicaid home state
run("d3_top", """
CREATE OR REPLACE TABLE d3_top AS
SELECT p.*, n.entity_type, COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))) AS nppes_name,
       n.city AS nppes_city, n.state AS nppes_state, n.taxonomy, n.deact_date AS nppes_deact_date, ps.state AS medicaid_home_state,
       (SELECT COUNT(*) FROM d3_enrolled_after ea WHERE ea.npi = p.npi AND ea.source = p.source AND ea.event_dt = p.event_dt) AS n_active_segments_after,
       CASE WHEN p.tier = 'A' THEN 2.0 ELSE 0.0 END + LOG10(p.paid_after + 1) + CASE WHEN p.months_paid_after >= 6 THEN 1.0 ELSE 0.0 END
         + CASE WHEN p.paid_before_12m > 0 THEN 0.5 ELSE 0.0 END AS score
FROM d3_paid_after p LEFT JOIN nppes n ON n.npi = p.npi LEFT JOIN provider_state ps ON ps.npi = p.npi
WHERE p.paid_after > 0""")

run("d3_npi", """
CREATE OR REPLACE TABLE d3_npi AS
WITH first_ev AS (
  SELECT npi, MIN(event_dt) AS first_event_dt, string_agg(DISTINCT source, ',') AS sources, COUNT(DISTINCT source) AS n_sources, bool_and(COALESCE(name_agrees_with_nppes, TRUE)) AS names_agree,
         CASE WHEN bool_and(id_match = 'exact_npi_name_verified') THEN 'exact_npi_name_verified' ELSE string_agg(DISTINCT id_match, ',') END AS id_match,
         CASE WHEN bool_or(window_end IS NULL) THEN NULL ELSE MAX(window_end) END AS window_end
  FROM d3_events WHERE tier = 'A' AND (source IN ('MEDICARE_REVOKED','OIG_LEIE') OR source LIKE 'STATE_EXCL_%') GROUP BY 1)
SELECT f.*, n.entity_type, COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))) AS nppes_name, n.state AS nppes_state, ps.state AS medicaid_home_state,
       COUNT(s.month) AS months_paid_after, MIN(s.month) AS first_month_after, MAX(s.month) AS last_month_after, COALESCE(SUM(s.paid), 0) AS paid_after
FROM first_ev f LEFT JOIN nppes n ON n.npi = f.npi LEFT JOIN provider_state ps ON ps.npi = f.npi
LEFT JOIN spend_any_month s ON s.npi = f.npi AND s.month_start >= date_trunc('month', f.first_event_dt) + INTERVAL 1 MONTH
     AND (f.window_end IS NULL OR s.month_start < date_trunc('month', f.window_end))
GROUP BY ALL""")

# ---- flags for the app ----
con.execute("""CREATE TABLE IF NOT EXISTS flags (id BIGINT, detector VARCHAR, npi VARCHAR, billing_npi VARCHAR, state VARCHAR, month DATE, hcpcs VARCHAR,
               metric VARCHAR, value DOUBLE, threshold DOUBLE, score DOUBLE, dollars DOUBLE, tier VARCHAR, evidence JSON, created_at TIMESTAMP)""")
con.execute("DELETE FROM flags WHERE detector = 'D3'")
con.execute("""INSERT INTO flags
SELECT CAST(hash(npi || 'D3' || source || CAST(event_dt AS VARCHAR) || COALESCE(reason, '') || COALESCE(first_month_after, '')) >> 1 AS BIGINT) AS id, 'D3', npi, NULL, COALESCE(medicaid_home_state, source_state), CAST(first_month_after || '-01' AS DATE), NULL,
       'medicaid_paid_after_' || lower(source), paid_after, 0, score, paid_after, tier,
       to_json(struct_pack(source := source, event_dt := event_dt, window_end := window_end, reason := reason, source_state := source_state, source_name := source_name,
                           source_type := source_type, nppes_name := nppes_name, entity_type := entity_type, nppes_city := nppes_city, nppes_state := nppes_state,
                           taxonomy := taxonomy, medicaid_home_state := medicaid_home_state, months_paid_after := months_paid_after, first_month_after := first_month_after,
                           last_month_after := last_month_after, paid_after := paid_after, paid_after_as_billing := paid_after_as_billing,
                           paid_after_as_servicing := paid_after_as_servicing, max_patients_after := max_patients_after, paid_before_12m := paid_before_12m,
                           n_active_segments_after := n_active_segments_after, nppes_deact_date := nppes_deact_date, id_match := id_match)),
       now()
FROM d3_top
QUALIFY row_number() OVER (PARTITION BY CAST(hash(npi || 'D3' || source || CAST(event_dt AS VARCHAR) || COALESCE(reason, '') || COALESCE(first_month_after, '')) >> 1 AS BIGINT) ORDER BY paid_after DESC) = 1""")
print("D3 flags:", con.execute("SELECT COUNT(*), COUNT(DISTINCT npi) FROM flags WHERE detector='D3'").fetchone())

# ---- summary ----
def q(sql): return con.execute(sql).fetchall()
S = {}
S["headline"] = q("""SELECT COUNT(*) AS npis_on_a_list, COUNT(*) FILTER (WHERE paid_after > 0) AS npis_paid_after, ROUND(SUM(paid_after)/1e6,2) AS millions_after,
                            ROUND(SUM(paid_after) FILTER (WHERE months_paid_after >= 6)/1e6,2) AS millions_after_6plus_months, COUNT(*) FILTER (WHERE months_paid_after >= 6) AS npis_6plus_months
                     FROM d3_npi""")
S["by_source"] = q("""SELECT source, tier, COUNT(DISTINCT npi) AS npis, ROUND(SUM(paid_after)/1e6,2) AS millions_after, ROUND(quantile_cont(paid_after,0.5)) AS median_paid, MAX(months_paid_after) AS max_months
                      FROM d3_paid_after GROUP BY 1,2 ORDER BY 4 DESC""")
S["headline_by_source_count"] = q("""SELECT sources, COUNT(*) FILTER (WHERE paid_after > 0), ROUND(SUM(paid_after)/1e6,2) FROM d3_npi GROUP BY 1 ORDER BY 3 DESC LIMIT 8""")
S["enrolled_after"] = q("""SELECT COUNT(DISTINCT npi) FROM d3_enrolled_after WHERE tier='A' AND source IN ('MEDICARE_REVOKED','OIG_LEIE')""")
S["enrolled_after_by_state"] = q("""SELECT medicaid_state, COUNT(DISTINCT npi) n FROM d3_enrolled_after WHERE tier='A' AND source IN ('MEDICARE_REVOKED','OIG_LEIE') GROUP BY 1 ORDER BY 2 DESC LIMIT 10""")
S["crossstate"] = q("""SELECT COUNT(*) pairs, COUNT(DISTINCT npi) npis, COUNT(DISTINCT npi) FILTER (WHERE federal_sources IS NOT NULL) corroborated_npis,
                              ROUND(SUM(paid_after_term)/1e6,2) millions_after, COUNT(DISTINCT npi) FILTER (WHERE paid_after_term > 0) npis_paid_after FROM d3_crossstate""")
S["crossstate_by_code"] = q("""SELECT term_code, term_reason, COUNT(DISTINCT npi), ROUND(SUM(paid_after_term)/1e6,2) FROM d3_crossstate GROUP BY 1,2 ORDER BY 3 DESC""")
S["deceased"] = q("""SELECT tier, COUNT(DISTINCT npi), ROUND(SUM(paid_after)/1e6,2), COUNT(DISTINCT npi) FILTER (WHERE months_paid_after >= 6) FROM d3_paid_after WHERE source='TMSIS_DECEASED' GROUP BY 1""")
S["deactivated"] = q("""SELECT COUNT(DISTINCT npi), ROUND(SUM(paid_after)/1e6,2) FROM d3_paid_after WHERE source='NPPES_DEACTIVATED'""")
S["by_year"] = q("""SELECT year(first_event_dt) yr, COUNT(*) FILTER (WHERE paid_after > 0), ROUND(SUM(paid_after)/1e6,2) FROM d3_npi GROUP BY 1 ORDER BY 1""")
S["top20"] = q("""SELECT npi, nppes_name, entity_type, sources, first_event_dt, medicaid_home_state, months_paid_after, first_month_after, last_month_after, ROUND(paid_after) paid_after, names_agree
                  FROM d3_npi WHERE paid_after > 0 ORDER BY paid_after DESC LIMIT 20""")
S["tier_c"] = q("""SELECT COUNT(*), ROUND(SUM(paid_after)/1e6,2) FROM d3_paid_after WHERE tier='C'""")
S["id_match"] = q("""SELECT id_match, tier, COUNT(DISTINCT npi) AS npis_paid_after, ROUND(SUM(paid_after)/1e6,2) AS millions_after
                     FROM d3_paid_after WHERE source NOT LIKE 'TMSIS_%' GROUP BY 1,2 ORDER BY 1, 2""")
S["id_match_headline"] = q("""SELECT id_match, COUNT(*) FILTER (WHERE paid_after > 0), ROUND(SUM(paid_after)/1e6,2) FROM d3_npi GROUP BY 1 ORDER BY 2 DESC""")
def _d(sql):
    try: return str(con.execute(sql).fetchone()[0])
    except Exception as e: return "n/a"
S["file_dates"] = [["T-MSIS provider spending, latest service month", _d("SELECT MAX(month) FROM spend_any_month")],
                   ["T-MSIS enrollment segments, latest segment start", _d("SELECT MAX(start_dt) FROM enroll")],
                   ["T-MSIS enrollment segments, latest dated segment end", _d("SELECT MAX(end_dt) FROM enroll WHERE end_dt <= DATE '2026-12-31'")],
                   ["Medicare revocations, latest effective date", _d("SELECT MAX(revoked_dt) FROM revoked")],
                   ["OIG LEIE, latest exclusion date", _d("SELECT MAX(excl_dt) FROM leie")],
                   ["SAM.gov, latest active date", _d("SELECT MAX(active_dt) FROM sam WHERE active_dt <= current_date")],
                   ["State exclusion lists, latest action date", _d("SELECT MAX(excl_dt) FROM state_exclusions")],
                   ["NPPES, latest deactivation date", _d("SELECT MAX(deact_date) FROM nppes")]]
S["top_deceased"] = q("""SELECT npi, nppes_name, source_state, event_dt, nppes_deact_date, months_paid_after, first_month_after, last_month_after, ROUND(paid_after) paid_after FROM d3_top WHERE source='TMSIS_DECEASED' AND tier='A' ORDER BY paid_after DESC LIMIT 10""")
S["top_crossstate"] = q("""SELECT npi, nppes_name, entity_type, term_state, term_reason, term_dt, active_state, active_end, ROUND(paid_after_term) paid_after, federal_sources FROM d3_crossstate ORDER BY (federal_sources IS NOT NULL) DESC, paid_after_term DESC LIMIT 12""")
for k, v in S.items(): print(f"\n== {k}"); [print("  ", r) for r in v]
json.dump({k: [[str(x) for x in r] for r in v] for k, v in S.items()}, open("demo/cache/d3_summary.json", "w"), indent=1)

import sys; sys.path.insert(0, "detectors"); from _methods import write_section, md_table
h = S["headline"][0]; cs = S["crossstate"][0]; de = {r[0]: r for r in S["deceased"]}
body = f"""
**Rule.** An NPI appears on a federal or state "must not be paid" list with an effective date, and Medicaid (T-MSIS provider spending, service months 2018-01 to 2024-12) shows paid claims in service months strictly after that month and, where the source gives one, before the window end (Medicare re-enrollment bar expiry, state reinstatement date). Dollars count each NPI-month once whether the NPI billed or rendered. Tier A grounds only: Medicare revocations under 42 CFR 424.535(a)(2),(3),(4),(5),(7),(8),(10),(12),(13),(14),(18),(19),(20),(22),(23); every OIG LEIE exclusion without a state waiver; California, New York and Texas Medicaid exclusion lists (rows carrying an NPI). Administrative revocations ((a)(1) noncompliance, (a)(6), (a)(9) alone, (a)(11), (a)(17), (a)(21)) are kept in the tables as tier B and excluded from the headline.

**Headline.** {h[0]:,} NPIs are on a tier-A list with an effective date inside the data window; {h[1]:,} of them have Medicaid claims with service months after the action, totalling ${h[2]:,.2f}M; {h[4]:,} were paid in six or more months after the action (${h[3]:,.2f}M). These are dollars paid after an action that should have triggered a state screening check under 42 CFR 455.436 (monthly LEIE, SAM and NPPES checks) and, for for-cause Medicare terminations and other states' terminations, a termination decision under 42 CFR 455.416. They are not "improper payments": a Medicare revocation is not by itself a Medicaid payment bar, appeals and reinstatements exist, and some payments may reflect claims that were later recouped. OIG's audit of providers terminated in one state and paid in others found $50.3M across 584 providers, so the order of magnitude is consistent.

{md_table(S["by_source"], ["source","tier","NPIs paid after","$M after","median $ per NPI","max months"])}

**Identity checks.** Every NPI on every list must pass the NPI check digit (Luhn with the 80840 prefix). Rows on any list whose name shares no token with the NPPES record for that NPI are set aside as tier C, whatever the source (the California list's provider-number field can carry an employer's NPI, and a revocation can name a practice rather than the individual; {S['tier_c'][0][0]:,} such rows, ${S['tier_c'][0][1]:,.2f}M, are excluded from every number above). Texas lists everyone ever excluded, so its rows use the reinstatement or eligible-to-reapply date as the window end and pre-2018 rows without either are tier B.\n\n**Match tiers.** Every event in this detector carries the NPI itself, so the match is exact by identifier; the tier records how far the identity could be verified against NPPES. Rows without an NPI on the source list are handled separately by the name-matching script (scripts/sam_match_claude.py) and never enter the headline. Counts are NPIs with Medicaid service months after the action, tier A and B lists combined, TMSIS terminations excluded.\n\n{md_table(S["id_match"], ["identity match", "tier", "NPIs paid after", "$M after"])}\n\n**File dates.** "Excluded but still enrolled" is often an artefact of a stale enrollment file, so the headline never relies on enrollment status: it counts paid service months in T-MSIS after the action. The enrollment-segment figures below are reported separately and carry the file's own dates.\n\n{md_table(S["file_dates"], ["file", "latest date in the file"])}\n\n**Still enrolled.** {S["enrolled_after"][0][0]:,} NPIs revoked by Medicare (tier A) or excluded by OIG still hold an active Medicaid enrollment segment (T-MSIS status 02-06) more than 90 days after the action.

{md_table(S["enrolled_after_by_state"], ["Medicaid state","NPIs"])}

**Deceased.** T-MSIS status 80 (provider deceased) is applied by some states to organizations and to old records, so the test is restricted to individual NPIs whose latest status in that state is 80 and whose record starts 2015 or later. Tier A additionally requires NPPES to show the NPI deactivated. Tier A: {de.get('A',[0,0,0,0])[1]:,} NPIs, ${de.get('A',[0,0,0,0])[2]:,.2f}M paid after; tier B (no NPPES corroboration): {de.get('B',[0,0,0,0])[1]:,} NPIs, ${de.get('B',[0,0,0,0])[2]:,.2f}M.

**Cross-state.** Terminated for cause in one state (T-MSIS status 60, 65, 66, 67, 70, 72, 75, 78, 81; termination is the final status in that state; individuals or organizations enrolled in three or fewer states, so national chains with one mis-coded segment are excluded) and active in another state more than 90 days later: {cs[1]:,} NPIs ({cs[0]:,} state pairs), {cs[2]:,} of them also on a federal or state exclusion list, {cs[4]:,} with Medicaid dollars after the termination (${cs[3]:,.2f}M). T-MSIS termination codes are state-coded and uneven, so this list is ranked with federally corroborated NPIs first and is presented as a screening queue, not a finding.

{md_table(S["crossstate_by_code"], ["code","reason","NPIs","$M after"])}

**NPI deactivation.** {S["deactivated"][0][0]:,} NPIs deactivated in NPPES show Medicaid paid claims in later service months (${S["deactivated"][0][1]:,.2f}M). Reported as tier B because states carry legacy identifiers.

**Top 20 by dollars after the action (tier A lists).**

{md_table(S["top20"], ["NPI","name (NPPES)","type","lists","first action","Medicaid state","months paid after","first","last","$ after","name agrees"])}

Tables: `d3_events`, `d3_paid_after`, `d3_enrolled_after`, `d3_crossstate`, `d3_npi`, `d3_top`; app rows in `flags` (detector D3). Code: `detectors/d3_revoked_but_paid.py`.
"""
write_section("Detector 3: paid after a screening-trigger action", body)
con.execute("CHECKPOINT"); con.close(); print("done")
