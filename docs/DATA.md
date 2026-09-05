# Verity data dictionary and join keys

All files are public. Provider identifiers: NPI (10 digits) is the universal join key. CCN (CMS Certification Number, 6 chars) identifies facilities (hospices, HHAs, SNFs, hospitals). Enrollment ID (PECOS) and Associate ID link enrollments to owners.

## cms_enrollment (data.cms.gov, snapshots July/Aug 2026)
- `Hospice_Enrollments`, `HHA_Enrollments`, `SNF_Enrollments`, `Hospital_Enrollments`, `FQHC_Enrollments`, `RHC_Enrollments`: one row per enrollment. Keys: ENROLLMENT ID, NPI, CCN, ASSOCIATE ID. Fields: organization name, doing-business-as, incorporation date and state, proprietary vs non-profit, address, city, state, zip. Incorporation date bursts and shared addresses feed the ghost-network detector.
- `*_All_Owners`: one row per owner per enrollment. Keys: ENROLLMENT ID, ASSOCIATE ID (owner), ASSOCIATE ID (enrollment). Fields: owner type (individual/organization), role (5% direct owner, indirect owner, managing employee, officer, director), ownership percentage, association date, owner name, address, and for organizations the corporation/LLC type. This is the graph: enrollment nodes to owner nodes.
- `*_CHOW` and `*_CHOW_Owners`: changes of ownership with buyer and seller. Churn feature.
- `PPEF_Enrollment_Extract`: Medicare FFS Public Provider Enrollment, every enrolled provider and supplier (individual and org) with NPI, PECOS ID, specialty, state, reassignment counts.
- `OrderReferring`: NPIs allowed to order and refer (Part B, DME, HHA, PMD). Referrers who are not on this list but appear in DME referring files are a flag.
- `revalidation_*`: revalidation due dates and group reassignments (which individuals reassign benefits to which groups: another graph edge).
- `OptOut`: providers who opted out of Medicare.
- `Revocation_Extract`: Revoked Medicare Providers and Suppliers. NPI, name, revocation effective date, reason (42 CFR 424.535(a)(n)), re-enrollment bar end date. Ground-truth labels for evaluation.
- `Chain_Performance`: nursing home chains (owner to facility mapping at chain level).

## cms_program_integrity
- `MSAT..._State_County`: Market Saturation and Utilization by state, county, and service type (hospice, home health, ambulance, IDTF, PT/OT, etc.). Fields: number of providers, users, beneficiaries, providers per 10K FFS beneficiaries, average spend per user, and a `moratorium` flag. Baseline for "too many hospices for this county."
- `MSAT_CBSA`: same by metro area.

## cms_pos
- `POS_iQIES`, `Hospital_and_other`: Provider of Services, every certified facility with CCN, ownership type, bed counts, certification and termination dates, address. `Clia`: clinical laboratories.

## cms_utilization
- `Physician_Other_Practitioners/` by Provider and Service (NPI x HCPCS x place of service; services, beneficiaries, submitted charge, allowed, paid, standardized) and by Provider (NPI totals, beneficiary demographics, risk score). 2013 to 2024.
- `Part_D_Prescribers/` by Provider and Drug (NPI x brand/generic; claims, 30-day fills, cost, beneficiaries) and by Provider. 2013 to 2024.
- `Durable_Medical_Equipment_Devices_Supplies/` by Referring Provider and Service (the telehealth order-mill fingerprint: referrer NPI x HCPCS x supplier rental/purchase), by Referring Provider, by Supplier and Service, by Supplier. 2014 to 2024.
- `Inpatient_Hospitals/` and `Outpatient_Hospitals/` by Provider and Service (CCN x DRG or APC). Skin substitutes live in outpatient HCPCS Q41xx to Q42xx and physician files.
- `post_acute/`: PAC PUF for hospice, HHA, SNF, IRF, LTCH by geography and provider (`_main_`) and by service (`_supp_`). Hospice main file has per-provider beneficiaries, days, payments, average length of stay, percent of stays over 180 days, live discharge rates, site of service mix. 2014 to 2024. Core of the hospice SSVI reproduction.

## medicaid_tmsis (opendata.hhs.gov)
- `medicaid-provider-spending.parquet` (3.07 GB, 238,015,729 rows, verified): columns BILLING_PROVIDER_NPI_NUM, SERVICING_PROVIDER_NPI_NUM, HCPCS_CODE, CLAIM_FROM_MONTH, TOTAL_PATIENTS, TOTAL_CLAIM_LINES, TOTAL_PAID. No state column: join to enrollment segments on NPI for STATE_CD. NPI x HCPCS x month, 2018 to 2024, with claim count, beneficiary count, and paid amount, across FFS, managed care, and CHIP, for every state. 227M rows. Use DuckDB, filter first. Convert time-based codes (97153, 97155, H2014, H2015, H2019, T1019, S5125, 90837, 90834, 99xxx) to implied hours per rendering NPI per day for the impossible-days detector.
- `medicaid-provider-spending-ndc.parquet` (21,515,000 rows): BILLING_PROVIDER_NPI_NUM, PRESCRIBING_PROVIDER_NPI_NUM, NATIONAL_DRUG_CODE, CLAIM_FROM_MONTH, TOTAL_UNIQUE_BENEFICIARIES, TOTAL_CLAIM_LINES, TOTAL_PAID.
- `medicaid-provider-enrollment-segments.parquet` (65,970,112 rows): columns NPI, STATE_CD, ENRL_START_DT, ENRL_END_DT, ENRL_STATUS_CD/DESC, ENRL_PLAN_CD/DESC, PRVDR_TYPE/DESC and more. T-MSIS provider enrollment views for every state: NPI, state, enrollment type, specialty, begin and end dates. Join to Revocation_Extract and LEIE for the revoked-in-Medicare, alive-in-Medicaid detector.
- `medicare-revoked-providers-and-suppliers.parquet`: HHS mirror of the CMS revoked list.

## oig_leie
- `LEIE_UPDATED.csv`: every excluded individual and entity: name, DOB, NPI (often blank for older rows), UPIN, address, exclusion type (1128(a)(1) etc.), exclusion date, reinstatement date. Match on NPI first, then name plus state plus DOB.

## nppes
- `NPPES_Data_Dissemination_August_2026_V2.zip` (1.1 GB): every NPI ever issued: entity type, names, practice and mailing address, phone, taxonomy codes, enumeration and deactivation dates, authorized official. Address and phone are shared-entity edges. Weekly deltas are on the NPPES site if needed.
- `NPPES_Deactivated_NPI_Report`: NPIs deactivated and when. A deactivated NPI still billing Medicaid is a flag.

## open_payments
- Summary files (small): payments by covered recipient for all years, by reporting organization.
- `OP_DTL_OWNRSHP_PGYR2025`: physician ownership interests in manufacturers and GPOs.
- `OP_DTL_GNRL_PGYR2024/2025` (large): every general payment from manufacturers to physicians and hospitals. Join on Covered_Recipient_NPI. Skin-substitute manufacturers to wound-care billers.

## openfda
- `drug_shortages.json`, `drug-enforcement` (recalls), `drug-ndc` (NDC directory, joins to the Medicaid NDC file).

## care_compare (data.cms.gov/provider-data)
- Hospice general information and provider data (CCN, ownership type, certification date, quality measures, CAHPS), home health agencies, hospital general information, nursing home provider info, LTCH, IRF, HHVBP, VA facilities. Join to enrollment on CCN.

## Detector recipes (see scripts/quickstart.py)
1. Ghost networks: enrollments + all owners + NPPES address/phone + CHOW, build the graph, connected components, features: shared owners across N new entities, incorporation burst window, address shared with a revoked or excluded entity, county providers per 10K vs Market Saturation, hospice PAC PUF long-stay and live-discharge rates.
2. Impossible days: Medicaid parquet filtered to time-based HCPCS, implied hours per NPI per day, robust z-scores by state and code, beneficiary growth.
3. Revoked but paid: Revocation_Extract + LEIE + NPPES deactivations joined to Medicaid enrollment segments and Medicaid spending after the revocation date.

## Conventions added 2026-09-05

- `data/clean/<subdir>/` holds UTF-8 copies of every CSV under `cms_enrollment`, `cms_program_integrity`, `oig_leie`, `care_compare`,
  `cms_pos`. CMS publishes these as UTF-8 with a handful of stray Windows-1252 bytes (en dashes, accented names), which DuckDB rejects
  under both `utf-8` and `latin-1`. `ingest/00_clean_encoding.py` re-decodes only the bad lines and symlinks files that were already clean.
  The warehouse SQL and the Supabase sync read from `data/clean/`.
- `data/std/` has symlinks with the short names the build playbook uses (`hospice_enroll.csv`, `hha_owners.csv`, `leie.csv`,
  `medicaid-provider-spending.parquet`, ...). The organized layout above stays the source of truth.
- NPPES is extracted next to the zip: `npidata_pfile_20050523-20260809.csv` (11.6 GB), `othername_pfile`, `pl_pfile`, and the
  deactivated-NPI xlsx.
- Incorporation dates in the enrollment files are MM/DD/YYYY; about a quarter of hospices, a quarter of HHAs and 40% of SNFs have no
  incorporation date at all (government and older non-profit providers), so it is null, not unparsed.
- T-MSIS enrollment segments use `0001-01-01`, `1900-01-01` and `1970-01-01` as placeholder start dates and `9999-12-30` as an
  open-ended end date; the warehouse drops the placeholder starts and treats the far-future end as null.

## sam_exclusions (SAM.gov, via SAM_API_KEY)
- `SAM_Exclusions_Public_Extract_V2_<yyddd>.CSV`: every active and inactive exclusion in SAM (168k rows on 2026-09-05). Columns: Classification (Individual, Firm, Special Entity Designation, Vessel), Name, First/Middle/Last, Address, City, State / Province, Zip Code, Unique Entity ID, Exclusion Program (Reciprocal, NonProcurement, Procurement), Excluding Agency (HHS 70k, OFAC 42k, OPM 41k, DOJ, HUD, EPA, ...), CT Code, Exclusion Type (Ineligible (Proceedings Completed), Prohibition/Restriction, ...), Active Date, Termination Date (2227-xx-xx = indefinite), Record Status, SAM Number, CAGE, NPI (7.2k rows), Creation_Date.
- Loaded as `sam` by `ingest/06_sam_exclusions.py`. HHS rows duplicate LEIE; OPM rows are FEHB debarments and are the unique signal (2.4k NPIs). Live lookups by name/UEI: `api/verify.py::sam_live_lookup`.

## bluebutton (CMS Blue Button 2.0)
- `v3-data-dictionary.csv`: every Blue Button field with its CCW variable name.
- Live data comes from `api/bluebutton.py` against the production API (OAuth + PKCE, pagination, normalization). EOB careTeam.provider.identifier carries NPIs (type code `npi`); billablePeriod is the service date; `type.coding` with system `.../eob-type` gives CARRIER, DME, HHA, HOSPICE, INPATIENT, OUTPATIENT, SNF, PDE. No synthetic or sample bundles are kept in this repo.
