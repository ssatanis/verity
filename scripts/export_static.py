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
dump("provider_risk", "SELECT npi, name, entity_type, city, state, tier, tier_label, detectors, score, dollars_at_risk, reasons, rank FROM provider_risk ORDER BY rank LIMIT 2000")
dump("clusters", "SELECT cluster_id AS id, rank, risk_score AS score, state, city, county_fips AS county, n_prov AS n_providers, n_hospice, n_hha, n_snf, dollars_medicaid_2024 AS dollars_at_risk, dollars_medicare_2023 AS dollars_medicare, summary, eligible, chain_or_pe = 1 AS chain_or_pe FROM clusters WHERE eligible ORDER BY rank LIMIT 300")
dump("hub_addresses", "SELECT * EXCLUDE (npis) FROM d1_hub_addresses ORDER BY n_providers DESC LIMIT 200")
with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as pg:
    write("county_risk", pg.execute("SELECT * FROM public.county_risk ORDER BY dollars_at_risk DESC LIMIT 3200").fetchall())
    write("summary", pg.execute("SELECT key, value FROM public.summary").fetchall())
