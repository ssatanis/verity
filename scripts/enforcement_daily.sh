#!/bin/sh
# Daily enforcement refresh: fetch new DOJ, HHS-OIG and state attorney general releases, extract and resolve them, rerun the
# detectors that read them, rescore, and publish. Fail-safe by construction: `set -e` stops the chain at the first failing step,
# so a broken feed or an API outage leaves every score exactly as it was and the console keeps showing the last good refresh date.
# Run from the project root. Scheduled by ops/launchd/org.verity.enforcement-daily.plist (macOS) or any cron.
set -e
cd "$(dirname "$0")/.."
mkdir -p logs
LOG="logs/enforcement_daily_$(date +%Y%m%d).log"
PY=".venv/bin/python -u"   # unbuffered so the log shows each step's progress as it happens
step() { echo "$(date '+%H:%M:%S') == $1" | tee -a "$LOG"; }

if [ -z "$SKIP_FEED" ]; then
  step "feed: last 7 days"
  $PY ingest/10_enforcement_feed.py --daily >> "$LOG" 2>&1
else
  step "feed: skipped (SKIP_FEED set; records already loaded)"
fi

step "extract: model reads new releases into the schema"
$PY scripts/enforcement_extract_claude.py >> "$LOG" 2>&1

step "match: parties to NPIs, high confidence only"
$PY scripts/enforcement_match_claude.py >> "$LOG" 2>&1

step "detector 3: paid after an action"
$PY detectors/d3_revoked_but_paid.py >> "$LOG" 2>&1

step "detector 1: provider networks (enforcement labels propagate to owners)"
$PY detectors/d1_ghost_networks.py >> "$LOG" 2>&1

step "risk score"
$PY detectors/risk_score.py >> "$LOG" 2>&1

step "publish: Supabase and static fallback"
$PY ingest/sync_outputs.py >> "$LOG" 2>&1
$PY scripts/export_static.py >> "$LOG" 2>&1

step "validation against named cases"
$PY scripts/ground_truth_check.py >> "$LOG" 2>&1 || echo "validation script reported an issue; scores were already published" | tee -a "$LOG"

date -u '+%Y-%m-%dT%H:%M:%SZ' > data/enforcement/last_refresh.txt
step "done"
