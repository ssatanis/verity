"""Static fallback for the console: writes the small serving tables to web/public/fallback/*.json so the demo survives a Supabase outage or budget pause.
Run after ingest/sync_outputs.py. The console reads Supabase first and falls back to these files when a query fails."""
from __future__ import annotations
import json, os, pathlib, sys
import duckdb
ROOT = pathlib.Path(__file__).resolve().parents[1]; OUT = ROOT / "web" / "public" / "fallback"; OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", str(ROOT / "data" / "verity.duckdb")), read_only=True)
def dump(name, sql, limit=None):
    rows = con.execute(sql).fetchall(); cols = [d[0] for d in con.description]
    data = [dict(zip(cols, r)) for r in rows][: limit or None]
    (OUT / f"{name}.json").write_text(json.dumps(data, default=str)); print(f"{name:18s} {len(data):>7,} rows {os.path.getsize(OUT / f'{name}.json') / 1e6:5.1f} MB")
dump("provider_risk", "SELECT npi, name, entity_type, city, state, tier, tier_label, detectors, score, dollars_at_risk, reasons, rank FROM provider_risk ORDER BY rank LIMIT 2000")
dump("clusters", "SELECT id, rank, score, state, city, county, n_providers, n_hospice, n_hha, n_snf, dollars_at_risk, dollars_medicare, summary, eligible, chain_or_pe FROM d1_clusters WHERE eligible ORDER BY rank LIMIT 300")
dump("hub_addresses", "SELECT * EXCLUDE (npis) FROM d1_hub_addresses ORDER BY n_providers DESC LIMIT 200")
dump("county_risk", "SELECT * FROM county_risk ORDER BY dollars_at_risk DESC LIMIT 3200") if con.execute("SELECT count(*) FROM information_schema.tables WHERE table_name='county_risk'").fetchone()[0] else None
summ = json.loads((ROOT / "demo" / "cache" / "risk_summary.json").read_text()) if (ROOT / "demo" / "cache" / "risk_summary.json").exists() else {}
(OUT / "summary.json").write_text(json.dumps(summ, default=str)); print("summary written")
