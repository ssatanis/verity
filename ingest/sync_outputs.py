#!/usr/bin/env python3
"""Push detector outputs from data/verity.duckdb into Supabase Postgres: clusters, cluster_members, flags, providers (only NPIs a
detector touches), county_risk rollups, and the summary the home page reads. Idempotent (truncate + copy per table)."""
import io, json, os, sys, time, duckdb, psycopg
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); load_dotenv()
DB = os.environ["DATABASE_URL"]
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"), read_only=True)
pg = psycopg.connect(DB, autocommit=False)
with pg.cursor() as cur: cur.execute(open("ingest/supabase_schema.sql").read())
pg.commit(); print("schema applied")
os.makedirs("demo/cache", exist_ok=True)
def copy(table, cols, sql, truncate=True):
    t = time.time(); tmp = f"demo/cache/out_{table}.csv"
    con.execute(f"COPY ({sql}) TO '{tmp}' (FORMAT CSV, HEADER false, NULL '', QUOTE '\"', ESCAPE '\"')")
    n = con.execute(f"SELECT COUNT(*) FROM read_csv_auto('{tmp}', header=false, all_varchar=true)").fetchone()[0] if os.path.getsize(tmp) else 0
    with pg.cursor() as cur:
        if truncate: cur.execute(f"TRUNCATE public.{table} CASCADE"); pg.commit()
        with open(tmp, "rb") as f, cur.copy(f"COPY public.{table} ({cols}) FROM STDIN WITH (FORMAT csv, NULL '')") as cp:
            for chunk in iter(lambda: f.read(1 << 20), b""): cp.write(chunk)
    pg.commit(); os.remove(tmp); print(f"synced {table:<18} {n:>9,} rows {time.time()-t:5.1f}s", flush=True); return n
have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
counts = {}
if "clusters" in have:
    counts["clusters"] = copy("clusters", "id, detector, state, county, county_fips, score, dollars_at_risk, n_providers, summary, features, rank, eligible, chain_or_pe, n_hospice, n_hha, n_snf, city, structure_score, label_score, context_score, dollars_medicare, graph, lat, lon",
        """SELECT c.cluster_id, 'D1', c.state, cc.county_name, c.county_fips, c.risk_score, c.dollars_medicaid_2024, c.n_prov, c.summary, c.features_json, c.rank, c.eligible, c.chain_or_pe = 1,
                  c.n_hospice, c.n_hha, c.n_snf, c.city, c.structure_score, c.label_score, c.context_score, c.dollars_medicare_2023, c.graph_json, cc.lat, cc.lon
           FROM clusters c LEFT JOIN county_centroid cc ON cc.county_fips = c.county_fips""")
    counts["cluster_members"] = copy("cluster_members", "cluster_id, npi, enrollment_id, role, org_name, evidence, ptype, ccn, city, state, zip5, inc_date, labels, medicaid_2024, medicare_2023",
        """SELECT cluster_id, npi, enrollment_id, ptype, org_name, to_json(struct_pack(dba := dba, county_fips := county_fips)), ptype, ccn, city, state, zip5, TRY_CAST(inc_date AS DATE), labels, medicaid_2024, medicare_2023 FROM cluster_members""")
if "flags" in have:
    counts["flags"] = copy("flags", "id, detector, npi, billing_npi, state, month, hcpcs, metric, value, threshold, score, dollars, evidence, tier, name, entity_type",
        """SELECT f.id, f.detector, f.npi, f.billing_npi, f.state, f.month, f.hcpcs, f.metric, f.value, f.threshold, f.score, f.dollars, f.evidence, f.tier,
                  COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))), n.entity_type
           FROM flags f LEFT JOIN nppes n ON n.npi = f.npi
           WHERE NOT (f.detector = 'D2' AND f.tier = 'C')   -- tier C (elevated, informational) stays in DuckDB to keep Postgres inside its disk budget""")
# providers: every NPI referenced by a flag or a cluster member, slim NPPES + Medicaid home state + ZIP centroid
counts["providers"] = copy("providers", "npi, entity_type, name, org_name, address1, city, state, zip5, phone, taxonomy, enum_date, deact_date, medicaid_state, ao_name, ao_phone, extra, lat, lon, county_fips",
    f"""WITH ids AS ({' UNION '.join(x for x in ['SELECT npi FROM flags'] + (['SELECT npi FROM cluster_members'] if 'cluster_members' in have else []))})
        SELECT n.npi, n.entity_type, COALESCE(n.org_name, trim(COALESCE(n.first_name,'') || ' ' || COALESCE(n.last_name,''))), n.org_name, n.addr1, n.city, n.state, n.zip5, n.phone, n.taxonomy,
               n.enum_date, n.deact_date, ps.state, trim(COALESCE(n.ao_first,'') || ' ' || COALESCE(n.ao_last,'')), n.ao_phone,
               to_json(struct_pack(credential := n.credential, mail_city := n.mail_city, mail_state := n.mail_state, sole_proprietor := n.sole_proprietor, parent_org := n.parent_org_lbn)),
               zc.lat, zc.lon, pc.county_fips
        FROM ids JOIN nppes n ON n.npi = ids.npi LEFT JOIN provider_state ps ON ps.npi = n.npi LEFT JOIN zcta_centroid zc ON zc.zcta = n.zip5 LEFT JOIN zcta_primary_county pc ON pc.zcta = n.zip5""")
# county rollups: D1 dollars by dominant county, D2/D3 dollars by the flagged provider's ZIP county
counts["county_risk"] = copy("county_risk", "county_fips, state, county_name, lat, lon, n_clusters, n_providers_flagged, dollars_at_risk, d1_dollars, d2_dollars, d3_dollars, top_cluster_id, top_score",
    f"""WITH d1 AS ({'SELECT county_fips, COUNT(*) n_clusters, SUM(dollars_medicaid_2024) d, MAX(risk_score) top_score, arg_max(cluster_id, risk_score) top_id FROM clusters WHERE eligible AND county_fips IS NOT NULL GROUP BY 1' if 'clusters' in have else "SELECT NULL::VARCHAR county_fips, 0 n_clusters, 0.0 d, 0.0 top_score, NULL::VARCHAR top_id WHERE FALSE"}),
             fl AS (SELECT pc.county_fips, f.detector, f.npi, SUM(f.dollars) d FROM flags f JOIN nppes n ON n.npi = f.npi JOIN zcta_primary_county pc ON pc.zcta = n.zip5 WHERE f.tier IN ('A') GROUP BY 1,2,3),
             fa AS (SELECT county_fips, COUNT(DISTINCT npi) n_prov, SUM(d) FILTER (WHERE detector='D2') d2, SUM(d) FILTER (WHERE detector='D3') d3 FROM fl GROUP BY 1),
             u AS (SELECT county_fips FROM d1 UNION SELECT county_fips FROM fa)
        SELECT u.county_fips, cc.state, cc.county_name, cc.lat, cc.lon, COALESCE(d1.n_clusters,0), COALESCE(fa.n_prov,0),
               COALESCE(d1.d,0) + COALESCE(fa.d2,0) + COALESCE(fa.d3,0), COALESCE(d1.d,0), COALESCE(fa.d2,0), COALESCE(fa.d3,0), d1.top_id, d1.top_score
        FROM u LEFT JOIN d1 USING (county_fips) LEFT JOIN fa USING (county_fips) LEFT JOIN county_centroid cc ON cc.county_fips = u.county_fips WHERE u.county_fips IS NOT NULL""")
# summary
summ = {}
for f in ("d1_summary", "d2_summary", "d3_summary"):
    p = f"demo/cache/{f}.json"
    if os.path.exists(p): summ[f] = json.load(open(p))
summ["totals"] = dict(
    d3_npis_paid_after=con.execute("SELECT COUNT(*) FROM d3_npi WHERE paid_after > 0").fetchone()[0] if "d3_npi" in have else None,
    d3_dollars_after=con.execute("SELECT SUM(paid_after) FROM d3_npi").fetchone()[0] if "d3_npi" in have else None,
    d2_npis_impossible=con.execute("SELECT COUNT(*) FROM d2_top WHERE months_impossible > 0").fetchone()[0] if "d2_top" in have else None,
    d2_dollars_impossible=con.execute("SELECT SUM(paid_flagged_months) FROM d2_top WHERE months_impossible > 0").fetchone()[0] if "d2_top" in have else None,
    d1_clusters_eligible=con.execute("SELECT COUNT(*) FROM clusters WHERE eligible").fetchone()[0] if "clusters" in have else None,
    d1_dollars_top200=con.execute("SELECT SUM(dollars_medicaid_2024) FROM clusters WHERE eligible AND rank <= 200").fetchone()[0] if "clusters" in have else None,
    spend_rows=238015729, spend_time_rows=con.execute("SELECT COUNT(*) FROM spend").fetchone()[0], providers_with_state=con.execute("SELECT COUNT(*) FROM provider_state").fetchone()[0],
    nppes=con.execute("SELECT COUNT(*) FROM nppes").fetchone()[0], generated_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
if os.path.exists("docs/methods.md"): summ["methods_md"] = {"text": open("docs/methods.md").read(), "updated": time.strftime("%Y-%m-%d %H:%M")}
with pg.cursor() as cur:
    for k, v in summ.items():
        cur.execute("INSERT INTO public.summary (key, value, updated_at) VALUES (%s, %s, now()) ON CONFLICT (key) DO UPDATE SET value = excluded.value, updated_at = now()", (k, json.dumps(v, default=str)))
    for t, n in counts.items():
        cur.execute("INSERT INTO public.datasets (id, name, rows, notes, loaded_at) VALUES (%s,%s,%s,%s,now()) ON CONFLICT (id) DO UPDATE SET rows = excluded.rows, loaded_at = now()", (t, f"public.{t}", n, "detector output, ingest/sync_outputs.py"))
pg.commit(); pg.close(); print("done", counts)
