#!/usr/bin/env python3
"""Unified provider risk: one row per NPI with a tier, a score and the detectors behind it. The hierarchy is explicit.

  Tier 1  documented action, then payment: on a tier-A federal or state list and Medicaid service months after it (D3 tier A)
  Tier 2  physically impossible volume with concurrency: impossible personal-service hours billed by three or more organizations in a
          month, more than 24 hours per patient per day, or over Minnesota's own daily cap (D2 tier A)
  Tier 3  network structure plus a label link: member of an eligible community whose label family is present (D1)
  Tier 4  structure only, or single-organization impossibility, or growth anomaly (D1 eligible without label link, D2 tier B)
  Tier 5  informational (D3 tier B, D2 umbrella volume, community membership below the ranked list)

  score = tier base (90, 75, 60, 45, 25) + 8 for each additional detector that independently reached the NPI (cap 16)
          + min(9, log10(dollars at risk)) ; capped at 100. Dollars at risk = the highest single-detector figure for the NPI, never a sum.
"""
import json, math, os, sys, time, duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "detectors")
from _methods import write_section, md_table
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb")); con.execute("SET threads=8")
def q(s): return con.execute(s).fetchall()

con.execute("""CREATE OR REPLACE MACRO pretty_source(s) AS
  list_aggregate(list_transform(string_split(s, ','), x ->
    CASE WHEN x = 'MEDICARE_REVOKED' THEN 'the Medicare revocation list'
         WHEN x = 'OIG_LEIE' THEN 'the OIG exclusion list'
         WHEN x = 'NPPES_DEACTIVATED' THEN 'the deactivated NPI list'
         WHEN x = 'TMSIS_DECEASED' THEN 'a state file marking the provider deceased'
         WHEN x LIKE 'STATE_EXCL_%' THEN 'the ' || substr(x, 12) || ' Medicaid exclusion list'
         WHEN x LIKE 'SAM_%' THEN 'the SAM.gov exclusion list (' || replace(substr(x, 5), '_', ' ') || ')'
         WHEN x LIKE 'TMSIS_TERM_%' THEN 'a state Medicaid termination'
         ELSE lower(replace(x, '_', ' ')) END), 'string_agg', ' and ')""")
con.execute("CREATE TABLE IF NOT EXISTS provider_procedure_signal (npi VARCHAR, points INTEGER, reason VARCHAR)")
con.execute("CREATE TABLE IF NOT EXISTS d2_umbrella (npi VARCHAR, avg_org_render DOUBLE, max_org_render DOUBLE)")
con.execute("""
CREATE OR REPLACE TABLE provider_risk AS
WITH d3 AS (
  SELECT npi, MAX(CASE WHEN tier='A' THEN 1 ELSE 0 END) AS d3_a, MAX(CASE WHEN tier='B' THEN 1 ELSE 0 END) AS d3_b, MAX(paid_after) AS d3_paid_after,
         string_agg(DISTINCT source, ',') AS d3_sources, MIN(event_dt) AS d3_first_event, MAX(months_paid_after) AS d3_months
  FROM d3_top WHERE tier IN ('A','B') GROUP BY 1),
d2 AS (
  SELECT t.servicing_npi AS npi, months_impossible, months_over_mn_cap, months_umbrella, peak_hours_per_day, max_billing_orgs, paid_flagged_months, paid_total, growth_paid_24_22, entity_type,
         max_patients, u.avg_org_render,
         -- supervisory umbrella: hundreds of patients a month, or billing organizations that each carry dozens of rendering clinicians
         (max_patients > 500 OR COALESCE(u.avg_org_render, 0) >= 30) AS umbrella,
         CASE WHEN months_over_mn_cap > 0 OR (months_impossible > 0 AND entity_type = '2')
                   OR (months_impossible > 0 AND max_billing_orgs >= 3 AND NOT (max_patients > 500 OR COALESCE(u.avg_org_render, 0) >= 30)) THEN 'A'
              WHEN months_impossible > 0 THEN 'B' WHEN months_umbrella > 0 OR months_implausible > 0 THEN 'C' END AS d2_tier
  FROM d2_top t LEFT JOIN d2_umbrella u ON u.npi = t.servicing_npi WHERE months_impossible > 0 OR months_over_mn_cap > 0 OR months_umbrella > 0 OR months_implausible > 0),
d1 AS (
  SELECT m.npi, c.cluster_id, c.rank, c.eligible, c.label_family, c.risk_score, m.medicaid_2024, m.medicare_2023, c.summary
  FROM cluster_members m JOIN clusters c ON c.cluster_id = m.cluster_id
  QUALIFY ROW_NUMBER() OVER (PARTITION BY m.npi ORDER BY c.eligible DESC, c.rank) = 1),
u AS (SELECT npi FROM d3 UNION SELECT npi FROM d2 UNION SELECT npi FROM d1 WHERE eligible)
SELECT u.npi, COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))) AS name, n.entity_type, n.city, n.state, n.taxonomy, pc.county_fips, ps.state AS medicaid_state,
       d3.d3_a, d3.d3_b, d3.d3_paid_after, d3.d3_sources, d3.d3_first_event, d3.d3_months,
       d2.d2_tier, d2.months_impossible, d2.months_over_mn_cap, d2.months_umbrella, d2.peak_hours_per_day, d2.max_billing_orgs, d2.paid_flagged_months, d2.growth_paid_24_22, d2.max_patients, d2.umbrella AS d2_umbrella,
       COALESCE(pp.points, 0) AS procedure_points, pp.reason AS procedure_reason,
       d1.cluster_id AS d1_cluster_id, d1.rank AS d1_rank, d1.eligible AS d1_eligible, d1.label_family AS d1_label_family, d1.risk_score AS d1_score, d1.medicaid_2024 AS d1_medicaid_2024, d1.medicare_2023 AS d1_medicare_2023,
       CASE WHEN d3.d3_a = 1 THEN 1
            WHEN d2.d2_tier = 'A' THEN 2
            WHEN d1.eligible AND d1.label_family = 1 THEN 3
            WHEN d1.eligible OR d2.d2_tier = 'B' THEN 4
            ELSE 5 END AS tier,
       (CASE WHEN d3.d3_a = 1 THEN 1 ELSE 0 END) + (CASE WHEN d2.d2_tier IN ('A','B') THEN 1 ELSE 0 END) + (CASE WHEN d1.eligible THEN 1 ELSE 0 END) AS n_detectors,
       -- corroboration counts only strong findings: a tier-A list action, tier-A (concurrent) impossible volume, or membership of a ranked community
       (CASE WHEN d3.d3_a = 1 THEN 1 ELSE 0 END) + (CASE WHEN d2.d2_tier = 'A' THEN 1 ELSE 0 END) + (CASE WHEN d1.eligible THEN 1 ELSE 0 END) AS n_strong,
       -- dollars at risk is the figure of the detector that set the tier, never a sum and never borrowed from a weaker indicator
       CASE WHEN d3.d3_a = 1 THEN COALESCE(d3.d3_paid_after, 0)
            WHEN d2.d2_tier = 'A' THEN COALESCE(d2.paid_flagged_months, 0)
            WHEN d1.eligible AND d1.label_family = 1 THEN COALESCE(d1.medicaid_2024, 0)
            WHEN d1.eligible OR d2.d2_tier = 'B' THEN GREATEST(CASE WHEN d1.eligible THEN COALESCE(d1.medicaid_2024, 0) ELSE 0 END, CASE WHEN d2.d2_tier = 'B' THEN COALESCE(d2.paid_flagged_months, 0) ELSE 0 END)
            ELSE GREATEST(COALESCE(d3.d3_paid_after, 0), COALESCE(d2.paid_flagged_months, 0), COALESCE(d2.growth_paid_24_22, 0)) END AS dollars_at_risk,
       list_filter(['D3', 'D2', 'D1'], x -> (x = 'D3' AND d3.npi IS NOT NULL) OR (x = 'D2' AND d2.npi IS NOT NULL) OR (x = 'D1' AND d1.npi IS NOT NULL)) AS detectors
FROM u LEFT JOIN d3 USING (npi) LEFT JOIN d2 USING (npi) LEFT JOIN d1 USING (npi)
LEFT JOIN provider_procedure_signal pp ON pp.npi = u.npi
LEFT JOIN nppes n ON n.npi = u.npi LEFT JOIN provider_state ps ON ps.npi = u.npi LEFT JOIN zcta_primary_county pc ON pc.zcta = n.zip5
QUALIFY row_number() OVER (PARTITION BY u.npi ORDER BY d1.rank NULLS LAST, d3.d3_paid_after DESC NULLS LAST) = 1""")
con.execute("""
CREATE OR REPLACE TABLE provider_risk AS
SELECT *, LEAST(100.0, (CASE tier WHEN 1 THEN 90 WHEN 2 THEN 75 WHEN 3 THEN 60 WHEN 4 THEN 45 ELSE 25 END) + LEAST(16, 8 * GREATEST(n_strong - 1, 0)) + LEAST(9.0, LOG10(GREATEST(dollars_at_risk, 1))) + procedure_points) AS score,
       CASE tier WHEN 1 THEN 'documented action, then payment' WHEN 2 THEN 'impossible volume with concurrency' WHEN 3 THEN 'network structure with a list link'
                 WHEN 4 THEN 'structure or single-organization volume' ELSE 'informational' END AS tier_label,
       concat_ws('; ',
         CASE WHEN d3_a = 1 THEN 'Listed on ' || pretty_source(d3_sources) || ' since ' || strftime(d3_first_event, '%B %-d, %Y') || '; Medicaid still paid claims in ' || d3_months || ' later months, $' || format('{:,}', CAST(ROUND(d3_paid_after) AS BIGINT)) || ' in total' END,
         CASE WHEN d2_tier = 'A' THEN 'Billed more hands-on hours than a day holds in ' || months_impossible || ' month(s), peaking at ' || ROUND(peak_hours_per_day, 1) || ' hours per day across ' || max_billing_orgs || ' billing organizations' END,
         CASE WHEN d2_tier = 'B' AND d2_umbrella THEN 'Hours beyond a day in ' || months_impossible || ' month(s), but with up to ' || CAST(max_patients AS BIGINT) || ' patients a month' || CASE WHEN max_billing_orgs >= 3 THEN ' across ' || max_billing_orgs || ' billing organizations' ELSE '' END || ', which points to a supervising clinician on the claims rather than one person''s hours; records needed'
              WHEN d2_tier = 'B' THEN 'Hours beyond a day in ' || months_impossible || ' month(s) under one organization, which can be supervisory billing; records needed' END,
         CASE WHEN months_over_mn_cap > 0 THEN 'Over the state daily cap in ' || months_over_mn_cap || ' month(s)' END,
         CASE WHEN d1_eligible THEN 'Part of provider network ' || d1_cluster_id || ', ranked ' || d1_rank || ' nationally' END,
         procedure_reason,
         CASE WHEN n_strong >= 2 THEN 'Confirmed independently by ' || n_strong || ' detectors' WHEN n_detectors >= 2 THEN 'A second detector adds a weaker signal' END) AS reasons
FROM provider_risk""")
con.execute("CREATE OR REPLACE TABLE provider_risk AS SELECT *, ROW_NUMBER() OVER (ORDER BY score DESC, dollars_at_risk DESC) AS rank FROM provider_risk")
S = {}
S["tiers"] = q("SELECT tier, tier_label, COUNT(*), ROUND(SUM(dollars_at_risk)/1e6,2), COUNT(*) FILTER (WHERE n_strong >= 2) FROM provider_risk GROUP BY 1,2 ORDER BY 1")
S["top"] = q("SELECT rank, npi, name, entity_type, state, tier, ROUND(score,1), detectors, ROUND(dollars_at_risk), reasons FROM provider_risk ORDER BY rank LIMIT 25")
S["corroborated"] = q("SELECT COUNT(*) FROM provider_risk WHERE n_strong >= 2")
for k, v in S.items(): print(f"== {k}"); [print("  ", r) for r in v]
body = f"""
**Hierarchy.** Every NPI any detector reached gets one row in `provider_risk` with a tier, a score and the reasons. Tier 1: on a tier-A federal or state list and Medicaid service months after the action. Tier 2: physically impossible personal-service volume billed by three or more small organizations in a month with at most 500 patients, more than 24 hours per patient per day, or over a state's own daily cap. Volume with hundreds of patients a month, or billed through organizations that each carry dozens of rendering clinicians, is a supervisory umbrella and stays in tier 4. Tier 3: member of an eligible provider community with a label link. Tier 4: structure only, or single-organization impossibility. Tier 5: informational. Score = tier base (90, 75, 60, 45, 25) + up to 8 procedure points (dollars per patient on a code in the top 5% of every provider billing it, most dollars on codes with a history of abuse, or Medicare charges far above the code's usual charge-to-allowed ratio) + 8 per additional strong finding that independently reached the NPI (a tier-A list action, tier-A concurrent impossible volume, or a ranked community; cap 16) + min(9, log10 dollars at risk), capped at 100. Dollars at risk is the figure of the detector that set the tier (service months after the action for tier 1, paid in flagged months for tier 2, Medicaid 2024 for the community tiers), never a sum and never borrowed from a weaker indicator, so a single-organization volume flag cannot lift a small documented-action case above a large one. The county map sums each NPI once.

{md_table(S["tiers"], ["tier","meaning","NPIs","$M at risk","reached by 2+ detectors"])}

{S["corroborated"][0][0]:,} NPIs were reached by two or more detectors independently; corroboration is the strongest signal the pipeline produces and it is weighted accordingly.

**Top 25 referral candidates.**

{md_table(S["top"], ["rank","NPI","name","type","state","tier","score","detectors","$ at risk","reasons"])}

Table: `provider_risk`. Code: `detectors/risk_score.py`. Every row is a referral candidate for records review, not a finding.
"""
write_section("Unified provider risk score", body)
json.dump({k: [[str(x) for x in r] for r in v] for k, v in S.items()}, open("demo/cache/risk_summary.json", "w"), indent=1)
con.execute("CHECKPOINT"); con.close(); print("done")
