#!/usr/bin/env python3
"""DuckDB quickstart for Verity. Run after download_all.py has finished tier 1 and 2.
Creates verity.duckdb with views over the raw files and prints starter results for the three detectors."""
import duckdb, glob, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); D = os.path.join(ROOT, "data")
con = duckdb.connect(os.path.join(ROOT, "verity.duckdb"))
def g(p): 
    f = sorted(glob.glob(os.path.join(D, p))); assert f, p; return f[-1]
con.execute(f"CREATE OR REPLACE VIEW hospice_enroll AS SELECT * FROM read_csv_auto('{g('cms_enrollment/Hospice_Enrollments*.csv')}', header=true, all_varchar=true)")
con.execute(f"CREATE OR REPLACE VIEW hospice_owners AS SELECT * FROM read_csv_auto('{g('cms_enrollment/Hospice_All_Owners*.csv')}', header=true, all_varchar=true)")
con.execute(f"CREATE OR REPLACE VIEW hha_enroll AS SELECT * FROM read_csv_auto('{g('cms_enrollment/HHA_Enrollments*.csv')}', header=true, all_varchar=true)")
con.execute(f"CREATE OR REPLACE VIEW hha_owners AS SELECT * FROM read_csv_auto('{g('cms_enrollment/HHA_All_Owners*.csv')}', header=true, all_varchar=true)")
con.execute(f"CREATE OR REPLACE VIEW revoked AS SELECT * FROM read_csv_auto('{g('cms_enrollment/Revocation_Extract*.csv')}', header=true, all_varchar=true)")
con.execute(f"CREATE OR REPLACE VIEW leie AS SELECT * FROM read_csv_auto('{g('oig_leie/LEIE_UPDATED.csv')}', header=true, all_varchar=true)")
con.execute(f"CREATE OR REPLACE VIEW saturation AS SELECT * FROM read_csv_auto('{g('cms_program_integrity/MSATMarket*.csv')}', header=true, all_varchar=true)")
for f in glob.glob(os.path.join(D, "cms_utilization/post_acute/*HOS*main*.csv")):
    pass
con.execute(f"CREATE OR REPLACE VIEW hospice_puf AS SELECT * FROM read_csv_auto('{os.path.join(D,'cms_utilization/post_acute/*HOS*main*.csv')}', header=true, all_varchar=true, union_by_name=true, filename=true)")
mp = os.path.join(D, "medicaid_tmsis/medicaid-provider-spending.parquet")
if os.path.exists(mp + ".done"):
    con.execute(f"CREATE OR REPLACE VIEW medicaid AS SELECT * FROM read_parquet('{mp}')")
    print(con.execute("DESCRIBE medicaid").fetchall())
me = os.path.join(D, "medicaid_tmsis/medicaid-provider-enrollment-segments.parquet")
if os.path.exists(me + ".done"):
    con.execute(f"CREATE OR REPLACE VIEW medicaid_enroll AS SELECT * FROM read_parquet('{me}')")

print("hospice enrollments:", con.execute("SELECT count(*) FROM hospice_enroll").fetchone())
print("hospice owner rows:", con.execute("SELECT count(*) FROM hospice_owners").fetchone())
print("columns:", [c[0] for c in con.execute("DESCRIBE hospice_owners").fetchall()])
# Detector 1 starter: owners tied to many hospices
print(con.execute('''
SELECT o."ASSOCIATE ID - OWNER" AS owner, any_value(coalesce(o."ORGANIZATION NAME - OWNER", o."FIRST NAME - OWNER" || ' ' || o."LAST NAME - OWNER")) AS name,
       count(DISTINCT o."ENROLLMENT ID") AS n_hospices
FROM hospice_owners o GROUP BY 1 HAVING n_hospices >= 5 ORDER BY n_hospices DESC LIMIT 15''').fetchdf())
# Detector 1 starter: incorporation bursts by city
print(con.execute('''
SELECT "STATE", "CITY", strftime(try_cast("INCORPORATION DATE" AS DATE), '%Y') AS yr, count(*) AS n
FROM hospice_enroll GROUP BY 1,2,3 HAVING n >= 15 ORDER BY n DESC LIMIT 15''').fetchdf())
# Detector 3 starter: revoked NPIs (labels)
print(con.execute("SELECT count(*), min(\"REVOCATION EFFECTIVE DATE\"), max(\"REVOCATION EFFECTIVE DATE\") FROM revoked").fetchall())
con.close(); print("wrote verity.duckdb")
