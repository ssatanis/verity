# Supabase wiring

Project: `kdyvtsajakswyxmfrygv` (https://kdyvtsajakswyxmfrygv.supabase.co), Postgres 17, region us-east-1.

## Architecture

```
raw public files (data/)  ──►  data/clean/  ──►  DuckDB warehouse data/verity.duckdb   (compute: 238M-row scans, graph, scoring)
                                    │                     │
                                    │                     ├──►  Supabase Storage  verity-derived   parquet extracts the app/API can read directly
                                    │                     └──►  Supabase Postgres  public.*        reference tables + detector outputs + reviews
                                    └──────────────────►  Supabase Storage  verity-raw       byte-for-byte source snapshots (+ manifest.json)
```

DuckDB is where the heavy work happens (the T-MSIS spending file, NPPES, entity resolution). Supabase is the serving layer: what the
Next.js app, the FastAPI service and the investigator agent read, and where reviewer decisions are written back.

## Keys and connection strings

`.env` (Python, API, ingest) and `web/.env.local` (Next.js) hold the keys copied from the dashboard on 2026-09-05. Both are gitignored.

- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY` (browser-safe), `SUPABASE_SECRET_KEY` (server only), `SUPABASE_JWKS_URL`.
- `DATABASE_URL` points at the Supavisor pooler in session mode: `postgresql://postgres.kdyvtsajakswyxmfrygv:<pw>@aws-0-us-east-1.pooler.supabase.com:5432/postgres?sslmode=require`.
  The direct host `db.kdyvtsajakswyxmfrygv.supabase.co` only has an IPv6 address and this laptop has no IPv6 route, so psql/psycopg to it hang.
  `ingest/find_pooler.py` probes the pooler regions and rewrites `DATABASE_URL` if the project ever moves.
- Supabase MCP server for Claude Code is declared in `.mcp.json`; authenticate once with `claude /mcp` in a regular terminal.

## Storage buckets

| bucket | public | contents |
|---|---|---|
| `verity-raw` | yes | 40 source files (CMS enrollment, owners, CHOW, revoked, LEIE, Care Compare, Open Payments summaries, timecodes, download manifest). Files over 45 MB are gzipped. `manifest.json` at the root lists every object with size and sha256. |
| `verity-derived` | yes | Parquet exports of the warehouse tables the app needs: `spend_totals`, `provider_state`, `saturation_county`, `owners`, `hospice`/`hha`/`snf`/`hospital`, `revoked`, `leie`, `chow`, `optout`, `timecodes`, `drops`, `nppes_facilities`. `manifest.json` lists rows, bytes, sha256 and the SQL that produced each file. |
| `verity-packets` | no | Agent-generated referral packets (PDF/JSON), written by the API with the secret key. |

Public objects sit behind Supabase's CDN, so a re-uploaded file can be served stale for a few minutes; scripts that need the fresh copy use `/storage/v1/object/authenticated/<bucket>/<path>` with the secret key.

Public object URL pattern: `https://kdyvtsajakswyxmfrygv.supabase.co/storage/v1/object/public/<bucket>/<path>`.
DuckDB can query the derived files in place: `SELECT * FROM read_parquet('https://kdyvtsajakswyxmfrygv.supabase.co/storage/v1/object/public/verity-derived/spend_totals.parquet')`.

## Postgres tables (`ingest/supabase_schema.sql`)

Reference data, loaded by `ingest/sync_supabase.py` straight from the cleaned raw files: `timecodes`, `revoked`, `leie`, `enrollments`
(hospice, HHA, SNF, hospital, FQHC, RHC), `owners` (hospice, HHA, SNF, hospital All-Owners; the ownership-type Y/N columns are folded into a
`flags` text[] holding only the markers set to Y, e.g. `{llc,for_profit}`, with a GIN index), `chow`, `saturation_county` (2023 onward in
Postgres to stay well inside the database quota; 2020 onward is in the `verity-derived` parquet and everything is in DuckDB; county/state/nation rows, typed numbers, `providers_per_10k_ffs`).

Detector outputs, written by the detectors: `clusters`, `cluster_members`, `flags`, `evidence`, `providers` (slim NPPES rows for any NPI a
detector touches). Agent and feedback loop: `packets`, `reviews` (accept / reject / needs_info). `datasets` is the load manifest the home
page reads.

Row level security is on for every table with a public-read policy; writes go through the secret key (service role bypasses RLS) or,
for `reviews` and `packets`, through signed-in reviewers.

## Size budget

The project's Postgres disk is small (a reload that briefly doubled the `owners` table hit "no space left on device" at about 1 GB), so keep
`public.*` under roughly 400 MB: it is 268 MB now (owners 168 MB, saturation_county 50 MB, enrollments 20 MB, leie 15 MB). Big tables stay in
DuckDB and the derived parquet; `sync_supabase.py` commits the TRUNCATE before each COPY so a reload never needs double the space.

## Re-running

```
.venv/bin/python ingest/00_clean_encoding.py     # UTF-8 copies of the CMS CSVs (they ship with stray Windows-1252 bytes)
.venv/bin/python ingest/build_warehouse.py       # data/verity.duckdb, about 2 minutes on an M-series laptop
.venv/bin/python ingest/03_sanity_checks.py      # appends the Methods numbers to docs/methods.md
.venv/bin/python ingest/sync_supabase.py         # schema + reference tables into Postgres
.venv/bin/python ingest/upload_storage.py        # raw snapshots into verity-raw
.venv/bin/python ingest/export_derived.py        # parquet extracts into verity-derived
```
All are idempotent. `build_warehouse.py --only table1,table2` rebuilds a subset.

## Detector outputs and the app (added 2026-09-05 afternoon)

`ingest/sync_outputs.py` pushes the detector tables from DuckDB: `clusters` (one row per D1 community with rank, eligibility, chain flag,
feature JSON, the graph JSON the console draws, county centroid), `cluster_members`, `flags` (D2 and D3 rows with tier A/B, score,
dollars and an evidence JSON that the packet builder cites; D2 tier C rows, the informational "elevated" months, stay in DuckDB only so Postgres remains inside its disk budget), `providers` (slim NPPES rows for every NPI a detector touched, with ZIP
centroid and county), `county_risk` (dollars at risk per county by detector, for the map), and `summary` (the national totals the home
page reads, each detector's summary JSON, and the full text of `docs/methods.md` under key `methods_md`).

The console (`web/app/app/*`) reads all of that with the publishable key. Writes go through two route handlers with the secret key:
`POST /api/packets` builds a referral packet (deterministic TypeScript builder, drafted by Claude when `ANTHROPIC_API_KEY`
is set on the server) and stores it in `packets` and the private `verity-packets` bucket; `POST /api/reviews` records the reviewer's
decision in `reviews`, updates the packet status and re-weights the detector's evidence families in `score_weights` (Bayesian update
with a prior of four pseudo-reviews). The Python API (`api/main.py`) exposes the same operations plus `/verify` and Blue Button.
