# Verity methods

How the warehouse is built, what was dropped, and the numbers behind every figure in the demo. All inputs are public federal data (see `docs/DATA.md`).

## Build

**In plain language.** This section describes how the working database is built and what data is allowed into it. A SQL script is run by a Python driver to create a DuckDB file, and a companion CSV lists the time-based procedure codes along with the minutes each billed unit implies, a divisor for group codes, and deliberately low durations for untimed session codes so the impossible-days check understates rather than overstates. Per-diem codes carry no minutes and are kept only so day counts can be compared against patients times days in the month. Spending records are filtered to ten-digit identifiers on both provider fields and paid amounts between 0 and 50,000,000 dollars per provider-code-month, with one table further limited to codes on the time-code list. Enrollment segments with placeholder dates are dropped or treated as open-ended, and home state is assigned by the largest presence weight, which is not calendar days because segments overlap by plan and month. Exclusion screening relies on the LEIE file, the revoked list, and termination codes, since no SAM.gov extract was available.






`ingest/01_build_warehouse.sql` is executed by `ingest/build_warehouse.py` into `data/verity.duckdb` (DuckDB 1.5.5). Time-based HCPCS codes and the minutes implied by each unit are in `ingest/02_timecodes.csv`; `minutes_per_unit` is the face time one billed unit implies, `group_divisor` is the assumed number of participants for group codes, and untimed session codes use a conservative (low) duration so the impossible-days detector under-counts rather than over-counts. Per-diem codes are included with no minutes so day counts can be checked against patients times days in the month.

Filters on the T-MSIS Medicaid spending file: both NPIs must be ten digits, paid must be between 0 and 50,000,000 dollars per NPI-code-month, and (for the `spend` table only) the HCPCS code must be in the time-code list. Medicaid enrollment segments with placeholder start dates (1900-01-01, 1970-01-01) are dropped. A provider's home state is the state with the most enrolled days. Segments overlap (one per plan and month), so `days` in `provider_state` is a presence weight for ranking states, not calendar days. Placeholder dates in the segments file (`0001-01-01`, `1900-01-01`, `1970-01-01` starts; `9999-12-30` ends) are dropped or treated as open-ended. No SAM.gov extract is on disk; LEIE, the CMS revoked list and Medicaid termination codes are the exclusion sources.

## Warehouse sanity checks (2026-09-05 12:11 ET)

**In plain language.** This section is a data quality check on the analysis warehouse before any findings are produced. It counts the rows in each source table and shows what was filtered out of the Medicaid spending file. After keeping only time-based procedure codes, valid provider identifiers, and payments between zero and 50 million dollars, the working spend table holds 56.7 million rows, about 1.22 million servicing providers, and 532.82 billion dollars, rising from 51.31 billion in 2018 to 91.68 billion in 2024. Large numbers of rows were removed for unusable billing or servicing identifiers, roughly 7.9 million and 10.4 million, so coverage is incomplete and any provider-level totals should be read with that in mind. Other checks show expected patterns, such as two owner types, all revoked records carrying a date, only 8,841 of 83,842 exclusion records having a provider identifier, and incorporation dates parsing for only part of the hospice, home health, and nursing facility files.






Tables in `data/verity.duckdb`: chow, drops, enroll, hha, hospice, hospital, leie, medicare_revoked_hhs, nppes, optout, order_referring, owners, ppef, provider_state, revoked, saturation, saturation_cbsa, saturation_county, snf, spend, spend_totals, timecodes

**spend (time-based HCPCS only, clean NPIs, paid between 0 and 50M)**

| rows | servicing NPIs | $ billions |
|---|---|---|
| 56,701,897 | 1,220,721 | 532.82 |

**Rows dropped from the Medicaid spending file**

| reason | rows |
|---|---|
| total_rows | 238,015,729 |
| paid_over_50M | 1,239 |
| paid_negative | 9,212 |
| bad_billing_npi | 7,863,474 |
| bad_servicing_npi | 10,371,226 |
| servicing_npi_not_1_or_2_prefix | 7,648 |
| rows_with_time_code | 60,316,436 |

**Medicaid enrollment**

| enrollment segments | NPIs with a home state |
|---|---|
| 49,470,292 | 4,266,209 |

**CMS enrollment files**

| hospice | HHA | SNF | hospital | owner rows | CHOW rows | PPEF rows |
|---|---|---|---|---|---|---|
| 5,802 | 11,494 | 14,410 | 9,161 | 613,574 | 5,999 | 2,978,925 |

**Owner types (expect I and O)**

| type | rows |
|---|---|
| I | 455,179 |
| O | 158,395 |

**Labels**

| revoked rows | revoked with date | LEIE rows | LEIE with NPI |
|---|---|---|---|
| 8,136 | 8,136 | 83,842 | 8,841 |

**Incorporation date parse rate**

| file | rows | parsed inc_date |
|---|---|---|
| hospice | 5,802 | 4,389 |
| hha | 11,494 | 8,815 |
| snf | 14,410 | 8,607 |

**Market saturation (typed county table)**

| rows | service types | first period | last period | moratorium rows |
|---|---|---|---|---|
| 1,030,290 | 24 | 2020-01-01 to 2020-12-31 | 2025-01-01 to 2025-12-31 | 0 |

**NPPES**

| NPIs | individuals | organizations | deactivated |
|---|---|---|---|
| 9,726,865 | 7,415,294 | 1,959,660 | 370,737 |

**Spend by year**

| year | rows | $ billions |
|---|---|---|
| 2018 | 6,404,063 | 51.31 |
| 2019 | 7,205,022 | 62.43 |
| 2020 | 7,130,428 | 67.55 |
| 2021 | 8,778,697 | 77.61 |
| 2022 | 9,181,576 | 86.07 |
| 2023 | 9,655,691 | 96.15 |
| 2024 | 8,346,420 | 91.68 |

**Top 15 time-based codes by dollars**

| hcpcs | description | $ billions |
|---|---|---|
| T1019 | Personal care services per 15 min | 106.49 |
| 99213 | Office visit established patient level 3 | 32.59 |
| 99214 | Office visit established patient level 4 | 29.72 |
| T2016 | Habilitation residential waiver per diem | 27.78 |
| H2016 | Comprehensive community support services per diem | 17.53 |
| H2015 | Comprehensive community support services per 15 min | 16.20 |
| S5125 | Attendant care services per 15 min | 15.72 |
| 90837 | Psychotherapy 60 min | 11.97 |
| S5102 | Adult day care per diem | 9.34 |
| T1020 | Personal care services per diem | 8.24 |
| H2017 | Psychosocial rehabilitation services per 15 min | 8.19 |
| 90834 | Psychotherapy 45 min | 7.99 |
| T1017 | Targeted case management each 15 min | 7.87 |
| T2021 | Day habilitation waiver per 15 min | 7.57 |
| H2019 | Therapeutic behavioral services per 15 min | 7.37 |

## Detector 3: dead in Medicare, alive in Medicaid

**In plain language.** This detector matches provider IDs that appear on federal or state "do not pay" lists against Medicaid payment records for service months from January 2018 through December 2024, and flags payments dated strictly after the listing took effect and, where a reinstatement or bar expiry date exists, before that end date. Only the strongest grounds count toward the headline, meaning for-cause Medicare revocations, federal exclusions without a state waiver, and three state exclusion lists; administrative revocations and weaker signals are kept in the tables but held back as lower tiers. Of 15,708 provider IDs on a top-tier list with an effective date in the window, 353 had Medicaid paid claims after the action for $50.36M, and 174 were paid in six or more later months for $45.38M, which is in line with a prior federal audit that found $50.3M across 584 providers. Separate checks show 2,763 revoked or excluded IDs still holding an active Medicaid enrollment segment more than 90 days later, and 6,361 IDs terminated for cause in one state while active in another. The section states its own limits: every ID must pass the check digit test, rows whose names do not match the national registry are set aside, deceased-status and deactivation results lack corroboration and are reported as lower tier, and the cross-state list is described as a screening queue rather than a finding because state termination codes are uneven.






**Rule.** An NPI appears on a federal or state "must not be paid" list with an effective date, and Medicaid (T-MSIS provider spending, service months 2018-01 to 2024-12) shows paid claims in service months strictly after that month and, where the source gives one, before the window end (Medicare re-enrollment bar expiry, state reinstatement date). Dollars count each NPI-month once whether the NPI billed or rendered. Tier A grounds only: Medicare revocations under 42 CFR 424.535(a)(2),(3),(4),(5),(7),(8),(10),(12),(13),(14),(18),(19),(20),(22),(23); every OIG LEIE exclusion without a state waiver; California, New York and Texas Medicaid exclusion lists (rows carrying an NPI). Administrative revocations ((a)(1) noncompliance, (a)(6), (a)(9) alone, (a)(11), (a)(17), (a)(21)) are kept in the tables as tier B and excluded from the headline.

**Headline.** 15,708 NPIs are on a tier-A list with an effective date inside the data window; 353 of them have Medicaid paid claims dated after the action, totalling $50.36M; 174 were paid in six or more months after the action ($45.38M). OIG's 2022 audit (A-05-19-00029 family) found $50.3M across 584 providers terminated elsewhere, so the order of magnitude is consistent.

| source | tier | NPIs paid after | $M after | median $ per NPI | max months |
|---|---|---|---|---|---|
| NPPES_DEACTIVATED | B | 511 | 231.20 | 5,352.00 | 84 |
| MEDICARE_REVOKED | A | 270 | 39.64 | 13,607.00 | 67 |
| MEDICARE_REVOKED | B | 66 | 25.72 | 25,525.00 | 84 |
| STATE_EXCL_CA | C | 14 | 23.38 | 27,660.00 | 46 |
| OIG_LEIE | A | 14 | 8.07 | 67,706.00 | 55 |
| STATE_EXCL_CA | A | 81 | 7.22 | 12,029.00 | 52 |
| TMSIS_DECEASED | B | 20 | 4.02 | 40,210.00 | 81 |
| STATE_EXCL_NY | A | 35 | 3.45 | 7,470.00 | 78 |
| STATE_EXCL_TX | A | 6 | 2.33 | 54,286.00 | 33 |
| STATE_EXCL_TX | B | 3 | 2.28 | 90,573.00 | 25 |
| SAM_OPM | B | 5 | 0.11 | 2,266.00 | 27 |
| STATE_EXCL_NY | C | 5 | 0.04 | 6,519.00 | 3 |
| STATE_EXCL_TX | C | 1 | 0.01 | 13,635.00 | 7 |

**Identity checks.** Every NPI on every list must pass the NPI check digit (Luhn with the 80840 prefix). State-list rows whose name shares no token with the NPPES record for that NPI are set aside as tier C (the California list's provider-number field can carry an employer's NPI; 20 such rows, $23.43M, are excluded from every number above). Texas lists everyone ever excluded, so its rows use the reinstatement or eligible-to-reapply date as the window end and pre-2018 rows without either are tier B.

**Still enrolled.** 2,763 NPIs revoked by Medicare (tier A) or excluded by OIG still hold an active Medicaid enrollment segment (T-MSIS status 02-06) more than 90 days after the action.

| Medicaid state | NPIs |
|---|---|
| LA | 460 |
| TX | 342 |
| VA | 313 |
| TN | 284 |
| ID | 283 |
| CA | 280 |
| PA | 200 |
| RI | 197 |
| MI | 167 |
| GA | 130 |

**Deceased.** T-MSIS status 80 (provider deceased) is applied by some states to organizations and to old records, so the test is restricted to individual NPIs whose latest status in that state is 80 and whose record starts 2015 or later. Tier A additionally requires NPPES to show the NPI deactivated. Tier A: 0 NPIs, $0.00M paid after; tier B (no NPPES corroboration): 20 NPIs, $4.02M.

**Cross-state.** Terminated for cause in one state (T-MSIS status 60, 65, 66, 67, 70, 72, 75, 78, 81; termination is the final status in that state; individuals or organizations enrolled in three or fewer states, so national chains with one mis-coded segment are excluded) and active in another state more than 90 days later: 6,361 NPIs (16,319 state pairs), 161 of them also on a federal or state exclusion list, 2,980 with Medicaid dollars after the termination ($1,484.95M). T-MSIS termination codes are state-coded and uneven, so this list is ranked with federally corroborated NPIs first and is presented as a screening queue, not a finding.

| code | reason | NPIs | $M after |
|---|---|---|---|
| 70 | TERM - LICENSE REVOKED | 4,703 | 944.84 |
| 81 | TERM - STATE EXCLUSION/ DEBARMENT, ETC. | 948 | 429.19 |
| 78 | TERM - ONSITE REVIEW/ PROVIDER IS NO LONGER OPERATIONAL | 431 | 101.29 |
| 72 | TERM - MEDICARE/MEDICAID EXCLUSION | 217 | 4.91 |
| 60 | TERM - ABUSE OF BILLING PRIVILEGES | 60 | 0.25 |
| 65 | TERM - FALSE OR MISLEADING INFORMATION | 7 | 3.50 |
| 66 | TERM - FEDERAL EXCLUSION/ DEBARMENT, ETC. | 4 | 0.97 |
| 75 | TERM - MISUSE OF BILLING NUMBER | 2 | 0.00 |

**NPI deactivation.** 511 NPIs deactivated in NPPES show Medicaid paid claims in later service months ($231.20M). Reported as tier B because states carry legacy identifiers.

**Top 20 by dollars after the action (tier A lists).**

| NPI | name (NPPES) | type | lists | first action | Medicaid state | months paid after | first | last | $ after | name agrees |
|---|---|---|---|---|---|---|---|---|---|---|
| 1982736492 | WE CARE TRANSPORTATION | 2 | OIG_LEIE | 2010-01-20 |  | 31 | 2018-01 | 2020-07 | 4,441,513.00 | 1 |
| 1962546176 | MATIAS CLINICAL LABORATORY INC | 2 | MEDICARE_REVOKED | 2018-08-31 | MO | 44 | 2018-09 | 2022-04 | 3,846,471.00 | 1 |
| 1548629520 | EMPIRE MEDICAL LLC | 2 | MEDICARE_REVOKED | 2020-07-31 | DE | 9 | 2020-08 | 2021-04 | 2,389,353.00 | 1 |
| 1679896484 | BLAKES BLESSING HEALTH CARE INC. | 2 | STATE_EXCL_TX | 2022-01-19 | TX | 33 | 2022-02 | 2024-10 | 2,118,903.00 | 1 |
| 1225242985 | KIUP KIM | 1 | STATE_EXCL_CA | 2018-12-10 | AZ | 52 | 2019-01 | 2023-08 | 2,046,769.00 | 1 |
| 1861407637 | HEALTHSMART PACIFIC INC | 2 | OIG_LEIE | 2021-04-20 | MD | 34 | 2021-05 | 2024-02 | 1,639,221.00 | 1 |
| 1215266267 | ADVANCED SPINE AND PAIN CENTERS, PLLC | 2 | MEDICARE_REVOKED | 2021-11-19 | MD | 23 | 2021-12 | 2023-10 | 1,327,755.00 | 1 |
| 1457414286 | DM OPTICAL INC | 2 | STATE_EXCL_NY | 2016-09-22 |  | 26 | 2018-01 | 2020-02 | 1,183,544.00 | 1 |
| 1851726731 | INFINITY DIAGNOSTICS LABORATORY, INC | 2 | STATE_EXCL_NY,MEDICARE_REVOKED | 2022-10-31 | LA | 7 | 2022-11 | 2023-05 | 1,043,387.00 | 1 |
| 1891703922 | COMMUNITY CARE MEDICAL CLINICS INC | 2 | MEDICARE_REVOKED | 2020-03-02 | TX | 19 | 2021-04 | 2023-04 | 960,939.00 | 1 |
| 1871571406 | MOHAMED ASWAD | 1 | OIG_LEIE,MEDICARE_REVOKED | 2016-01-20 | AZ | 55 | 2018-01 | 2022-07 | 901,321.00 | 1 |
| 1407188543 | MERCRIS HOME HEALTH INC | 2 | MEDICARE_REVOKED | 2023-05-01 | TX | 17 | 2023-06 | 2024-10 | 899,287.00 | 1 |
| 1831547868 | SHANONE CHATMAN-ASHLEY | 1 | OIG_LEIE,MEDICARE_REVOKED | 2020-10-23 | LA | 38 | 2020-11 | 2023-12 | 883,542.00 | 1 |
| 1558706549 | JLJ MEDICAL LLC | 2 | MEDICARE_REVOKED | 2021-11-19 | MD | 33 | 2021-12 | 2024-09 | 882,532.00 | 0 |
| 1417068511 |  |  | MEDICARE_REVOKED,OIG_LEIE | 2022-06-06 | CA | 12 | 2022-07 | 2023-06 | 844,467.00 | 0 |
| 1740478270 | FIRST IDEAL ENTERPRISES INC. | 2 | MEDICARE_REVOKED | 2018-10-01 | MI | 38 | 2018-11 | 2021-12 | 843,035.00 | 1 |
| 1518931856 | LINDA WARREN-WATSON | 1 | STATE_EXCL_CA | 2020-10-31 | CA | 16 | 2020-11 | 2022-06 | 828,250.00 | 1 |
| 1609064153 | QUEENS OPTOMETRIC CARE PLLC | 2 | MEDICARE_REVOKED | 2023-10-25 | NY | 11 | 2023-11 | 2024-09 | 777,235.00 | 1 |
| 1336486448 | QOL COMMUNICATION SERVICES, LLC | 2 | MEDICARE_REVOKED | 2024-06-12 | MD | 6 | 2024-07 | 2024-12 | 728,911.00 | 1 |
| 1851702971 | NEW WAVE DIAGNOSTIC RADIOLOGY PLLC | 2 | MEDICARE_REVOKED | 2022-08-19 |  | 27 | 2022-09 | 2024-12 | 580,310.00 | 1 |

Tables: `d3_events`, `d3_paid_after`, `d3_enrolled_after`, `d3_crossstate`, `d3_npi`, `d3_top`; app rows in `flags` (detector D3). Code: `detectors/d3_revoked_but_paid.py`.

## Detector 2: impossible days

**In plain language.** This section explains how paid dollars are turned into implied clinician hours for each rendering provider, billing provider, code and month. Hours are computed three ways: a rate-free floor that counts each claim line as at least one unit, a point estimate using an estimated unit price, and a conservative estimate that inflates that price by 50 percent. Because the estimated price is itself an upper bound on what a unit can pay, the dollar-based hour counts are understatements, so a day flagged as impossible is impossible under every assumption made; group codes are divided by an assumed number of participants, and minutes per unit come from a published code time table. The unit price is estimated as the 5th percentile of paid per line by state, code and year after dropping very low cells, with the median used instead for codes where Medicare crossover lines pay only coinsurance, and published state rates replace the estimate where available, taking the highest non-supervision variant to keep hours conservative. Validation against published rates shows the chosen approach errs upward as intended: the median signed error is about 108 percent for the plain 5th percentile, 176 percent for the trimmed version and 655 percent for the median, across 131 code-years, and the chosen estimator sits at or above 0.9 times the published rate in 117 of them. The detailed table shows the estimate falling below the published rate for a few codes and years, for example the assessment codes where implied units per line are well under one.






**Conversion.** For each rendering NPI, billing NPI, HCPCS code and service month in the T-MSIS spending file, implied clinician hours are computed three ways: a rate-free lower bound (each claim line is at least one unit, so `lines x minutes_per_unit`), a point estimate (`paid / rate_pt x minutes_per_unit`), and a conservative estimate (`paid / rate_cons` with `rate_cons = 1.5 x rate_pt`). Because the data-driven rate is itself an upper bound on the unit price, both dollar-based figures understate hours; the label `IMPOSSIBLE` therefore means impossible under every assumption the method makes. Group codes are divided by the assumed participant count. Minutes per unit come from `ingest/02_timecodes.csv` (CPT/HCPCS unit definitions; untimed session codes use the low end of the CPT time range).

**Unit price estimation.** T-MSIS suppresses every NPI-code-month cell with fewer than 12 claim lines or 12 patients (the smallest cell in the file has 12 of each), so no single-line payments exist and `paid / lines` is an average over 12 or more lines. Under full payment a line pays `units x rate`, so `paid / lines = rate x mean units per line >= rate`: the lower envelope of `paid / lines` across a state's cells is an upper bound on the unit price, and hours computed from it are lower bounds. The estimator is the 5th percentile of `paid / lines` per state, code and year after dropping cells below 20 percent of the median (stray partial payments); for codes Medicare also covers, where crossover lines pay only coinsurance, the median is used instead (session codes bill one unit per line). Where Minnesota publishes the rate (DHS-3945 January 2022 and April 2026, EIDBI billing grid January 2026, MH procedure grid) the highest published non-supervision variant of the code replaces the estimate (several programs share a code at different prices, and the highest keeps hours conservative). The conservative rate is 1.5 times the point rate.

**Validation against Minnesota's published rates** (signed error is positive when the estimate sits above the published unit price, which is the expected direction; `units per line` is the estimate divided by the published rate):

| estimator | median signed error % | median |error| % | code-years |
|---|---|---|---|
| p05 | 107.50 | 107.50 | 131 |
| p05 trimmed | 175.90 | 175.90 | 131 |
| p50 | 655.30 | 655.30 | 131 |
| chosen estimator is >= 0.9 x published |  |  | 117 |

| code | year | cells | crossover | published | published max | p05 | p05 trimmed | p50 | err p05 trimmed % | err p50 % | units/line at p05 | units/line at p50 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 96130 | 2019 | 44 | 1 | 124.36 | 124.36 | 9.37 | 39.04 | 70.56 | -68.60 | -43.30 | 0.31 | 0.57 |
| 96130 | 2020 | 66 | 1 | 124.36 | 124.36 | 44.27 | 44.27 | 99.51 | -64.40 | -20.00 | 0.36 | 0.80 |
| 96130 | 2021 | 182 | 1 | 124.36 | 124.36 | 50.20 | 52.49 | 103.74 | -57.80 | -16.60 | 0.42 | 0.83 |
| 96130 | 2022 | 174 | 1 | 124.36 | 124.36 | 50.53 | 50.53 | 94.39 | -59.40 | -24.10 | 0.41 | 0.76 |
| 96130 | 2023 | 253 | 1 | 124.36 | 124.36 | 47.83 | 48.29 | 94.24 | -61.20 | -24.20 | 0.39 | 0.76 |
| 96130 | 2024 | 206 | 1 | 124.36 | 124.36 | 46.31 | 48.02 | 89.62 | -61.40 | -27.90 | 0.39 | 0.72 |
| 96131 | 2019 | 30 | 1 | 85.05 | 85.05 | 67.95 | 83.11 | 157.61 | -2.30 | 85.30 | 0.98 | 1.85 |
| 96131 | 2020 | 41 | 1 | 85.05 | 85.05 | 58.71 | 58.71 | 113.61 | -31.00 | 33.60 | 0.69 | 1.34 |
| 96131 | 2021 | 128 | 1 | 85.05 | 85.05 | 72.55 | 72.55 | 158.54 | -14.70 | 86.40 | 0.85 | 1.86 |
| 96131 | 2022 | 140 | 1 | 85.05 | 85.05 | 67.53 | 67.53 | 179.31 | -20.60 | 110.80 | 0.79 | 2.11 |
| 96131 | 2023 | 192 | 1 | 85.05 | 85.05 | 51.70 | 51.70 | 141.56 | -39.20 | 66.40 | 0.61 | 1.66 |
| 96131 | 2024 | 161 | 1 | 85.05 | 85.05 | 54.49 | 54.49 | 130.90 | -35.90 | 53.90 | 0.64 | 1.54 |
| 97151 | 2022 | 34 | 0 | 94.80 | 94.80 | 91.89 | 91.89 | 213.12 | -3.10 | 124.80 | 0.97 | 2.25 |
| 97151 | 2023 | 32 | 0 | 94.80 | 94.80 | 124.65 | 124.65 | 226.84 | 31.50 | 139.30 | 1.31 | 2.39 |
| 97151 | 2024 | 40 | 0 | 94.80 | 94.80 | 135.10 | 135.10 | 266.33 | 42.50 | 180.90 | 1.43 | 2.81 |
| 97153 | 2019 | 79 | 0 | 20.18 | 20.18 | 16.21 | 42.16 | 89.51 | 109.00 | 343.60 | 2.09 | 4.44 |
| 97153 | 2020 | 90 | 0 | 20.18 | 20.18 | 30.30 | 31.63 | 121.82 | 56.80 | 503.70 | 1.57 | 6.04 |
| 97153 | 2021 | 405 | 0 | 20.18 | 20.18 | 36.22 | 38.71 | 109.05 | 91.90 | 440.50 | 1.92 | 5.40 |
| 97153 | 2022 | 1,390 | 0 | 20.18 | 20.18 | 42.20 | 42.51 | 95.85 | 110.70 | 375.00 | 2.11 | 4.75 |
| 97153 | 2023 | 3,571 | 0 | 20.18 | 20.18 | 32.04 | 32.37 | 66.20 | 60.40 | 228.10 | 1.60 | 3.28 |
| 97153 | 2024 | 4,117 | 0 | 20.18 | 20.18 | 37.50 | 37.50 | 74.20 | 85.80 | 267.70 | 1.86 | 3.68 |
| 97154 | 2021 | 63 | 0 | 6.72 | 6.72 | 0.66 | 10.20 | 16.17 | 51.70 | 140.70 | 1.52 | 2.41 |
| 97154 | 2022 | 158 | 0 | 6.72 | 6.72 | 10.08 | 10.08 | 17.75 | 50.00 | 164.20 | 1.50 | 2.64 |
| 97154 | 2023 | 255 | 0 | 6.72 | 6.72 | 10.95 | 10.95 | 20.09 | 62.90 | 199.00 | 1.63 | 2.99 |
| 97154 | 2024 | 111 | 0 | 6.72 | 6.72 | 10.41 | 10.41 | 25.74 | 55.00 | 283.10 | 1.55 | 3.83 |
| 97155 | 2019 | 34 | 0 | 20.18 | 20.18 | 41.87 | 41.87 | 81.01 | 107.50 | 301.50 | 2.07 | 4.01 |
| 97155 | 2020 | 67 | 0 | 20.18 | 20.18 | 34.44 | 34.44 | 103.39 | 70.70 | 412.40 | 1.71 | 5.12 |
| 97155 | 2021 | 317 | 0 | 20.18 | 20.18 | 28.02 | 28.02 | 55.21 | 38.80 | 173.60 | 1.39 | 2.74 |
| 97155 | 2022 | 798 | 0 | 20.18 | 20.18 | 29.75 | 29.75 | 55.58 | 47.50 | 175.50 | 1.47 | 2.75 |
| 97155 | 2023 | 1,787 | 0 | 20.18 | 20.18 | 28.86 | 28.86 | 48.38 | 43.00 | 139.80 | 1.43 | 2.40 |
| 97155 | 2024 | 2,291 | 0 | 20.18 | 20.18 | 34.36 | 34.36 | 58.35 | 70.30 | 189.20 | 1.70 | 2.89 |
| 97156 | 2023 | 49 | 0 | 20.18 | 20.18 | 31.29 | 31.29 | 60.05 | 55.10 | 197.60 | 1.55 | 2.98 |
| 97156 | 2024 | 121 | 0 | 20.18 | 20.18 | 34.26 | 34.26 | 56.47 | 69.80 | 179.80 | 1.70 | 2.80 |
| G0299 | 2018 | 44 | 0 | 9.14 | 12.81 | 14.31 | 27.44 | 83.37 | 200.30 | 812.10 | 3.00 | 9.12 |
| G0299 | 2019 | 71 | 0 | 9.14 | 12.81 | 2.54 | 15.71 | 69.03 | 71.80 | 655.30 | 1.72 | 7.55 |
| G0299 | 2020 | 85 | 0 | 9.14 | 12.81 | 15.43 | 23.53 | 85.26 | 157.40 | 832.80 | 2.57 | 9.33 |
| G0299 | 2021 | 94 | 0 | 9.14 | 12.81 | 8.30 | 25.22 | 94.86 | 175.90 | 937.90 | 2.76 | 10.38 |
| G0299 | 2022 | 58 | 0 | 9.14 | 12.81 | 14.66 | 35.64 | 93.30 | 290.00 | 920.80 | 3.90 | 10.21 |
| G0299 | 2023 | 46 | 0 | 9.14 | 12.81 | 29.22 | 29.22 | 103.16 | 219.60 | 1,028.60 | 3.20 | 11.29 |
| G0299 | 2024 | 58 | 0 | 12.81 | 12.81 | 22.86 | 26.89 | 99.18 | 109.90 | 674.30 | 2.10 | 7.74 |
| H2011 | 2018 | 178 | 0 | 40.58 | 40.58 | 9.73 | 113.14 | 236.80 | 178.80 | 483.50 | 2.79 | 5.84 |
| H2011 | 2019 | 194 | 0 | 40.58 | 40.58 | 12.77 | 69.86 | 131.78 | 72.10 | 224.70 | 1.72 | 3.25 |
| H2011 | 2020 | 155 | 0 | 40.58 | 40.58 | 47.90 | 73.98 | 141.53 | 82.30 | 248.80 | 1.82 | 3.49 |
| H2011 | 2021 | 369 | 0 | 40.58 | 40.58 | 63.19 | 76.13 | 129.47 | 87.60 | 219.00 | 1.88 | 3.19 |
| H2011 | 2022 | 346 | 0 | 40.58 | 40.58 | 44.53 | 63.87 | 140.17 | 57.40 | 245.40 | 1.57 | 3.45 |
| H2011 | 2023 | 441 | 0 | 40.58 | 40.58 | 28.59 | 72.37 | 169.48 | 78.30 | 317.60 | 1.78 | 4.18 |
| H2011 | 2024 | 385 | 0 | 40.58 | 40.58 | 75.77 | 78.26 | 205.22 | 92.80 | 405.70 | 1.93 | 5.06 |
| H2014 | 2018 | 277 | 0 | 14.25 | 14.25 | 30.63 | 30.63 | 58.18 | 114.90 | 308.30 | 2.15 | 4.08 |
| H2014 | 2019 | 277 | 0 | 14.25 | 14.25 | 34.29 | 35.78 | 62.67 | 151.10 | 339.80 | 2.51 | 4.40 |
| H2014 | 2020 | 571 | 0 | 14.25 | 14.25 | 24.17 | 24.23 | 62.10 | 70.00 | 335.80 | 1.70 | 4.36 |
| H2014 | 2021 | 2,345 | 0 | 14.25 | 14.25 | 27.69 | 27.86 | 73.33 | 95.50 | 414.60 | 1.96 | 5.15 |
| H2014 | 2022 | 2,393 | 0 | 14.25 | 14.25 | 29.48 | 29.74 | 82.31 | 108.70 | 477.60 | 2.09 | 5.78 |
| H2014 | 2023 | 2,468 | 0 | 14.25 | 14.25 | 30.89 | 31.71 | 100.32 | 122.50 | 604.00 | 2.23 | 7.04 |
| H2014 | 2024 | 2,214 | 0 | 14.25 | 14.25 | 30.12 | 30.56 | 108.35 | 114.50 | 660.30 | 2.14 | 7.60 |
| H2015 | 2018 | 1,663 | 0 | 4.55 | 17.17 | 71.51 | 71.51 | 272.42 | 1,471.70 | 5,887.20 | 15.72 | 59.87 |
| H2015 | 2019 | 1,701 | 0 | 4.55 | 17.17 | 71.08 | 71.74 | 233.35 | 1,476.80 | 5,028.50 | 15.77 | 51.29 |
| H2015 | 2020 | 1,780 | 0 | 4.55 | 17.17 | 71.71 | 72.25 | 184.34 | 1,487.90 | 3,951.40 | 15.88 | 40.51 |
| H2015 | 2021 | 2,140 | 0 | 4.55 | 17.17 | 51.26 | 60.00 | 175.68 | 1,218.70 | 3,761.00 | 13.19 | 38.61 |
| H2015 | 2022 | 2,272 | 0 | 4.55 | 17.17 | 51.07 | 58.82 | 175.60 | 1,192.70 | 3,759.30 | 12.93 | 38.59 |
| H2015 | 2023 | 1,584 | 0 | 4.55 | 17.17 | 52.18 | 53.61 | 149.74 | 1,078.20 | 3,191.10 | 11.78 | 32.91 |
| H2015 | 2024 | 908 | 0 | 4.55 | 17.17 | 39.95 | 43.75 | 123.00 | 861.60 | 2,603.30 | 9.62 | 27.03 |
| H2017 | 2018 | 1,089 | 0 | 19.12 | 19.12 | 65.21 | 67.14 | 145.95 | 251.20 | 663.30 | 3.51 | 7.63 |
| H2017 | 2019 | 1,204 | 0 | 19.12 | 19.12 | 54.88 | 55.74 | 132.97 | 191.50 | 595.50 | 2.92 | 6.95 |
| H2017 | 2020 | 1,658 | 0 | 19.12 | 19.12 | 43.88 | 44.51 | 111.92 | 132.80 | 485.40 | 2.33 | 5.85 |
| H2017 | 2021 | 3,144 | 0 | 19.12 | 19.12 | 51.39 | 53.27 | 113.25 | 178.60 | 492.30 | 2.79 | 5.92 |
| H2017 | 2022 | 3,346 | 0 | 19.12 | 19.12 | 57.61 | 60.38 | 128.87 | 215.80 | 574.00 | 3.16 | 6.74 |
| H2017 | 2023 | 3,747 | 0 | 19.12 | 19.12 | 52.64 | 64.85 | 150.10 | 239.20 | 685.00 | 3.39 | 7.85 |
| H2017 | 2024 | 3,366 | 0 | 19.12 | 19.12 | 52.03 | 63.50 | 159.36 | 232.10 | 733.50 | 3.32 | 8.33 |
| S5100 | 2018 | 56 | 0 | 3.45 | 11.58 | 55.69 | 55.69 | 63.74 | 1,514.30 | 1,747.60 | 16.14 | 18.48 |
| S5100 | 2019 | 55 | 0 | 3.45 | 11.58 | 57.15 | 57.59 | 66.44 | 1,569.30 | 1,825.90 | 16.69 | 19.26 |
| S5100 | 2020 | 197 | 0 | 3.45 | 11.58 | 28.94 | 33.28 | 64.89 | 864.60 | 1,781.00 | 9.65 | 18.81 |
| S5100 | 2021 | 481 | 0 | 3.45 | 11.58 | 46.99 | 46.99 | 79.79 | 1,261.90 | 2,212.60 | 13.62 | 23.13 |
| S5100 | 2022 | 424 | 0 | 3.45 | 11.58 | 62.91 | 62.91 | 84.30 | 1,723.60 | 2,343.40 | 18.24 | 24.43 |
| S5100 | 2023 | 428 | 0 | 3.45 | 11.58 | 77.81 | 77.81 | 84.27 | 2,155.40 | 2,342.60 | 22.55 | 24.43 |
| S5100 | 2024 | 386 | 0 | 4.53 | 11.58 | 82.57 | 82.57 | 107.15 | 1,722.60 | 2,265.30 | 18.23 | 23.65 |
| S5120 | 2020 | 35 | 0 | 3.76 | 7.90 | 57.24 | 57.24 | 92.55 | 1,422.30 | 2,361.50 | 15.22 | 24.62 |
| S5120 | 2021 | 72 | 0 | 3.76 | 7.90 | 39.69 | 39.69 | 97.05 | 955.60 | 2,481.20 | 10.56 | 25.81 |
| S5120 | 2022 | 61 | 0 | 3.76 | 7.90 | 43.89 | 43.89 | 106.32 | 1,067.30 | 2,727.60 | 11.67 | 28.28 |
| S5120 | 2023 | 76 | 0 | 3.76 | 7.90 | 52.90 | 54.15 | 159.30 | 1,340.20 | 4,136.70 | 14.40 | 42.37 |
| S5120 | 2024 | 66 | 0 | 4.32 | 7.90 | 69.58 | 69.58 | 230.07 | 1,510.70 | 5,225.80 | 16.11 | 53.26 |
| S5130 | 2018 | 905 | 0 | 4.61 | 7.90 | 17.18 | 21.26 | 38.49 | 361.20 | 734.90 | 4.61 | 8.35 |
| S5130 | 2019 | 886 | 0 | 4.61 | 7.90 | 21.23 | 21.29 | 41.16 | 361.90 | 792.90 | 4.62 | 8.93 |
| S5130 | 2020 | 1,071 | 0 | 4.61 | 7.90 | 19.88 | 19.88 | 40.23 | 331.20 | 772.70 | 4.31 | 8.73 |
| S5130 | 2021 | 1,665 | 0 | 4.61 | 7.90 | 20.65 | 20.65 | 40.04 | 348.00 | 768.60 | 4.48 | 8.69 |
| S5130 | 2022 | 1,485 | 0 | 4.61 | 7.90 | 23.00 | 23.10 | 42.57 | 401.10 | 823.40 | 5.01 | 9.23 |
| S5130 | 2023 | 1,468 | 0 | 4.61 | 7.90 | 24.67 | 24.78 | 46.40 | 437.50 | 906.50 | 5.38 | 10.07 |
| S5130 | 2024 | 1,346 | 0 | 7.90 | 7.90 | 39.62 | 39.62 | 73.83 | 401.60 | 834.60 | 5.02 | 9.35 |
| S5135 | 2018 | 77 | 0 | 2.57 | 7.90 | 53.02 | 53.02 | 116.82 | 1,963.10 | 4,445.60 | 20.63 | 45.46 |
| S5135 | 2019 | 103 | 0 | 2.57 | 7.90 | 60.33 | 60.33 | 99.40 | 2,247.60 | 3,767.80 | 23.48 | 38.68 |
| S5135 | 2020 | 129 | 0 | 2.57 | 7.90 | 63.24 | 63.24 | 119.87 | 2,360.60 | 4,564.10 | 24.61 | 46.64 |
| S5135 | 2021 | 137 | 0 | 2.57 | 7.90 | 62.35 | 62.35 | 151.79 | 2,325.90 | 5,806.40 | 24.26 | 59.06 |
| S5135 | 2022 | 154 | 0 | 2.57 | 7.90 | 91.51 | 91.51 | 155.67 | 3,460.70 | 5,957.20 | 35.61 | 60.57 |
| S5135 | 2023 | 277 | 0 | 2.57 | 7.90 | 97.89 | 97.89 | 171.46 | 3,708.90 | 6,571.50 | 38.09 | 66.72 |
| S5135 | 2024 | 342 | 0 | 7.90 | 7.90 | 92.18 | 92.18 | 181.76 | 1,066.80 | 2,200.70 | 11.67 | 23.01 |
| S5150 | 2018 | 78 | 0 | 5.77 | 9.64 | 52.77 | 52.77 | 104.99 | 814.60 | 1,719.60 | 9.15 | 18.20 |
| S5150 | 2019 | 87 | 0 | 5.77 | 9.64 | 53.92 | 53.92 | 102.59 | 834.50 | 1,677.90 | 9.35 | 17.78 |
| S5150 | 2020 | 77 | 0 | 5.77 | 9.64 | 61.43 | 61.43 | 125.94 | 964.60 | 2,082.70 | 10.65 | 21.83 |
| S5150 | 2021 | 71 | 0 | 5.77 | 9.64 | 66.76 | 66.76 | 152.81 | 1,056.90 | 2,548.30 | 11.57 | 26.48 |
| S5150 | 2022 | 75 | 0 | 5.77 | 9.64 | 68.66 | 68.66 | 170.41 | 1,089.90 | 2,853.40 | 11.90 | 29.53 |
| S5150 | 2023 | 90 | 0 | 5.77 | 9.64 | 58.28 | 62.51 | 189.42 | 983.40 | 3,182.80 | 10.83 | 32.83 |
| S5150 | 2024 | 85 | 0 | 9.64 | 9.64 | 97.68 | 97.68 | 216.84 | 913.20 | 2,149.40 | 10.13 | 22.49 |
| T1002 | 2018 | 68 | 0 | 8.71 | 15.89 | 0.96 | 15.00 | 26.44 | 72.20 | 203.50 | 1.72 | 3.04 |
| T1002 | 2019 | 62 | 0 | 8.71 | 15.89 | 0.26 | 19.69 | 28.46 | 126.10 | 226.70 | 2.26 | 3.27 |
| T1002 | 2020 | 67 | 0 | 8.71 | 15.89 | 0.37 | 5.16 | 15.88 | -40.70 | 82.40 | 0.59 | 1.82 |
| T1002 | 2021 | 78 | 0 | 8.71 | 15.89 | 0.31 | 6.61 | 31.40 | -24.20 | 260.50 | 0.76 | 3.60 |
| T1002 | 2022 | 53 | 0 | 8.71 | 15.89 | 0.34 | 19.61 | 34.94 | 125.10 | 301.10 | 2.25 | 4.01 |
| T1002 | 2023 | 47 | 0 | 8.71 | 15.89 | 0.47 | 14.18 | 34.21 | 62.80 | 292.80 | 1.63 | 3.93 |
| T1002 | 2024 | 52 | 0 | 13.26 | 15.89 | 0.98 | 36.90 | 49.84 | 178.30 | 275.90 | 2.78 | 3.76 |
| T1003 | 2021 | 49 | 0 | 6.69 | 11.93 | 3.30 | 49.00 | 95.00 | 632.40 | 1,320.00 | 7.32 | 14.20 |
| T1003 | 2022 | 31 | 0 | 6.69 | 11.93 | 0.34 | 49.00 | 94.23 | 632.40 | 1,308.50 | 7.32 | 14.09 |
| T1016 | 2018 | 798 | 0 | 23.19 | 25.46 | 21.37 | 30.33 | 59.37 | 30.80 | 156.00 | 1.31 | 2.56 |
| T1016 | 2019 | 988 | 0 | 23.19 | 25.46 | 7.17 | 13.50 | 54.32 | -41.80 | 134.20 | 0.58 | 2.34 |
| T1016 | 2020 | 1,221 | 0 | 23.19 | 25.46 | 10.15 | 13.16 | 51.40 | -43.30 | 121.60 | 0.57 | 2.22 |
| T1016 | 2021 | 1,604 | 0 | 23.19 | 25.46 | 11.48 | 13.50 | 53.59 | -41.80 | 131.10 | 0.58 | 2.31 |
| T1016 | 2022 | 1,677 | 0 | 23.19 | 25.46 | 10.92 | 12.13 | 48.50 | -47.70 | 109.10 | 0.52 | 2.09 |
| T1016 | 2023 | 1,788 | 0 | 23.19 | 25.46 | 10.83 | 11.36 | 48.24 | -51.00 | 108.00 | 0.49 | 2.08 |
| T1016 | 2024 | 1,569 | 0 | 23.19 | 25.46 | 10.70 | 11.71 | 46.36 | -49.50 | 99.90 | 0.50 | 2.00 |
| T1017 | 2018 | 1,142 | 0 | 16.63 | 16.63 | 73.64 | 78.60 | 175.24 | 372.60 | 953.80 | 4.73 | 10.54 |
| T1017 | 2019 | 1,211 | 0 | 16.63 | 16.63 | 61.48 | 77.45 | 173.52 | 365.70 | 943.40 | 4.66 | 10.43 |
| T1017 | 2020 | 1,362 | 0 | 16.63 | 16.63 | 57.46 | 59.48 | 149.38 | 257.60 | 798.30 | 3.58 | 8.98 |
| T1017 | 2021 | 1,375 | 0 | 16.63 | 16.63 | 57.11 | 60.13 | 152.32 | 261.60 | 815.90 | 3.62 | 9.16 |
| T1017 | 2022 | 1,381 | 0 | 16.63 | 16.63 | 53.54 | 56.14 | 160.32 | 237.60 | 864.10 | 3.38 | 9.64 |
| T1017 | 2023 | 1,538 | 0 | 16.63 | 16.63 | 60.56 | 69.57 | 226.42 | 318.30 | 1,261.50 | 4.18 | 13.62 |
| T1017 | 2024 | 1,201 | 0 | 16.63 | 16.63 | 101.17 | 131.27 | 272.83 | 689.40 | 1,540.60 | 7.89 | 16.41 |
| T1019 | 2018 | 1,353 | 0 | 4.90 | 6.99 | 60.63 | 60.63 | 77.95 | 1,137.40 | 1,490.80 | 12.37 | 15.91 |
| T1019 | 2019 | 1,365 | 0 | 4.90 | 6.99 | 58.26 | 58.26 | 78.74 | 1,089.00 | 1,506.90 | 11.89 | 16.07 |
| T1019 | 2020 | 1,263 | 0 | 4.90 | 6.99 | 40.46 | 46.43 | 80.45 | 847.50 | 1,541.70 | 9.47 | 16.42 |
| T1019 | 2021 | 807 | 0 | 4.90 | 6.99 | 8.42 | 9.94 | 30.84 | 102.80 | 529.40 | 2.03 | 6.29 |
| T1019 | 2022 | 742 | 0 | 4.90 | 6.99 | 7.15 | 13.50 | 41.08 | 175.60 | 738.40 | 2.76 | 8.38 |
| T1019 | 2023 | 782 | 0 | 4.90 | 6.99 | 12.75 | 13.78 | 42.11 | 181.20 | 759.40 | 2.81 | 8.59 |
| T1019 | 2024 | 675 | 0 | 4.10 | 6.99 | 16.40 | 17.68 | 45.46 | 331.20 | 1,008.90 | 4.31 | 11.09 |

Rate sources used nationally: p50_per_line 22,177, p05_per_line_trimmed 7,266, published_MN 131, no_rate_bundled_or_zero_paid 115.

**Tests.** Every code carries a `personal_service` attribute: psychotherapy, E/M, prolonged services, evaluations, professional psychological testing, health-behavior, counseling, telehealth, nutrition and acupuncture must be delivered by the rendering clinician; technician, aide, personal-care, habilitation and other HCBS codes are billed under a supervising or agency NPI by design. Individual NPIs (NPPES entity type 1) are tested on personal-service hours only: `IMPOSSIBLE_BY_LINE_COUNT` when even the rate-free lower bound exceeds 24 hours per calendar day; `IMPOSSIBLE_CONSERVATIVE_RATE` when the conservative estimate exceeds 24; `IMPLAUSIBLE_OVER_16H`; `ELEVATED_OVER_12H`. Supervision-billable volume above 24 hours per day under one individual NPI is reported as `UMBRELLA_VOLUME` (tier B): it can be a legitimate agency structure or a ghost clinician, and only records can tell. Any NPI: `IMPOSSIBLE_PER_PATIENT` when conservative hours per patient exceed 24 per calendar day. Minnesota: `EXCEEDS_MN_DAILY_CAP` when conservative hours on capped EIDBI codes exceed `cap x patients x days`, i.e. more than every patient receiving the state's own daily maximum every day of the month (97153 and 0373T 8 h, 97155 6 h, 97154 4.5 h, 97156 4 h, 97151 8 h). Robust z-scores (median/MAD, 0.6745 scaling) are computed within state and NPPES taxonomy (state-only when fewer than 200 NPIs) and feed the ranking, never a label on their own.

**Results.** 2,661 rendering NPIs have at least one impossible month (1,904 impossible by line count alone, 1,699 with three or more impossible months), with $7,761.27M paid in those months; 613 of them are tier A (an individual whose impossible personal-service hours were billed by three or more different organizations in the same month, or an organization with more than 24 hours per patient per day); 0 Minnesota providers exceed the state's own daily cap allowance. The most common drivers are office E/M codes (99213, 99214) and psychotherapy (90837, 90791), which several states let clinics bill under a supervising physician's or psychologist's NPI; a single-organization impossibility is therefore tier B and reads as "verify the state's supervisory billing rule and pull records", not as a finding.

| tier | NPI-months | NPIs | $M |
|---|---|---|---|
| A | 5,922 | 449 | 1,428.31 |
| B | 22,562 | 2,379 | 3,649.08 |
| C | 146,487 | 15,056 | 8,488.74 |

**Denominator sensitivity.** Labels divide monthly hours by calendar days, the strictest physical bound. Dividing by Monday-to-Friday working days instead moves the counts as follows (individual NPIs, conservative personal-service hours):

| denominator | NPIs over 24 h/day | NPIs over 16 h/day |
|---|---|---|
| calendar days (used for labels) | 1,576 | 3,587 |
| working days (Mon to Fri) | 3,114 | 7,074 |

**Growth and concentration indicator.** Medicaid-only home and community-based billers (housing stabilization, EIDBI, personal care) never appear in the CMS enrollment files, so the network detector cannot see them, and services billed under the agency NPI are tested per patient. For every billing NPI and year the indicator records the dominant code, the share of dollars in it, dollars per patient-month, the year-over-year growth and whether the NPI was enumerated within three years. `GROWTH_ANOMALY` (tier C, informational) marks new NPIs with at least $500k in the year, 80 percent or more of dollars in one high-vector code, a first year at that size or three-fold growth, and dollars per patient-month in the top decile of their state and code. It is a queue for records review; many new providers grow quickly for legitimate reasons.

**Convention caveat.** In several states the T-MSIS rendering NPI is the supervising clinician or the group by convention, and telehealth and locum tenens arrangements can concentrate volume under one NPI legitimately. Every label here is a screening indicator to be checked against the state's supervisory-billing rules and the provider's records; none is a finding.

| label | NPI-months | NPIs | $M in flagged months |
|---|---|---|---|
| ELEVATED_OVER_12H | 123,560 | 14,076 | 5,107.08 |
| IMPOSSIBLE_BY_LINE_COUNT | 21,208 | 1,866 | 4,329.75 |
| IMPLAUSIBLE_OVER_16H | 16,972 | 2,902 | 1,195.24 |
| IMPOSSIBLE_CONSERVATIVE_RATE | 7,359 | 1,052 | 816.61 |
| UMBRELLA_VOLUME | 6,602 | 713 | 1,611.82 |
| IMPOSSIBLE_PER_PATIENT | 12 | 4 | 5.06 |

| state | NPIs with impossible months | $M |
|---|---|---|
| CA | 638 | 1,267.69 |
| LA | 234 | 674.35 |
| FL | 177 | 234.77 |
| IN | 160 | 2,356.96 |
| TX | 132 | 259.19 |
| NY | 121 | 561.02 |
| NV | 112 | 250.69 |
| KY | 93 | 209.13 |
| AZ | 89 | 260.26 |
| TN | 72 | 142.68 |
| VA | 70 | 101.80 |
| AL | 63 | 137.64 |

**Minnesota EIDBI, CTSS, HSS and PCA codes** (rendering NPIs, dollars, implied hours, rate source):

| code | NPIs | $M | implied hours (M) | rate source |
|---|---|---|---|---|
| H2015 | 358 | 730.30 | 10.63 | published_MN |
| T1019 | 179 | 685.39 | 24.51 | published_MN |
| H2014 | 644 | 266.18 | 4.67 | published_MN |
| 97153 | 2,089 | 62.14 | 0.77 | published_MN |
| 97155 | 902 | 19.47 | 0.24 | published_MN |
| 97151 | 25 | 1.23 | 0.00 | published_MN |
| 97154 | 266 | 0.67 | 0.01 | published_MN |
| 97156 | 48 | 0.49 | 0.01 | published_MN |

Tables: `d2_rate`, `d2_rate_validation`, `d2_implied`, `d2_npi_month`, `d2_scored`, `d2_top`; app rows in `flags` (detector D2). Code: `detectors/d2_impossible_days.py`.

## Detector 1: ghost networks

**In plain language.** This detector builds a network of 31,706 nursing home, home health and hospice enrollments linked by shared owners, managing employees, addresses, phones, faxes, authorised officials, EINs and mailing addresses, then splits it into 1,962 communities of two or more providers. Owner identities are merged conservatively, using record identifiers, exact keys and a probabilistic model that only links a pair when the match probability is at least 0.95 and a location field also agrees, and very large hubs such as national chains are held out so they do not absorb the graph. Each community is scored on structure (rapid incorporation bursts, address and phone sharing, owners tied to several members, share of very new entities), on market context, and on links to exclusion, revocation and termination lists, with 138 communities meeting the eligibility rules for the ranked list. Because the enrollment files only contain providers that are still enrolled, revoked providers cannot serve as held out labels, so only the structure-only score is tested against any label link: against a base rate of 0.370 it reaches 0.60 precision in the top 10 and 0.56 through the top 100, with the top-10 figure resting on ten items and not meaningful by itself. The top 200 is heavily concentrated in California, and the section states plainly that every ranked community is a candidate for records review, not a finding.


**Graph.** 31,706 enrollments (14,410 SNF, 11,494 HHA, 5,802 HOSPICE) and 466,715 owner or managing-employee rows. Nodes: providers, resolved owner persons (86,804) and organizations (18,936), building and suite-level addresses, NPPES phones, faxes, authorised officials, EINs, mailing addresses, secondary practice locations; CHOW buyer to seller edges. 270,399 nodes and 466,676 edges. 1,193 hub nodes (chains with 25+ facilities, buildings with 25+ tenants, phone numbers on 25+ records, and similar) are held out of component formation so national operators do not swallow the graph; shared buildings, mailing addresses and phones are down-weighted by 1/log2(1 + tenants).

**Identity resolution.** Owner persons are merged on the PECOS associate ID and on an exact key (last name, first three letters, ZIP5), then a Fellegi-Sunter model over six comparison fields (last name with Jaro-Winkler levels, first name with nickname and initial levels, middle initial, ZIP5/ZIP3, city, street number) is fitted by EM on 91,729 blocked candidate pairs (same state and last name, or same state, Soundex and first initial). Pairs are linked when the posterior match probability is at least 0.95 and at least one locational field agrees, so names alone never merge two people. EM fitted lambda = 0.0863, 24 pairs linked. Organizations merge on associate ID, on a normalized name (corporate suffixes stripped) plus state, and on token-set similarity of at least 94 within a state.

**Communities.** Connected components of the hub-free graph, with Leiden (RB configuration, resolution 1.0) applied to components above 120 providers: 1,962 communities with two or more providers.

**Features per community.** n_prov by type and distinct organizations; incorporation bursts over distinct organizations formed 2019 or later (most organizations incorporated inside any 90, 180 or 365 day window; NPPES enumeration date when the incorporation date is missing); for-profit share; share of members formed since 2021; largest number of members at one building and at one suite; phone, fax, authorised-official, mailing-address and EIN sharing; owners tied to three or more members; label links (member NPIs on LEIE, SAM, Medicare revocations, state exclusion lists, Medicaid for-cause terminations, NPI deactivations; owner-name links to LEIE and SAM at high (name + ZIP5) or medium (name + state) confidence); CMS Market Saturation providers per 10k FFS beneficiaries for the dominant county and service, as a robust z on the log scale across all counties; county moratorium flag; Medicaid 2024 and all-years dollars (billing NPI) and Medicare 2023 hospice/HHA payments (PAC PUF).

**Score.** Each feature is converted to a robust z (median/MAD, capped at 5): structure = 1.5 z(burst_90 over distinct organizations, bursts of three or more only) + 1.5 z(address share/n) + 1.0 z(owner_multi/n) + 1.5 z(new ratio) + 0.5 z(phone or official share/n) + 0.5 z(log size); the for-profit share is recorded as a feature but not scored, because nearly every hospice and home health agency in Los Angeles, Houston, Phoenix and Las Vegas is for-profit; context = 0.8 z(saturation) + 0.5 moratorium; labels = 2.0 excluded links (member NPI on LEIE or SAM, owner name on LEIE or SAM at high 1.0 or medium 0.5 confidence, same suite as an excluded or revoked entity 1.0, same building 0.5; cap 3) + 1.0 z(Medicaid for-cause terminations/n, bulk-coded states suppressed) + 1.0 revoked (cap 3) + 0.5 state exclusions (cap 3) + 0.3 deactivations (cap 3). Owner counts use ownership and managing-control roles only (5 percent direct or indirect owners, managing employees, operational control, administrators); boards, officers and trustees are recorded but not scored, so hospital systems with a shared board do not look like networks. Ranked list eligibility: no chain or private-equity owner (319 communities are scored but held out: consolidation is not a ghost network), at least three distinct organizations, at least one organization formed since 2021, and at least two independent evidence families (structure, label, context). Every ranked community is a referral candidate for records review, not a finding. 138 communities are eligible.

**Evaluation.** The CMS enrollment files only contain providers that are still enrolled, so Medicare revocations cannot be held out as labels (only 0.0000 of communities contain a member revoked or excluded in 2023 or 2024: the revoked ones have already left the file). The structure-only score, which uses no label information, is instead evaluated against any label link (member NPI on LEIE, SAM, the revoked list, a state exclusion list or a for-cause Medicaid termination; owner name on LEIE or SAM; address shared with an excluded or revoked entity). Base rate 0.370; precision at K of the structure-only score among communities of three or more distinct organizations, chains excluded: P@10 = 0.60 (one-sided binomial p = 0.120), P@25 = 0.56 (one-sided binomial p = 0.041), P@50 = 0.56 (one-sided binomial p = 0.005), P@100 = 0.56 (one-sided binomial p = 0.000), P@250 = 0.49 (one-sided binomial p = 0.000). Read this honestly: the top-10 figure is ten items and is not statistically meaningful on its own; the label set is incomplete (it cannot contain providers that have already left the enrollment file) and it overlaps the inputs of the full risk score, so only the structure-only score is evaluated against it. 71,964 addresses of LEIE-excluded entities and revoked organizations were indexed for the address test.

| state | communities in top 200 | providers | Medicaid 2024 $M |
|---|---|---|---|
| CA | 61 | 2,996 | 132.80 |
| TX | 15 | 887 | 236.80 |
| FL | 13 | 362 | 456.40 |
| OH | 7 | 291 | 143.20 |
| IL | 6 | 230 | 11.40 |
| MA | 4 | 119 | 18.40 |
| NV | 4 | 122 | 0.00 |
| CO | 3 | 121 | 2.20 |
| MI | 3 | 18 | 0.00 |
| AZ | 3 | 51 | 1.40 |

**Top 25.**

| cluster | n | hospice | HHA | SNF | city | score | burst90 | addr | owner_multi | phone | excl | revoked | Medicaid term | sat z | Medicaid 2024 $M | Medicare 2023 $M |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1-00001 | 3 | 0 | 3 | 0 | Van Nuys, CA | 18.67 | 3 | 1 | 1 | 2 | 1.50 | 0.00 | 0 | 1.20 | 0.00 | 0.00 |
| D1-00002 | 6 | 0 | 6 | 0 | Burbank, CA | 16.62 | 3 | 5 | 0 | 1 | 2.50 | 0.00 | 0 | 1.20 | 0.00 | 1.67 |
| D1-00003 | 35 | 5 | 30 | 0 | Glendale, CA | 14.76 | 8 | 5 | 3 | 3 | 10.50 | 0.00 | 0 | 1.20 | 0.01 | 12.80 |
| D1-00004 | 7 | 0 | 7 | 0 | Glendale, CA | 14.74 | 4 | 5 | 1 | 1 | 0.50 | 0.00 | 0 | 1.20 | 0.00 | 0.38 |
| D1-00005 | 33 | 6 | 27 | 0 | Glendale, CA | 14.64 | 7 | 10 | 0 | 3 | 8.00 | 0.00 | 0 | 1.20 | 0.05 | 14.01 |
| D1-00006 | 38 | 10 | 28 | 0 | Glendale, CA | 14.28 | 7 | 8 | 3 | 2 | 6.50 | 0.00 | 0 | 1.20 | 4.35 | 13.22 |
| D1-00007 | 22 | 5 | 17 | 0 | Glendale, CA | 13.66 | 3 | 7 | 3 | 2 | 7.00 | 0.00 | 0 | 1.20 | 0.00 | 9.53 |
| D1-00008 | 82 | 18 | 64 | 0 | Burbank, CA | 13.43 | 14 | 9 | 11 | 3 | 13.50 | 0.00 | 0 | 1.20 | 3.33 | 32.32 |
| D1-00009 | 37 | 8 | 27 | 2 | Burbank, CA | 13.42 | 5 | 10 | 4 | 3 | 3.50 | 0.00 | 0 | 1.20 | 0.00 | 7.39 |
| D1-00010 | 10 | 0 | 10 | 0 | Glendale, CA | 13.38 | 3 | 7 | 0 | 1 | 0.50 | 0.00 | 0 | 1.20 | 0.00 | 2.10 |
| D1-00011 | 104 | 36 | 68 | 0 | Van Nuys, CA | 13.32 | 23 | 10 | 13 | 2 | 27.00 | 0.00 | 0 | 1.20 | 0.53 | 49.97 |
| D1-00012 | 33 | 5 | 25 | 3 | Mission Hills, CA | 12.80 | 5 | 10 | 3 | 1 | 3.00 | 0.00 | 0 | 1.20 | 0.62 | 63.66 |
| D1-00013 | 93 | 17 | 76 | 0 | Van Nuys, CA | 12.65 | 13 | 17 | 7 | 2 | 14.00 | 0.00 | 0 | 1.20 | 1.13 | 66.34 |
| D1-00014 | 47 | 14 | 33 | 0 | Burbank, CA | 12.24 | 10 | 6 | 5 | 1 | 11.50 | 0.00 | 0 | 1.20 | 9.54 | 26.75 |
| D1-00015 | 45 | 12 | 33 | 0 | Northridge, CA | 12.20 | 7 | 9 | 3 | 1 | 5.00 | 0.50 | 0 | 1.20 | 2.66 | 19.50 |
| D1-00016 | 100 | 33 | 67 | 0 | Burbank, CA | 12.08 | 14 | 10 | 9 | 2 | 12.00 | 0.00 | 0 | 1.20 | 5.10 | 77.47 |
| D1-00017 | 180 | 53 | 121 | 6 | Van Nuys, CA | 11.87 | 25 | 18 | 22 | 3 | 41.00 | 0.00 | 0 | 1.20 | 2.76 | 92.29 |
| D1-00018 | 69 | 16 | 53 | 0 | Glendale, CA | 11.82 | 12 | 6 | 5 | 2 | 10.00 | 0.00 | 0 | 1.20 | 1.44 | 51.27 |
| D1-00019 | 42 | 32 | 10 | 0 | San Antonio, TX | 11.78 | 10 | 7 | 5 | 2 | 2.00 | 0.00 | 0 | 0.20 | 11.63 | 48.87 |
| D1-00020 | 23 | 1 | 22 | 0 | Burbank, CA | 11.71 | 4 | 5 | 3 | 1 | 2.50 | 0.00 | 0 | 1.20 | 0.02 | 12.50 |
| D1-00021 | 85 | 27 | 58 | 0 | Glendale, CA | 11.65 | 13 | 8 | 10 | 3 | 12.50 | 0.00 | 0 | 1.20 | 2.15 | 39.89 |
| D1-00022 | 57 | 18 | 39 | 0 | North Hollywood, CA | 11.51 | 8 | 7 | 5 | 2 | 9.00 | 0.00 | 0 | 1.20 | 0.86 | 43.82 |
| D1-00023 | 52 | 20 | 31 | 1 | Glendale, CA | 11.44 | 8 | 5 | 5 | 1 | 9.00 | 0.00 | 0 | 1.20 | 0.21 | 29.53 |
| D1-00024 | 87 | 1 | 2 | 84 | Fort Wayne, IN | 11.42 | 6 | 1 | 130 | 2 | 2.00 | 0.00 | 0 | 0.20 | 0.04 | 0.42 |
| D1-00025 | 23 | 13 | 10 | 0 | Houston, TX | 11.42 | 4 | 5 | 6 | 1 | 7.00 | 0.00 | 0 | -0.20 | 7.86 | 9.52 |

Tables: `clusters` (features, score, rank, summary, graph JSON), `cluster_members`, `d1_persons`, `d1_orgs`, `d1_providers`. Code: `detectors/d1_ghost_networks.py`.

## Detector 3: paid after a screening-trigger action

**In plain language.** This detector looks for Medicaid payments in service months after a provider identifier appeared on a federal or state list that should have triggered a state screening or termination check. It matches on the NPI itself, so the link is exact by identifier, and it counts each NPI-month once whether the NPI billed or rendered the service. Of 16,357 NPIs on a tier-A list with an effective date inside the 2018-01 to 2024-12 window, 391 had paid claims in later service months totalling $55.92M, and 197 were paid in six or more later months ($50.65M). The section is explicit that these are not improper payments: a Medicare revocation is not by itself a Medicaid payment bar, appeals and reinstatements exist, and some claims may have been recouped later. Rows where the listed name shares no token with the NPPES record are set aside as tier C and excluded from the headline (557 rows, $260.43M), administrative revocations are held as tier B, and the cross-state termination results (6,364 NPIs, $1,475.66M) are presented as a screening queue rather than a finding because state termination codes are uneven.


**Rule.** An NPI appears on a federal or state "must not be paid" list with an effective date, and Medicaid (T-MSIS provider spending, service months 2018-01 to 2024-12) shows paid claims in service months strictly after that month and, where the source gives one, before the window end (Medicare re-enrollment bar expiry, state reinstatement date). Dollars count each NPI-month once whether the NPI billed or rendered. Tier A grounds only: Medicare revocations under 42 CFR 424.535(a)(2),(3),(4),(5),(7),(8),(10),(12),(13),(14),(18),(19),(20),(22),(23); every OIG LEIE exclusion without a state waiver; California, New York and Texas Medicaid exclusion lists (rows carrying an NPI). Administrative revocations ((a)(1) noncompliance, (a)(6), (a)(9) alone, (a)(11), (a)(17), (a)(21)) are kept in the tables as tier B and excluded from the headline.

**Headline.** 16,357 NPIs are on a tier-A list with an effective date inside the data window; 391 of them have Medicaid claims with service months after the action, totalling $55.92M; 197 were paid in six or more months after the action ($50.65M). These are dollars paid after an action that should have triggered a state screening check under 42 CFR 455.436 (monthly LEIE, SAM and NPPES checks) and, for for-cause Medicare terminations and other states' terminations, a termination decision under 42 CFR 455.416. They are not "improper payments": a Medicare revocation is not by itself a Medicaid payment bar, appeals and reinstatements exist, and some payments may reflect claims that were later recouped. OIG's audit of providers terminated in one state and paid in others found $50.3M across 584 providers, so the order of magnitude is consistent.

| source | tier | NPIs paid after | $M after | median $ per NPI | max months |
|---|---|---|---|---|---|
| NPPES_DEACTIVATED | C | 511 | 231.20 | 5,352.00 | 84 |
| MEDICARE_REVOKED | A | 260 | 30.52 | 13,096.00 | 67 |
| MEDICARE_REVOKED | B | 62 | 24.11 | 25,525.00 | 84 |
| STATE_EXCL_CA | C | 14 | 23.38 | 27,660.00 | 46 |
| OIG_LEIE | A | 12 | 7.77 | 67,706.00 | 55 |
| STATE_EXCL_CA | A | 81 | 7.22 | 12,029.00 | 52 |
| TMSIS_DECEASED | B | 21 | 4.04 | 39,625.00 | 81 |
| STATE_EXCL_NY | A | 35 | 3.45 | 7,470.00 | 78 |
| MEDICARE_REVOKED | C | 14 | 3.44 | 7,029.00 | 33 |
| STATE_EXCL_KY | A | 25 | 2.71 | 16,320.00 | 41 |
| STATE_EXCL_TX | A | 6 | 2.33 | 54,286.00 | 33 |
| STATE_EXCL_TX | B | 3 | 2.28 | 90,573.00 | 25 |
| STATE_EXCL_IN | A | 4 | 2.19 | 78,698.00 | 54 |
| STATE_EXCL_WA | C | 1 | 1.68 | 1,677,349.00 | 28 |
| STATE_EXCL_ND | A | 1 | 1.51 | 1,506,469.00 | 11 |
| STATE_EXCL_WA | A | 6 | 1.11 | 68,330.00 | 83 |
| OIG_LEIE | C | 2 | 0.30 | 152,045.00 | 43 |
| STATE_EXCL_KY | C | 2 | 0.24 | 120,054.00 | 10 |
| STATE_EXCL_MO | A | 8 | 0.19 | 4,761.00 | 69 |
| STATE_EXCL_CO | A | 7 | 0.12 | 3,047.00 | 38 |
| SAM_OPM | B | 4 | 0.11 | 11,467.00 | 27 |
| STATE_EXCL_MD | A | 5 | 0.08 | 5,888.00 | 26 |
| STATE_EXCL_AZ | A | 2 | 0.06 | 31,240.00 | 2 |
| STATE_EXCL_SC | C | 2 | 0.06 | 28,649.00 | 4 |
| STATE_EXCL_SC | A | 8 | 0.05 | 1,342.00 | 32 |
| STATE_EXCL_CO | C | 1 | 0.05 | 47,488.00 | 1 |
| STATE_EXCL_NY | C | 5 | 0.04 | 6,519.00 | 3 |
| STATE_EXCL_MI | C | 1 | 0.04 | 38,205.00 | 3 |
| STATE_EXCL_TX | C | 1 | 0.01 | 13,635.00 | 7 |
| STATE_EXCL_MT | A | 1 | 0.00 | 100.00 | 1 |
| STATE_EXCL_MS | C | 1 | 0.00 | 0.00 | 8 |
| STATE_EXCL_AZ | C | 1 | 0.00 | 3,150.00 | 10 |
| STATE_EXCL_MI | A | 1 | 0.00 | 306.00 | 1 |
| STATE_EXCL_MS | A | 1 | 0.00 | 0.00 | 4 |
| STATE_EXCL_NH | A | 1 | 0.00 | 444.00 | 2 |
| SAM_OPM | C | 1 | 0.00 | 0.00 | 2 |

**Identity checks.** Every NPI on every list must pass the NPI check digit (Luhn with the 80840 prefix). Rows on any list whose name shares no token with the NPPES record for that NPI are set aside as tier C, whatever the source (the California list's provider-number field can carry an employer's NPI, and a revocation can name a practice rather than the individual; 557 such rows, $260.43M, are excluded from every number above). Texas lists everyone ever excluded, so its rows use the reinstatement or eligible-to-reapply date as the window end and pre-2018 rows without either are tier B.

**Match tiers.** Every event in this detector carries the NPI itself, so the match is exact by identifier; the tier records how far the identity could be verified against NPPES. Rows without an NPI on the source list are handled separately by the name-matching script (scripts/sam_match_claude.py) and never enter the headline. Counts are NPIs with Medicaid service months after the action, tier A and B lists combined, TMSIS terminations excluded.

| identity match | tier | NPIs paid after | $M after |
|---|---|---|---|
| exact_npi_name_conflict | C | 550 | 260.43 |
| exact_npi_name_verified | A | 427 | 59.28 |
| exact_npi_name_verified | B | 68 | 26.51 |

**File dates.** "Excluded but still enrolled" is often an artefact of a stale enrollment file, so the headline never relies on enrollment status: it counts paid service months in T-MSIS after the action. The enrollment-segment figures below are reported separately and carry the file's own dates.

| file | latest date in the file |
|---|---|
| T-MSIS provider spending, latest service month | 2024-12 |
| T-MSIS enrollment segments, latest segment start | 2024-12-31 |
| T-MSIS enrollment segments, latest dated segment end | 2026-12-31 |
| Medicare revocations, latest effective date | 2026-05-27 |
| OIG LEIE, latest exclusion date | 2026-08-20 |
| SAM.gov, latest active date | 2026-09-04 |
| State exclusion lists, latest action date | 2026-09-02 |
| NPPES, latest deactivation date | 2026-08-09 |

**Still enrolled.** 2,576 NPIs revoked by Medicare (tier A) or excluded by OIG still hold an active Medicaid enrollment segment (T-MSIS status 02-06) more than 90 days after the action.

| Medicaid state | NPIs |
|---|---|
| LA | 419 |
| TX | 327 |
| VA | 292 |
| ID | 261 |
| TN | 258 |
| CA | 257 |
| PA | 180 |
| RI | 176 |
| MI | 157 |
| GA | 120 |

**Deceased.** T-MSIS status 80 (provider deceased) is applied by some states to organizations and to old records, so the test is restricted to individual NPIs whose latest status in that state is 80 and whose record starts 2015 or later. Tier A additionally requires NPPES to show the NPI deactivated. Tier A: 0 NPIs, $0.00M paid after; tier B (no NPPES corroboration): 21 NPIs, $4.04M.

**Cross-state.** Terminated for cause in one state (T-MSIS status 60, 65, 66, 67, 70, 72, 75, 78, 81; termination is the final status in that state; individuals or organizations enrolled in three or fewer states, so national chains with one mis-coded segment are excluded) and active in another state more than 90 days later: 6,364 NPIs (16,309 state pairs), 210 of them also on a federal or state exclusion list, 2,982 with Medicaid dollars after the termination ($1,475.66M). T-MSIS termination codes are state-coded and uneven, so this list is ranked with federally corroborated NPIs first and is presented as a screening queue, not a finding.

| code | reason | NPIs | $M after |
|---|---|---|---|
| 70 | TERM - LICENSE REVOKED | 4,710 | 944.22 |
| 81 | TERM - STATE EXCLUSION/ DEBARMENT, ETC. | 943 | 420.49 |
| 78 | TERM - ONSITE REVIEW/ PROVIDER IS NO LONGER OPERATIONAL | 432 | 101.29 |
| 72 | TERM - MEDICARE/MEDICAID EXCLUSION | 217 | 4.94 |
| 60 | TERM - ABUSE OF BILLING PRIVILEGES | 60 | 0.25 |
| 65 | TERM - FALSE OR MISLEADING INFORMATION | 7 | 3.50 |
| 66 | TERM - FEDERAL EXCLUSION/ DEBARMENT, ETC. | 4 | 0.97 |
| 75 | TERM - MISUSE OF BILLING NUMBER | 2 | 0.00 |

**NPI deactivation.** 511 NPIs deactivated in NPPES show Medicaid paid claims in later service months ($231.20M). Reported as tier B because states carry legacy identifiers.

**Top 20 by dollars after the action (tier A lists).**

| NPI | name (NPPES) | type | lists | first action | Medicaid state | months paid after | first | last | $ after | name agrees |
|---|---|---|---|---|---|---|---|---|---|---|
| 1982736492 | WE CARE TRANSPORTATION | 2 | OIG_LEIE | 2010-01-20 |  | 31 | 2018-01 | 2020-07 | 4,441,513.00 | 1 |
| 1962546176 | MATIAS CLINICAL LABORATORY INC | 2 | MEDICARE_REVOKED | 2018-08-31 | MO | 44 | 2018-09 | 2022-04 | 3,846,471.00 | 1 |
| 1548629520 | EMPIRE MEDICAL LLC | 2 | MEDICARE_REVOKED,STATE_EXCL_MD | 2020-07-31 | DE | 9 | 2020-08 | 2021-04 | 2,389,353.00 | 1 |
| 1679896484 | BLAKES BLESSING HEALTH CARE INC. | 2 | STATE_EXCL_TX | 2022-01-19 | TX | 33 | 2022-02 | 2024-10 | 2,118,903.00 | 1 |
| 1225242985 | KIUP KIM | 1 | STATE_EXCL_CA | 2018-12-10 | AZ | 52 | 2019-01 | 2023-08 | 2,046,769.00 | 1 |
| 1619941614 | HISHAM SADEK | 1 | MEDICARE_REVOKED,STATE_EXCL_IN | 2015-07-15 | IL | 54 | 2020-05 | 2024-11 | 2,029,469.00 | 1 |
| 1861407637 | HEALTHSMART PACIFIC INC | 2 | OIG_LEIE | 2021-04-20 | MD | 34 | 2021-05 | 2024-02 | 1,639,221.00 | 1 |
| 1447440359 | DOYLE'S YELLOW CHECKER CAB, INC | 2 | STATE_EXCL_ND | 2024-01-24 | MN | 11 | 2024-02 | 2024-12 | 1,506,469.00 | 1 |
| 1215266267 | ADVANCED SPINE AND PAIN CENTERS, PLLC | 2 | MEDICARE_REVOKED | 2021-11-19 | MD | 23 | 2021-12 | 2023-10 | 1,327,755.00 | 1 |
| 1457414286 | DM OPTICAL INC | 2 | STATE_EXCL_NY | 2016-09-22 |  | 26 | 2018-01 | 2020-02 | 1,183,544.00 | 1 |
| 1194744185 | QUALITY HEALTHCARE MANAGEMENT INC | 2 | STATE_EXCL_KY | 2023-10-07 | RI | 14 | 2023-11 | 2024-12 | 1,092,507.00 | 1 |
| 1851726731 | INFINITY DIAGNOSTICS LABORATORY, INC | 2 | STATE_EXCL_NY,MEDICARE_REVOKED,STATE_EXCL_SC | 2022-10-31 | LA | 7 | 2022-11 | 2023-05 | 1,043,387.00 | 1 |
| 1891703922 | COMMUNITY CARE MEDICAL CLINICS INC | 2 | MEDICARE_REVOKED | 2020-03-02 | TX | 19 | 2021-04 | 2023-04 | 960,939.00 | 1 |
| 1871571406 | MOHAMED ASWAD | 1 | OIG_LEIE,MEDICARE_REVOKED | 2016-01-20 | AZ | 55 | 2018-01 | 2022-07 | 901,321.00 | 1 |
| 1407188543 | MERCRIS HOME HEALTH INC | 2 | MEDICARE_REVOKED | 2023-05-01 | TX | 17 | 2023-06 | 2024-10 | 899,287.00 | 1 |
| 1831547868 | SHANONE CHATMAN-ASHLEY | 1 | MEDICARE_REVOKED,OIG_LEIE | 2020-10-23 | LA | 38 | 2020-11 | 2023-12 | 883,542.00 | 1 |
| 1740478270 | FIRST IDEAL ENTERPRISES INC. | 2 | MEDICARE_REVOKED | 2018-10-01 | MI | 38 | 2018-11 | 2021-12 | 843,035.00 | 1 |
| 1518931856 | LINDA WARREN-WATSON | 1 | STATE_EXCL_CA | 2020-10-31 | CA | 16 | 2020-11 | 2022-06 | 828,250.00 | 1 |
| 1609064153 | QUEENS OPTOMETRIC CARE PLLC | 2 | MEDICARE_REVOKED | 2023-10-25 | NY | 11 | 2023-11 | 2024-09 | 777,235.00 | 1 |
| 1336486448 | QOL COMMUNICATION SERVICES, LLC | 2 | MEDICARE_REVOKED | 2024-06-12 | MD | 6 | 2024-07 | 2024-12 | 728,911.00 | 1 |

Tables: `d3_events`, `d3_paid_after`, `d3_enrolled_after`, `d3_crossstate`, `d3_npi`, `d3_top`; app rows in `flags` (detector D3). Code: `detectors/d3_revoked_but_paid.py`.

## Unified provider risk score

**In plain language.** This section combines the separate detectors into one row per provider identifier, assigning a tier, a score and written reasons. Tiers run from documented list actions with later paid service months, through physically impossible billing volume across multiple organizations, network structure with a list link, structure or single-organization volume, down to informational. The score starts at a tier base of 90, 75, 60, 45 or 25, adds 8 points for each extra strong finding that independently reached the same identifier up to 16 points, adds up to 9 points based on the log of dollars at risk, and is capped at 100. Dollars at risk come only from the detector that set the tier, are never summed and never taken from a weaker indicator, so a small documented-action case cannot be inflated past a larger one. Counts by tier are 391 identifiers and $56.96M at tier 1, 602 and $2,676.69M at tier 2, 6,096 and $1,058.33M at tier 3, 1,998 and $4,875.43M at tier 4, and 2,115 and $2,771.60M at tier 5, with no identifiers reached independently by two or more detectors, which the section notes is the strongest corroboration the pipeline can produce. Every row, including the top 25 listed, is a candidate for records review and not a finding.


**Hierarchy.** Every NPI any detector reached gets one row in `provider_risk` with a tier, a score and the reasons. Tier 1: on a tier-A federal or state list and Medicaid service months after the action. Tier 2: physically impossible personal-service volume billed by three or more organizations in a month, more than 24 hours per patient per day, or over Minnesota's own daily cap. Tier 3: member of an eligible provider community with a label link. Tier 4: structure only, or single-organization impossibility. Tier 5: informational. Score = tier base (90, 75, 60, 45, 25) + 8 per additional strong finding that independently reached the NPI (a tier-A list action, tier-A concurrent impossible volume, or a ranked community; cap 16) + min(9, log10 dollars at risk), capped at 100. Dollars at risk is the figure of the detector that set the tier (service months after the action for tier 1, paid in flagged months for tier 2, Medicaid 2024 for the community tiers), never a sum and never borrowed from a weaker indicator, so a single-organization volume flag cannot lift a small documented-action case above a large one. The county map sums each NPI once.

| tier | meaning | NPIs | $M at risk | reached by 2+ detectors |
|---|---|---|---|---|
| 1 | documented action, then payment | 391 | 56.96 | 0 |
| 2 | impossible volume with concurrency | 602 | 2,676.69 | 0 |
| 3 | network structure with a list link | 6,096 | 1,058.33 | 0 |
| 4 | structure or single-organization volume | 1,998 | 4,875.43 | 0 |
| 5 | informational | 2,115 | 2,771.60 | 0 |

0 NPIs were reached by two or more detectors independently; corroboration is the strongest signal the pipeline produces and it is weighted accordingly.

**Top 25 referral candidates.**

| rank | NPI | name | type | state | tier | score | detectors | $ at risk | reasons |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1982736492 | WE CARE TRANSPORTATION | 2 | KS | 1 | 96.60 | ['D3'] | 4,441,513.00 | Listed on the OIG exclusion list since January 20, 2010; Medicaid still paid claims in 31 later months, $4,441,513 in total |
| 2 | 1962546176 | MATIAS CLINICAL LABORATORY INC | 2 | CA | 1 | 96.60 | ['D3'] | 3,846,471.00 | Listed on the Medicare revocation list since August 31, 2018; Medicaid still paid claims in 44 later months, $3,846,471 in total |
| 3 | 1548629520 | EMPIRE MEDICAL LLC | 2 | DE | 1 | 96.40 | ['D3'] | 2,389,353.00 | Listed on the Medicare revocation list since July 31, 2020; Medicaid still paid claims in 9 later months, $2,389,353 in total |
| 4 | 1679896484 | BLAKES BLESSING HEALTH CARE INC. | 2 | TX | 1 | 96.30 | ['D3'] | 2,118,903.00 | Listed on the TX Medicaid exclusion list since January 19, 2022; Medicaid still paid claims in 33 later months, $2,118,903 in total |
| 5 | 1225242985 | KIUP KIM | 1 | AZ | 1 | 96.30 | ['D3'] | 2,046,769.00 | Listed on the CA Medicaid exclusion list since December 10, 2018; Medicaid still paid claims in 52 later months, $2,046,769 in total |
| 6 | 1619941614 | HISHAM SADEK | 1 | IL | 1 | 96.30 | ['D3', 'D2'] | 2,029,469.00 | Listed on the IN Medicaid exclusion list since July 15, 2015; Medicaid still paid claims in 54 later months, $2,029,469 in total |
| 7 | 1861407637 | HEALTHSMART PACIFIC INC | 2 | CA | 1 | 96.20 | ['D3'] | 1,639,221.00 | Listed on the OIG exclusion list since April 20, 2021; Medicaid still paid claims in 34 later months, $1,639,221 in total |
| 8 | 1447440359 | DOYLE'S YELLOW CHECKER CAB, INC | 2 | ND | 1 | 96.20 | ['D3'] | 1,506,469.00 | Listed on the ND Medicaid exclusion list since January 24, 2024; Medicaid still paid claims in 11 later months, $1,506,469 in total |
| 9 | 1215266267 | ADVANCED SPINE AND PAIN CENTERS, PLLC | 2 | VA | 1 | 96.10 | ['D3'] | 1,327,754.00 | Listed on the Medicare revocation list since November 19, 2021; Medicaid still paid claims in 23 later months, $1,327,754 in total |
| 10 | 1457414286 | DM OPTICAL INC | 2 | NY | 1 | 96.10 | ['D3'] | 1,183,544.00 | Listed on the NY Medicaid exclusion list since September 22, 2016; Medicaid still paid claims in 26 later months, $1,183,544 in total |
| 11 | 1194744185 | QUALITY HEALTHCARE MANAGEMENT INC | 2 | NY | 1 | 96.00 | ['D3'] | 1,092,507.00 | Listed on the KY Medicaid exclusion list since October 7, 2023; Medicaid still paid claims in 14 later months, $1,092,507 in total |
| 12 | 1780780031 | DAVID SMITH | 1 | NC | 1 | 96.00 | ['D3'] | 1,063,751.00 | Listed on the SC Medicaid exclusion list and the Medicare revocation list since August 30, 2021; Medicaid still paid claims in 7 later months, $1,063,751 in total |
| 13 | 1851726731 | INFINITY DIAGNOSTICS LABORATORY, INC | 2 | NJ | 1 | 96.00 | ['D3'] | 1,043,387.00 | Listed on the NY Medicaid exclusion list and the Medicare revocation list since October 31, 2022; Medicaid still paid claims in 7 later months, $1,043,387 in total |
| 14 | 1891703922 | COMMUNITY CARE MEDICAL CLINICS INC | 2 | TX | 1 | 96.00 | ['D3'] | 960,939.00 | Listed on the Medicare revocation list since March 2, 2020; Medicaid still paid claims in 19 later months, $960,939 in total |
| 15 | 1871571406 | MOHAMED ASWAD | 1 | NM | 1 | 96.00 | ['D3'] | 901,321.00 | Listed on the OIG exclusion list since January 20, 2016; Medicaid still paid claims in 55 later months, $901,321 in total |
| 16 | 1407188543 | MERCRIS HOME HEALTH INC | 2 | TX | 1 | 96.00 | ['D3'] | 899,287.00 | Listed on the Medicare revocation list since May 1, 2023; Medicaid still paid claims in 17 later months, $899,287 in total |
| 17 | 1831547868 | SHANONE CHATMAN-ASHLEY | 1 | LA | 1 | 95.90 | ['D3'] | 883,542.00 | Listed on the Medicare revocation list since October 23, 2020; Medicaid still paid claims in 38 later months, $883,542 in total |
| 18 | 1740478270 | FIRST IDEAL ENTERPRISES INC. | 2 | MI | 1 | 95.90 | ['D3'] | 843,035.00 | Listed on the Medicare revocation list since October 1, 2018; Medicaid still paid claims in 38 later months, $843,035 in total |
| 19 | 1518931856 | LINDA WARREN-WATSON | 1 | CA | 1 | 95.90 | ['D3'] | 828,250.00 | Listed on the CA Medicaid exclusion list since October 31, 2020; Medicaid still paid claims in 16 later months, $828,250 in total |
| 20 | 1609064153 | QUEENS OPTOMETRIC CARE PLLC | 2 | NY | 1 | 95.90 | ['D3'] | 777,235.00 | Listed on the Medicare revocation list since October 25, 2023; Medicaid still paid claims in 11 later months, $777,235 in total |
| 21 | 1336486448 | QOL COMMUNICATION SERVICES, LLC | 2 | MD | 1 | 95.90 | ['D3'] | 728,911.00 | Listed on the Medicare revocation list since June 12, 2024; Medicaid still paid claims in 6 later months, $728,911 in total |
| 22 | 1730473745 | MADISON PRIMARY CARE, LLC | 2 | KY | 1 | 95.80 | ['D3'] | 612,164.00 | Listed on the KY Medicaid exclusion list since April 20, 2021; Medicaid still paid claims in 40 later months, $612,164 in total |
| 23 | 1851702971 | NEW WAVE DIAGNOSTIC RADIOLOGY PLLC | 2 | NY | 1 | 95.80 | ['D3'] | 580,310.00 | Listed on the Medicare revocation list since August 19, 2022; Medicaid still paid claims in 27 later months, $580,310 in total |
| 24 | 1831107150 | RICHARD GOLEMBIOSKI | 1 | NJ | 1 | 95.80 | ['D3'] | 565,117.00 | Listed on the Medicare revocation list since November 4, 2020; Medicaid still paid claims in 48 later months, $565,117 in total |
| 25 | 1447395736 | BHUPINDER BHANDARI MD INC | 2 | CA | 1 | 95.70 | ['D3'] | 526,010.00 | Listed on the Medicare revocation list and the CA Medicaid exclusion list since November 23, 2022; Medicaid still paid claims in 9 later months, $526,010 in total |

Table: `provider_risk`. Code: `detectors/risk_score.py`. Every row is a referral candidate for records review, not a finding.

## Entity resolution adjudication

**In plain language.** This section checks the rule that decides when two owner records refer to the same person. A sample of 224 owner-person pairs was reviewed: every pair the rule accepted, meaning a match probability of at least 0.95 plus agreement on location and on a real name, along with the strongest pairs the rule turned down. A language model was given the same six fields the statistical matching model uses and asked to judge each pair independently, and its verdict was compared to the rule's final decision rather than to the raw probability, because that probability is unreliable for pairs that share only a city, a state and a first initial. The model agreed with the applied decision on 94.6% of all pairs and on 100.0% of the 196 pairs it rated high confidence; among the 200 rejected pairs it called about 1% the same person, and among the 24 merged pairs it called 58% the same person. These judgments are stored for human review and do not alter the graph on their own, and pairs where the model confidently says same but the rule said different form the queue for the next round of matcher tuning.


**Method.** 224 owner-person pairs were adjudicated: every pair the applied merge rule accepted (posterior at or above 0.95 plus a locational agreement and real name agreement) and the highest-posterior pairs it rejected. They were judged by Claude (claude-opus-5, structured output, Message Batches API, batch msgbatch_01We4rtEVHfz66XGSusawhHA) from the same six fields the EM model sees. The model's verdict is compared with the applied decision, not the raw posterior: the EM posterior alone is miscalibrated for pairs that agree only on city, state and a name initial, which is exactly why the rule requires a locational agreement.

Agreement with the applied merge decision: 94.6% over all adjudicated pairs, 100.0% over the 196 pairs the model rated high confidence.

| pairs | pairs | model says same | EM says same |
|---|---|---|---|
| rejected by the rule | 200 | 0.01 | 0.00 |
| merged by the rule | 24 | 0.58 | 1.00 |

Adjudications are stored in `d1_er_adjudications` for human review and do not change the graph automatically; pairs where the model says same with high confidence and the EM said different are the review queue for the next matcher iteration.

## Network factor desk

**In plain language.** This desk profiles every provider network that has at least three providers, scoring 30 factors grouped into seven families: formation timing, ownership, addresses and contacts, public list exposure, market conditions, money, and identity and enrollment. Each factor is reported three ways: its raw value, its percentile among all networks measured in the risky direction, and a robust z-score. Six of the factors track rate of change, and they are clipped, converted to robust z-scores, and averaged into a single momentum number with an outlook label of rising fast, rising, steady, or cooling. Across the 914 networks with an outlook, 388 are steady, 276 rising, 151 cooling, and 99 rising fast; among the top ten ranked networks shown, momentum z-scores run from 0.25 to 1.66. The section states that momentum is indicative only, that no outcome data yet exist to calibrate it, and that it never changes a network's tier."}


**What it is.** For every provider network with three or more providers, the desk measures 30 factors in seven families: formation timing (incorporation bursts, share of new companies, formation velocity, company age), ownership (owners on several providers, concentration, managing-employee share, association-date bursts, changes of ownership), addresses and contacts (shared buildings, suites, phones, officials, addresses of revoked companies, office plazas), list exposure (members and owners on public lists), market (county saturation, its three-year trend, moratorium history), money (Medicaid 2024, Medicare 2023, Medicaid growth 2022 to 2024, dollar concentration, billing share) and identity and enrollment (NPI issued close to incorporation, deactivated NPIs, multi-state footprint, chain share). Each factor carries its value, its percentile among all such networks in the risky direction, and a robust z-score.

**Momentum.** Six rate-of-change factors (formation velocity, new-company share, Medicaid growth, owner association bursts, saturation trend and ownership changes) are averaged as clipped robust z-scores into one momentum number with an outlook label: rising fast (z at or above 1), rising (0.3 to 1), steady, cooling. This is an indicative reading of what is moving, not a validated forecast; no outcome data exist yet to calibrate it, and it never changes a tier.

Outlook across networks: steady 388, rising 276, cooling 151, rising fast 99.

| network | rank | momentum z | outlook |
|---|---|---|---|
| D1-00001 | 1 | 0.25 | steady |
| D1-00002 | 2 | 0.41 | rising |
| D1-00003 | 3 | 1.28 | rising fast |
| D1-00004 | 4 | 0.76 | rising |
| D1-00005 | 5 | 1.15 | rising fast |
| D1-00006 | 6 | 1.57 | rising fast |
| D1-00007 | 7 | 1.25 | rising fast |
| D1-00008 | 8 | 1.66 | rising fast |
| D1-00009 | 9 | 0.71 | rising |
| D1-00010 | 10 | 0.79 | rising |
