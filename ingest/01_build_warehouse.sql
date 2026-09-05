-- ingest/01_build_warehouse.sql
-- Builds data/verity.duckdb from the raw public files in data/. Run with: .venv/bin/python ingest/build_warehouse.py
-- Statement order matters: timecodes first (spend filters on it), NPPES last (slowest).

CREATE OR REPLACE TABLE timecodes AS
SELECT hcpcs, description, TRY_CAST(minutes_per_unit AS DOUBLE) AS minutes_per_unit, unit_basis,
       COALESCE(TRY_CAST(group_divisor AS INTEGER), 1) AS group_divisor, family, fraud_vector,
       TRY_CAST(mn_rate_per_unit AS DOUBLE) AS mn_rate_per_unit, TRY_CAST(mn_daily_cap_hours AS DOUBLE) AS mn_daily_cap_hours, personal_service = 'Y' AS personal_service, source, notes
FROM read_csv_auto('ingest/02_timecodes.csv', all_varchar=true, header=true);

-- Spending: clean NPIs only, time-based codes only, cap absurd dollars.
CREATE OR REPLACE TABLE spend AS
SELECT BILLING_PROVIDER_NPI_NUM AS billing_npi, SERVICING_PROVIDER_NPI_NUM AS servicing_npi,
       HCPCS_CODE AS hcpcs, CLAIM_FROM_MONTH AS month,
       CAST(try_strptime(CLAIM_FROM_MONTH || '-01', '%Y-%m-%d') AS DATE) AS month_start,
       TOTAL_PATIENTS AS patients, TOTAL_CLAIM_LINES AS lines, TOTAL_PAID AS paid
FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet')
WHERE regexp_matches(SERVICING_PROVIDER_NPI_NUM, '^[0-9]{10}$')
  AND regexp_matches(BILLING_PROVIDER_NPI_NUM, '^[0-9]{10}$')
  AND HCPCS_CODE IN (SELECT hcpcs FROM timecodes)
  AND TOTAL_PAID BETWEEN 0 AND 50000000;

-- All-code dollars per billing NPI per year (cluster dollars, Detector 3, the state pages)
CREATE OR REPLACE TABLE spend_totals AS
SELECT BILLING_PROVIDER_NPI_NUM AS billing_npi, substr(CLAIM_FROM_MONTH,1,4) AS year,
       SUM(TOTAL_PAID) AS paid, SUM(TOTAL_CLAIM_LINES) AS lines, MAX(TOTAL_PATIENTS) AS max_patients
FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet')
WHERE regexp_matches(BILLING_PROVIDER_NPI_NUM, '^[0-9]{10}$') AND TOTAL_PAID BETWEEN 0 AND 50000000
GROUP BY 1,2;

-- Rows dropped, for the Methods page (one scan, conditional counts)
CREATE OR REPLACE TABLE drops AS
WITH s AS (
  SELECT COUNT(*) AS total_rows,
         COUNT(*) FILTER (WHERE TOTAL_PAID > 50000000) AS paid_over_50M,
         COUNT(*) FILTER (WHERE TOTAL_PAID < 0) AS paid_negative,
         COUNT(*) FILTER (WHERE NOT regexp_matches(COALESCE(BILLING_PROVIDER_NPI_NUM,''), '^[0-9]{10}$')) AS bad_billing_npi,
         COUNT(*) FILTER (WHERE NOT regexp_matches(COALESCE(SERVICING_PROVIDER_NPI_NUM,''), '^[0-9]{10}$')) AS bad_servicing_npi,
         COUNT(*) FILTER (WHERE regexp_matches(COALESCE(SERVICING_PROVIDER_NPI_NUM,''), '^[0-9]{10}$') AND substr(SERVICING_PROVIDER_NPI_NUM,1,1) NOT IN ('1','2')) AS servicing_npi_not_1_or_2_prefix,
         COUNT(*) FILTER (WHERE HCPCS_CODE IN (SELECT hcpcs FROM timecodes)) AS rows_with_time_code
  FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet')
)
SELECT 'total_rows' AS reason, total_rows AS n FROM s
UNION ALL SELECT 'paid_over_50M', paid_over_50M FROM s
UNION ALL SELECT 'paid_negative', paid_negative FROM s
UNION ALL SELECT 'bad_billing_npi', bad_billing_npi FROM s
UNION ALL SELECT 'bad_servicing_npi', bad_servicing_npi FROM s
UNION ALL SELECT 'servicing_npi_not_1_or_2_prefix', servicing_npi_not_1_or_2_prefix FROM s
UNION ALL SELECT 'rows_with_time_code', rows_with_time_code FROM s;

-- Enrollment segments
CREATE OR REPLACE TABLE enroll AS
SELECT NPI AS npi, STATE_CD AS state, ENRL_START_DT AS start_dt,
       CASE WHEN ENRL_END_DT > DATE '2030-12-31' THEN NULL ELSE ENRL_END_DT END AS end_dt,   -- 9999-12-30 means open-ended
       ENRL_STATUS_CD AS status_cd, ENRL_STATUS_DESC AS status_desc, ENRL_PLAN_CD AS plan_cd, ENRL_PLAN_DESC AS plan_desc,
       PRVDR_TYPE AS prvdr_type, PRVDR_TYPE_DESC AS prvdr_type_desc
FROM read_parquet('data/medicaid_tmsis/medicaid-provider-enrollment-segments.parquet')
WHERE regexp_matches(NPI, '^[0-9]{10}$') AND ENRL_START_DT NOT IN (DATE '1900-01-01', DATE '1970-01-01') AND ENRL_START_DT > DATE '1900-01-01';
-- (0001-01-01 is a placeholder start date too)

CREATE OR REPLACE TABLE provider_state AS
WITH d AS (SELECT npi, state, SUM(GREATEST(0, date_diff('day', GREATEST(start_dt, DATE '2000-01-01'), LEAST(COALESCE(end_dt, DATE '2024-12-31'), DATE '2026-12-31')))) AS days FROM enroll GROUP BY 1,2)
SELECT npi, state, days FROM d QUALIFY ROW_NUMBER() OVER (PARTITION BY npi ORDER BY days DESC, state) = 1;

-- CMS enrollment and owners. Read as VARCHAR. Incorporation dates are MM/DD/YYYY in the July 2026 files but
-- try both ISO and US formats. ZIPs are 9 digits with no hyphen.
CREATE OR REPLACE TABLE hospice AS
SELECT *, COALESCE(TRY_CAST("INCORPORATION DATE" AS DATE), CAST(try_strptime("INCORPORATION DATE",'%m/%d/%Y') AS DATE)) AS inc_date,
       substr("ZIP CODE",1,5) AS zip5
FROM read_csv_auto('data/clean/cms_enrollment/Hospice_Enrollments_2026.07.17.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE hha AS
SELECT *, COALESCE(TRY_CAST("INCORPORATION DATE" AS DATE), CAST(try_strptime("INCORPORATION DATE",'%m/%d/%Y') AS DATE)) AS inc_date,
       substr("ZIP CODE",1,5) AS zip5
FROM read_csv_auto('data/clean/cms_enrollment/HHA_Enrollments_2026.07.17.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE snf AS
SELECT *, COALESCE(TRY_CAST("INCORPORATION DATE" AS DATE), CAST(try_strptime("INCORPORATION DATE",'%m/%d/%Y') AS DATE)) AS inc_date,
       substr("ZIP CODE",1,5) AS zip5
FROM read_csv_auto('data/clean/cms_enrollment/SNF_Enrollments_2026.07.31.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE hospital AS
SELECT *, COALESCE(TRY_CAST("INCORPORATION DATE" AS DATE), CAST(try_strptime("INCORPORATION DATE",'%m/%d/%Y') AS DATE)) AS inc_date,
       substr("ZIP CODE",1,5) AS zip5
FROM read_csv_auto('data/clean/cms_enrollment/Hospital_Enrollments_2026.07.31.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE owners AS
  SELECT 'HOSPICE' AS ptype, * FROM read_csv_auto('data/clean/cms_enrollment/Hospice_All_Owners_2026.07.17.csv', all_varchar=true, header=true)
  UNION ALL BY NAME SELECT 'HHA' AS ptype, * FROM read_csv_auto('data/clean/cms_enrollment/HHA_All_Owners_2026.07.17.csv', all_varchar=true, header=true)
  UNION ALL BY NAME SELECT 'SNF' AS ptype, * FROM read_csv_auto('data/clean/cms_enrollment/SNF_All_Owners_2026.07.31.csv', all_varchar=true, header=true)
  UNION ALL BY NAME SELECT 'HOSPITAL' AS ptype, * FROM read_csv_auto('data/clean/cms_enrollment/Hospital_All_Owners_2026.07.31.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE chow AS
  SELECT 'SNF' AS ptype, *, CAST(try_strptime("EFFECTIVE DATE",'%m/%d/%Y') AS DATE) AS effective_dt FROM read_csv_auto('data/clean/cms_enrollment/SNF_CHOW_2026.07.17.csv', all_varchar=true, header=true)
  UNION ALL BY NAME SELECT 'HOSPITAL' AS ptype, *, CAST(try_strptime("EFFECTIVE DATE",'%m/%d/%Y') AS DATE) AS effective_dt FROM read_csv_auto('data/clean/cms_enrollment/Hospital_CHOW_2026.07.17.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE ppef AS SELECT * FROM read_csv_auto('data/clean/cms_enrollment/PPEF_Enrollment_Extract_2026.07.17.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE order_referring AS SELECT * FROM read_csv_auto('data/clean/cms_enrollment/OrderReferring_20260831.csv', all_varchar=true, header=true, strict_mode=false, quote='"');

CREATE OR REPLACE TABLE optout AS
SELECT *, CAST(try_strptime("Optout Effective Date",'%m/%d/%Y') AS DATE) AS optout_start, CAST(try_strptime("Optout End Date",'%m/%d/%Y') AS DATE) AS optout_end
FROM read_csv_auto('data/clean/cms_enrollment/OptOut_July2026.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE revoked AS
SELECT ENRLMT_ID AS enrlmt_id, NPI AS npi, FIRST_NAME AS first_name, MDL_NAME AS mdl_name, LAST_NAME AS last_name, ORG_NAME AS org_name,
       STATE_CD AS state, PROVIDER_TYPE_DESC AS provider_type_desc, REVOCATION_RSN AS revocation_rsn,
       CAST(try_strptime(REVOCATION_EFCTV_DT, '%m/%d/%Y') AS DATE) AS revoked_dt,
       CAST(try_strptime(REENROLLMENT_BAR_EXPRTN_DT, '%m/%d/%Y') AS DATE) AS reenroll_bar_dt
FROM read_csv_auto('data/clean/cms_enrollment/Revocation_Extract_2026.07.30.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE leie AS
SELECT LASTNAME AS lastname, FIRSTNAME AS firstname, MIDNAME AS midname, BUSNAME AS busname, GENERAL AS general, SPECIALTY AS specialty, UPIN AS upin,
       CASE WHEN NPI='0000000000' OR NPI='' THEN NULL ELSE NPI END AS npi,
       CASE WHEN DOB IN ('00000000','') THEN NULL ELSE CAST(try_strptime(DOB,'%Y%m%d') AS DATE) END AS dob,
       ADDRESS AS address, CITY AS city, STATE AS state, ZIP AS zip, EXCLTYPE AS excltype,
       CASE WHEN EXCLDATE IN ('00000000','') THEN NULL ELSE CAST(try_strptime(EXCLDATE,'%Y%m%d') AS DATE) END AS excl_dt,
       CASE WHEN REINDATE IN ('00000000','') THEN NULL ELSE CAST(try_strptime(REINDATE,'%Y%m%d') AS DATE) END AS rein_dt,
       CASE WHEN WAIVERDATE IN ('00000000','') THEN NULL ELSE CAST(try_strptime(WAIVERDATE,'%Y%m%d') AS DATE) END AS waiver_dt,
       WVRSTATE AS wvrstate
FROM read_csv_auto('data/clean/oig_leie/LEIE_UPDATED.csv', all_varchar=true, header=true);

-- Market saturation: keep the raw county file as-is, plus a typed county-level table for the detectors.
CREATE OR REPLACE TABLE saturation AS
SELECT * FROM read_csv_auto('data/clean/cms_program_integrity/MSATMarket_Saturation_and_Utilization_State_County_Dataset_Release_R23_2026-04-23.csv', all_varchar=true, header=true, normalize_names=false);

CREATE OR REPLACE TABLE saturation_cbsa AS
SELECT * FROM read_csv_auto('data/clean/cms_program_integrity/MSAT_CBSA_Dataset_Release_R23_26-04-28.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE saturation_county AS
SELECT reference_period, substr(reference_period,1,4) AS period_year, type_of_service, aggregation_level, state, county,
       trim(state_fips) AS state_fips, trim(county_fips) AS county_fips,
       TRY_CAST(replace(trim(number_of_fee_for_service_beneficiaries),',','') AS BIGINT) AS ffs_beneficiaries,
       TRY_CAST(replace(trim(number_of_providers),',','') AS BIGINT) AS providers,
       TRY_CAST(replace(trim(average_number_of_users_per_provider),',','') AS DOUBLE) AS users_per_provider,
       TRY_CAST(replace(replace(trim(percentage_of_users_out_of_ffs_beneficiaries),',',''),'%','') AS DOUBLE) AS pct_users_of_ffs,
       TRY_CAST(replace(trim(number_of_users),',','') AS BIGINT) AS users,
       TRY_CAST(replace(trim(average_number_of_providers_per_county),',','') AS DOUBLE) AS providers_per_county,
       TRY_CAST(replace(trim(number_of_dual_eligible_users),',','') AS BIGINT) AS dual_users,
       TRY_CAST(replace(replace(replace(trim(total_payment),',',''),'$',''),' ','') AS DOUBLE) AS total_payment,
       CASE WHEN upper(trim(moratorium)) IN ('Y','YES','TRUE','1') THEN TRUE WHEN trim(moratorium)='' THEN NULL ELSE FALSE END AS moratorium,
       CASE WHEN TRY_CAST(replace(trim(number_of_fee_for_service_beneficiaries),',','') AS DOUBLE) > 0
            THEN 10000.0 * TRY_CAST(replace(trim(number_of_providers),',','') AS DOUBLE) / TRY_CAST(replace(trim(number_of_fee_for_service_beneficiaries),',','') AS DOUBLE) END AS providers_per_10k_ffs
FROM saturation
WHERE aggregation_level IN ('COUNTY','STATE','NATION + TERRITORIES','NATION');

CREATE OR REPLACE TABLE medicare_revoked_hhs AS SELECT * FROM read_parquet('data/medicaid_tmsis/medicare-revoked-providers-and-suppliers.parquet');

-- NPPES slim: only the columns needed, all NPIs. 11.6 GB CSV; 10 to 20 minutes.
CREATE OR REPLACE TABLE nppes AS
SELECT "NPI" AS npi, "Entity Type Code" AS entity_type, "Replacement NPI" AS replacement_npi,
       "Employer Identification Number (EIN)" AS ein,
       "Provider Organization Name (Legal Business Name)" AS org_name,
       "Provider Last Name (Legal Name)" AS last_name, "Provider First Name" AS first_name, "Provider Middle Name" AS middle_name,
       "Provider Credential Text" AS credential, "Provider Other Organization Name" AS other_org_name,
       "Provider First Line Business Mailing Address" AS mail_addr1, "Provider Business Mailing Address City Name" AS mail_city,
       "Provider Business Mailing Address State Name" AS mail_state, substr("Provider Business Mailing Address Postal Code",1,5) AS mail_zip5,
       "Provider First Line Business Practice Location Address" AS addr1, "Provider Second Line Business Practice Location Address" AS addr2,
       "Provider Business Practice Location Address City Name" AS city,
       "Provider Business Practice Location Address State Name" AS state,
       substr("Provider Business Practice Location Address Postal Code",1,5) AS zip5,
       "Provider Business Practice Location Address Telephone Number" AS phone,
       "Provider Business Practice Location Address Fax Number" AS fax,
       CAST(try_strptime("Provider Enumeration Date",'%m/%d/%Y') AS DATE) AS enum_date,
       CAST(try_strptime("Last Update Date",'%m/%d/%Y') AS DATE) AS last_update,
       "NPI Deactivation Reason Code" AS deact_reason,
       CAST(try_strptime("NPI Deactivation Date",'%m/%d/%Y') AS DATE) AS deact_date,
       CAST(try_strptime("NPI Reactivation Date",'%m/%d/%Y') AS DATE) AS react_date,
       "Healthcare Provider Taxonomy Code_1" AS taxonomy, "Healthcare Provider Primary Taxonomy Switch_1" AS taxonomy_primary,
       "Provider License Number_1" AS license1, "Provider License Number State Code_1" AS license1_state,
       "Is Sole Proprietor" AS sole_proprietor, "Is Organization Subpart" AS org_subpart,
       "Parent Organization LBN" AS parent_org_lbn, "Parent Organization TIN" AS parent_org_tin,
       "Authorized Official Last Name" AS ao_last, "Authorized Official First Name" AS ao_first,
       "Authorized Official Title or Position" AS ao_title, "Authorized Official Telephone Number" AS ao_phone
FROM read_csv('data/nppes/npidata_pfile_20050523-20260809.csv', all_varchar=true, header=true, ignore_errors=true, parallel=true);
