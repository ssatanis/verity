"""Static fallback for the console: writes the small serving tables to web/public/fallback/*.json so the demo survives a Supabase outage or budget pause.
Run after ingest/sync_outputs.py. The console reads Supabase first and falls back to these files when a query fails."""
from __future__ import annotations
import json, os, pathlib
import duckdb, psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
ROOT = pathlib.Path(__file__).resolve().parents[1]; load_dotenv(ROOT / ".env")
OUT = ROOT / "web" / "public" / "fallback"; OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", str(ROOT / "data" / "verity.duckdb")), read_only=True)
def write(name, data):
    (OUT / f"{name}.json").write_text(json.dumps(data, default=str)); print(f"{name:16s} {len(data):>7,} rows {os.path.getsize(OUT / f'{name}.json') / 1e6:5.1f} MB")
def dump(name, sql):
    rows = con.execute(sql).fetchall(); cols = [d[0] for d in con.description]; write(name, [dict(zip(cols, r)) for r in rows])
dump("provider_risk", "SELECT npi, name, entity_type, city, state, tier, tier_label, detectors, score, dollars_at_risk, reasons, rank, enf_url, enf_title FROM provider_risk ORDER BY rank LIMIT 2000")
dump("clusters", "SELECT cluster_id AS id, rank, risk_score AS score, state, city, county_fips AS county, n_prov AS n_providers, n_hospice, n_hha, n_snf, dollars_medicaid_2024 AS dollars_at_risk, dollars_medicare_2023 AS dollars_medicare, summary, eligible, chain_or_pe = 1 AS chain_or_pe FROM clusters WHERE eligible ORDER BY rank LIMIT 300")
dump("hub_addresses", "SELECT * EXCLUDE (npis) FROM d1_hub_addresses ORDER BY n_providers DESC LIMIT 200")
# enforcement releases for the News tab: the newest relevant releases with their text. Bodies are kept only for the newest so the file stays small.
dump("enforcement", """WITH a AS (SELECT * FROM enforcement_actions WHERE relevant QUALIFY row_number() OVER (PARTITION BY source_id ORDER BY confidence DESC NULLS LAST, extracted_at DESC) = 1),
                            m AS (SELECT source_id, to_json(list(DISTINCT npi ORDER BY npi)) AS npis FROM enforcement_npi_matches WHERE same_entity AND confidence = 'high' AND npi IS NOT NULL GROUP BY 1)
                       SELECT r.source_id AS id, r.source, r.title, r.published, r.url, r.district, COALESCE(a.event_state, a.state, r.state) AS state, a.action_type, a.tier, a.programs, a.scheme,
                              a.dollars_alleged, a.dollars_ordered, TRY_CAST(a.action_date AS DATE) AS action_date,
                              CASE WHEN row_number() OVER (ORDER BY r.published DESC) <= 400 THEN r.body END AS body, m.npis
                       FROM enforcement_raw r JOIN a USING (source_id) LEFT JOIN m USING (source_id)
                       WHERE r.title IS NOT NULL AND r.published IS NOT NULL ORDER BY r.published DESC LIMIT 1500""")
with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as pg:
    write("county_risk", pg.execute("SELECT * FROM public.county_risk ORDER BY dollars_at_risk DESC LIMIT 3200").fetchall())
    write("summary", pg.execute("SELECT key, value FROM public.summary").fetchall())
