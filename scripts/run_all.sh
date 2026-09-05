#!/bin/bash
# Full Verity pipeline: clean -> warehouse -> aux tables -> rates and state lists -> SAM -> detectors -> risk score -> Supabase -> static fallback. About 20 minutes on an M-series laptop.
# Optional model steps (need ANTHROPIC_API_KEY, run separately, each writes a docs/ report): ingest/07_state_exclusions_claude.py, scripts/timecode_qa_claude.py,
# scripts/sam_match_claude.py, scripts/er_tiebreak_batch.py, scripts/methods_narrative_claude.py, scripts/pregenerate_packets.py.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
$PY ingest/00_clean_encoding.py
$PY ingest/build_warehouse.py && $PY ingest/03_sanity_checks.py
$PY -c "import duckdb,re;c=duckdb.connect('data/verity.duckdb');[c.execute(s) for s in re.split(r';\s*\n', open('ingest/04_build_monthly_and_aux.sql').read()) if 'CREATE' in s]"
$PY ingest/05_mn_rates_and_state_exclusions.py
$PY ingest/06_sam_exclusions.py --no-fetch
$PY detectors/d3_revoked_but_paid.py
$PY detectors/d2_impossible_days.py
$PY detectors/d1_ghost_networks.py
$PY detectors/risk_score.py
$PY ingest/sync_supabase.py && $PY ingest/sync_outputs.py
$PY scripts/export_static.py
$PY ingest/upload_storage.py && $PY ingest/export_derived.py
$PY scripts/ground_truth_check.py
$PY -m pytest -q tests
echo "pipeline complete"
