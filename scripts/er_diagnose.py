"""Inspect the entity-resolution candidate pairs closest to the match threshold: what names and locations did the EM model actually compare?"""
import os, duckdb
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"), read_only=True)
print("candidates:", con.execute("SELECT count(*), sum(matched::int), round(avg(posterior),3) FROM d1_er_candidates").fetchone())
print("null or blank names on side i:", con.execute("SELECT count(*) FILTER (WHERE p_last_i IS NULL OR p_last_i = ''), count(*) FILTER (WHERE p_first_i IS NULL OR p_first_i = ''), count(*) FILTER (WHERE upper(p_last_i) = 'NAN') FROM d1_er_candidates").fetchone())
print("posterior bands:", con.execute("SELECT CASE WHEN posterior < 0.2 THEN 'lt0.2' WHEN posterior < 0.95 THEN '0.2to0.95' WHEN posterior < 0.98 THEN '0.95to0.98' ELSE 'ge0.98' END b, count(*) FROM d1_er_candidates GROUP BY 1 ORDER BY 1").fetchall())
for r in con.execute("SELECT p_last_i, p_first_i, zip5_i, city_i, p_last_j, p_first_j, zip5_j, city_j, g_last, g_first, g_zip, g_city, round(posterior,3), matched FROM d1_er_candidates WHERE matched ORDER BY posterior LIMIT 12").fetchall(): print("  ", r)
if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='d1_er_adjudications'").fetchone()[0]:
    print("adjudications:", con.execute("SELECT count(*), sum(CASE WHEN model_same THEN 1 ELSE 0 END), sum(CASE WHEN em_same THEN 1 ELSE 0 END) FROM d1_er_adjudications").fetchone())
    for r in con.execute("SELECT p_last_i, p_first_i, zip5_i, p_last_j, p_first_j, zip5_j, round(posterior,3), model_same, model_conf, substr(model_reason,1,90) FROM d1_er_adjudications LIMIT 6").fetchall(): print("  ", r)
