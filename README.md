# Verity

Pre-payment fraud tripwire for Medicare and Medicaid, built on public federal data. DNHacks 2026, Health and Public Service track.

Read `docs/Verity_Brief.md` for the judge analysis, the idea, the demo script, and the 24-hour plan. `docs/methods.md` has every
number behind the demo. `docs/SUPABASE.md` explains how the warehouse, Supabase Storage and Postgres fit together. `docs/DATA.md` is the
data dictionary and join keys.

## Problem and solution

See [docs/SUBMISSION.md](docs/SUBMISSION.md) for the problem statement, the solution, the persona, and the mapping to the DNHacks judging criteria. In one line: Medicaid and Medicare pay first and audit later, the public record already carries the signals that a payment should not go out, and Verity joins fourteen public datasets into one ranked, cited, human-reviewed referral queue for health plans.

## Layout

```
data/                    raw downloads (gitignored). See docs/DATA.md. manifest.json lists every file and its source URL.
  clean/                 UTF-8 copies of the CMS CSVs (ingest/00_clean_encoding.py); the warehouse reads these
  std/                   symlinks with the short names the playbook SQL uses
  sam_exclusions/        SAM.gov public exclusions extract (daily file, downloaded 2026-09-05)
  state_exclusions/      California S&I list, New York OMIG list, Texas OIG exclusions (Minnesota's list sits behind a captcha)
  census/                ZCTA to county relationship file, ZCTA and county centroids (2024 gazetteer)
  mn_rates/              Minnesota DHS-3945 rate tables (Jan 2022, Apr 2026) and the EIDBI billing grid (Jan 2026)
  verity.duckdb          the warehouse: spend, spend_totals, spend_*_month, enroll, provider_state, hospice/hha/snf/hospital, owners, chow,
                         ppef, order_referring, optout, revoked, leie, sam, state_exclusions, saturation*, nppes (+othername, locations,
                         deactivated), mn_rates, timecodes, zcta_*, county_centroid, and every detector table (d1_*, d2_*, d3_*, clusters, flags)
ingest/                  00_clean_encoding.py, 01_build_warehouse.sql + build_warehouse.py, 02_timecodes.csv, 03_sanity_checks.py,
                         04_build_monthly_and_aux.sql, 05_mn_rates_and_state_exclusions.py, 06_sam_exclusions.py, supabase_schema.sql,
                         sync_supabase.py (reference tables), sync_outputs.py (detector outputs), upload_storage.py, export_derived.py
detectors/               d1_ghost_networks.py, d2_impossible_days.py, d3_revoked_but_paid.py, _methods.py (writes docs/methods.md)
api/                     FastAPI: evidence.py, packet.py (investigator agent, deterministic fallback), main.py; verify.py + bluebutton.py (NPI tripwire, Blue Button 2.0)
web/                     Next.js 15 app (landing page + console) on Supabase; deployable to Vercel
scripts/                 download_all.py, fetch_medicaid_parquet.sh, bluebutton_offline_verify.py, quickstart.py (superseded)
docs/                    brief, data dictionary, methods (generated numbers), Supabase wiring
logs/                    build and detector logs (gitignored)
```

## Setup

```
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env      # then paste the Supabase keys, ANTHROPIC_API_KEY and SAM_API_KEY
```
Python 3.14 with DuckDB 1.5.5, pandas 3, pyarrow 25, networkx, leidenalg/igraph, scikit-learn, rapidfuzz, usaddress, nameparser,
FastAPI, anthropic (Claude Opus 5 for packets and the case chat, Batch API for list extraction and QA), psycopg. Exact versions in `requirements.txt`.

The web app needs Node 20+: `cd web && npm install && npm run dev`.

## Build the warehouse, run the detectors, load Supabase

```
.venv/bin/python ingest/00_clean_encoding.py
.venv/bin/python ingest/build_warehouse.py && .venv/bin/python ingest/03_sanity_checks.py
.venv/bin/python -c "import duckdb,re;c=duckdb.connect('data/verity.duckdb');[c.execute(s) for s in re.split(r';\s*\n', open('ingest/04_build_monthly_and_aux.sql').read()) if 'CREATE' in s]"
.venv/bin/python ingest/05_mn_rates_and_state_exclusions.py
.venv/bin/python ingest/06_sam_exclusions.py --no-fetch        # or with SAM_API_KEY set to refresh the extract
.venv/bin/python detectors/d3_revoked_but_paid.py
.venv/bin/python detectors/d2_impossible_days.py
.venv/bin/python detectors/d1_ghost_networks.py
.venv/bin/python ingest/sync_supabase.py && .venv/bin/python ingest/sync_outputs.py
.venv/bin/python ingest/upload_storage.py && .venv/bin/python ingest/export_derived.py
```
The whole chain runs in about 15 minutes on an M-series laptop. `docs/methods.md` is rewritten by the detectors with every number they produce.

## Web app and API

```
source .envrc                       # puts ~/.local/node/bin on PATH
cd web && npm install && npm run dev  # http://localhost:3000 (landing) and /app (console)
.venv/bin/uvicorn api.main:app --reload --port 8000   # evidence, packets, reviews, /verify, Blue Button
```
Deploy `web/` to Vercel with `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY` (server only) and, optionally, `ANTHROPIC_API_KEY` for Claude-drafted packets and the case chat; without a key the packet builder is deterministic and still cites every row.

## The three detectors

1. **Ghost networks** (`detectors/d1_ghost_networks.py`): heterogeneous graph over hospice, HHA and SNF enrollments, owners resolved with PECOS IDs plus a Fellegi-Sunter model fitted by EM, addresses at building and suite level, NPPES phones, officials and EINs, CHOW edges; Leiden communities; incorporation bursts, sharing, exclusion links, county saturation; robust-z composite; chains held out; precision at K against held-out 2023 to 2024 revocations.
2. **Impossible days** (`detectors/d2_impossible_days.py`): time-based Medicaid codes to clinician hours per calendar day with a rate-free lower bound, published Minnesota rates, and conservative estimates elsewhere; Minnesota's per-child EIDBI caps; robust z within state and taxonomy.
3. **Revoked but paid** (`detectors/d3_revoked_but_paid.py`): Medicare revocations (tiered by 42 CFR 424.535 ground), OIG LEIE, SAM.gov, California, New York and Texas exclusion lists, NPPES deactivations and Medicaid terminations joined to T-MSIS service months after the action; NPI check digit and name agreement on every match; cross-state for-cause terminations with bulk-coded states suppressed.

## Time-based HCPCS codes

`ingest/02_timecodes.csv`: 318 codes (265 timed, 53 per-diem) with the minutes one billed unit implies, a group divisor for group codes,
and conservative durations for untimed session codes. This drives the `spend` table and the impossible-days detector.

## Resume or refresh the downloads

```
python3 scripts/download_all.py --tier all --workers 5
```

## SAM.gov exclusions (SAM_API_KEY)

`ingest/06_sam_exclusions.py` pulls the daily public exclusions extract through the SAM Data Services API (all ~168k records, 7.2k with an NPI,
including 2.4k OPM/FEHB debarments and 4.7k HHS records) into `data/sam_exclusions/` and builds the `sam` table the detectors and the API use.
`api/verify.py::sam_live_lookup(name=...)` hits the Exclusions API v4 live for entities SAM lists without an NPI (`GET /sam/lookup?name=...`).
```
python3 ingest/06_sam_exclusions.py          # refresh extract + rebuild `sam`
```

## Blue Button 2.0 (beneficiary-side tripwire)

`api/bluebutton.py` implements the CMS authorization-code + PKCE flow, pulls Patient, Coverage and every ExplanationOfBenefit page for a
beneficiary who consents, extracts every NPI on the claims (careTeam, billing provider, contained organizations) and runs each service date
through the same exclusion sources as Detector 3 (CMS revocations, OIG LEIE, SAM.gov, state exclusion lists, NPPES deactivations, Medicaid
deceased terminations).

Real data only. `BLUEBUTTON_BASE_URL` is the production API (`https://api.bluebutton.cms.gov`). Production credentials require CMS approval
through the Production Access Guide (https://bluebutton.cms.gov/guide/): a registered app, privacy policy and terms URLs, a demo to the
Blue Button team, and an access-duration category. The sandbox app "Verity" is registered (credentials in `.env`) and is what CMS reviews
for that approval, but the sandbox serves only synthetic beneficiaries, so `/bluebutton/login` refuses to run against it unless
`BLUEBUTTON_ALLOW_SANDBOX=1` is set for integration testing. No synthetic bundles or test users are kept in this repo.

The path that works today with real data: any Medicare beneficiary can export their own claims from Medicare.gov (Blue Button download,
JSON). `POST /bluebutton/verify-bundle` and `scripts/bluebutton_offline_verify.py <file>` run that export through the tripwire.
```
uvicorn api.main:app --reload --port 8000       # redirect URI is http://localhost:8000/bluebutton/callback
# /verify/npi/<npi>   POST /verify/claims   /sam/lookup?name=...   POST /bluebutton/verify-bundle   /health
python3 scripts/bluebutton_offline_verify.py --npis 1811937436
```
Reference: `data/bluebutton/v3-data-dictionary.csv` (every Blue Button field and its CCW variable name).

## Not included

VA Lighthouse, No Surprises Act IDR files, hospital price transparency MRFs (per hospital). There is no private data in this project; everything
here is public federal data, with no PII or PHI.

### Scripts added on 2026-09-05 (evening)

| script | what it does |
|---|---|
| `detectors/risk_score.py` | one row per provider: tier 1 to 5, corroboration bonus, dollars at risk (max across detectors) |
| `scripts/export_static.py` | writes `web/public/fallback/*.json` so the console renders if Supabase is paused |
| `scripts/ground_truth_check.py` | profiles named enforcement cases and large health-system controls into `docs/validation.md` |
| `scripts/apply_timecode_qa.py` | reloads the time-code table after QA edits (DuckDB and Postgres) |
| `ingest/07_state_exclusions_claude.py` | fifty-state exclusion lists extracted with Claude (PDF, sheet, HTML); status in `docs/state_lists_status.md` |
| `scripts/timecode_qa_claude.py`, `scripts/sam_match_claude.py`, `scripts/er_tiebreak_batch.py`, `scripts/methods_narrative_claude.py` | Batch API jobs with reports in `docs/` |
| `scripts/pregenerate_packets.py` | drafts Claude packets for the top subjects so the console opens with packets in place |

### Console notes (2026-09-05, evening)

- Search and provider pages use the CMS NPPES Registry API (version 2.1, no key, refreshed daily), so any NPI in the country can be opened; the serving tables add tiers and indicators, and the local API adds Medicaid figures when it is running.
- Press Cmd+K (Ctrl+K on Windows) anywhere for a command palette: provider search plus page navigation.
- The network page carries a factor desk: thirty factors in seven families with percentiles and robust z-scores, and an indicative momentum reading (`detectors/d1_factor_desk.py`, table `network_factors`).
- The console is open for the demo (no sign in).
