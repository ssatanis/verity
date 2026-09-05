-- Monthly all-code totals per NPI in each role (for Detector 3 timing and Detector 2 growth). Two parquet scans, ~20 s each.
CREATE OR REPLACE TABLE spend_bill_month AS
SELECT BILLING_PROVIDER_NPI_NUM AS npi, CLAIM_FROM_MONTH AS month, CAST(CLAIM_FROM_MONTH || '-01' AS DATE) AS month_start,
       SUM(TOTAL_PAID) AS paid, SUM(TOTAL_CLAIM_LINES) AS lines, MAX(TOTAL_PATIENTS) AS max_patients, COUNT(*) AS n_codes
FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet')
WHERE regexp_matches(BILLING_PROVIDER_NPI_NUM, '^[0-9]{10}$') AND TOTAL_PAID BETWEEN 0 AND 50000000
GROUP BY 1,2,3;

CREATE OR REPLACE TABLE spend_srv_month AS
SELECT SERVICING_PROVIDER_NPI_NUM AS npi, CLAIM_FROM_MONTH AS month, CAST(CLAIM_FROM_MONTH || '-01' AS DATE) AS month_start,
       SUM(TOTAL_PAID) AS paid, SUM(TOTAL_CLAIM_LINES) AS lines, MAX(TOTAL_PATIENTS) AS max_patients, COUNT(*) AS n_codes,
       COUNT(DISTINCT BILLING_PROVIDER_NPI_NUM) AS n_billing
FROM read_parquet('data/medicaid_tmsis/medicaid-provider-spending.parquet')
WHERE regexp_matches(SERVICING_PROVIDER_NPI_NUM, '^[0-9]{10}$') AND TOTAL_PAID BETWEEN 0 AND 50000000
GROUP BY 1,2,3;

-- Census ZCTA -> county (2020 relationship file; a ZIP can span counties, keep the land-area share) and ZCTA / county centroids
CREATE OR REPLACE TABLE zcta_county AS
SELECT GEOID_ZCTA5_20 AS zcta, GEOID_COUNTY_20 AS county_fips, NAMELSAD_COUNTY_20 AS county_name,
       TRY_CAST(AREALAND_PART AS DOUBLE) / NULLIF(TRY_CAST(AREALAND_ZCTA5_20 AS DOUBLE), 0) AS land_share
FROM read_csv('data/census/tab20_zcta520_county20_natl.txt', delim='|', header=true, all_varchar=true)
WHERE GEOID_ZCTA5_20 IS NOT NULL AND GEOID_ZCTA5_20 <> '';

CREATE OR REPLACE TABLE zcta_primary_county AS
SELECT zcta, county_fips, county_name, land_share FROM zcta_county
QUALIFY ROW_NUMBER() OVER (PARTITION BY zcta ORDER BY land_share DESC NULLS LAST) = 1;

CREATE OR REPLACE TABLE zcta_centroid AS
SELECT trim(GEOID) AS zcta, TRY_CAST(INTPTLAT AS DOUBLE) AS lat, TRY_CAST(INTPTLONG AS DOUBLE) AS lon
FROM read_csv('data/census/2024_Gaz_zcta_national.txt', delim='\t', header=true, all_varchar=true);

CREATE OR REPLACE TABLE county_centroid AS
SELECT trim(GEOID) AS county_fips, trim(NAME) AS county_name, trim(USPS) AS state, TRY_CAST(INTPTLAT AS DOUBLE) AS lat, TRY_CAST(INTPTLONG AS DOUBLE) AS lon
FROM read_csv('data/census/2024_Gaz_counties_national.txt', delim='\t', header=true, all_varchar=true);

-- NPPES extras: other names (DBA), secondary practice locations, deactivated-NPI report
CREATE OR REPLACE TABLE nppes_othername AS
SELECT "NPI" AS npi, "Provider Other Organization Name" AS other_name, "Provider Other Organization Name Type Code" AS name_type
FROM read_csv('data/nppes/othername_pfile_20050523-20260809.csv', all_varchar=true, header=true);

CREATE OR REPLACE TABLE nppes_locations AS
SELECT "NPI" AS npi, "Provider Secondary Practice Location Address- Address Line 1" AS addr1, "Provider Secondary Practice Location Address-  Address Line 2" AS addr2, "Provider Secondary Practice Location Address - City Name" AS city, "Provider Secondary Practice Location Address - State Name" AS state,
       substr("Provider Secondary Practice Location Address - Postal Code",1,5) AS zip5, "Provider Secondary Practice Location Address - Telephone Number" AS phone
FROM read_csv('data/nppes/pl_pfile_20050523-20260809.csv', all_varchar=true, header=true, ignore_errors=true);
