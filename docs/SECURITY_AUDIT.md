# Security audit, 2026-09-05

Scope: the Next.js console (`web/`), the FastAPI service (`api/`), the Supabase serving layer (row level security, storage, grants) and the repository itself. Method: the categories from Anthropic's claude-code-security-review (injection, authentication and authorization, secrets, code execution, data exposure) checked by reading every route and then attacking the running servers with malformed and hostile input, plus dependency audits and a live check of the database policies with the public key. Denial of service and rate limiting are out of scope by that method's rules.

## Verified and left as is

| area | result |
|---|---|
| Row level security | Every public table has RLS on with a SELECT-only policy. With the publishable key an INSERT returns 42501, an UPDATE or DELETE matches zero rows. Supabase's default table grants still list INSERT, UPDATE and DELETE for `anon`; RLS is what blocks them. |
| Storage | `verity-packets` is private and invisible to the publishable key (list and public paths both fail). `verity-raw` and `verity-derived` are public by design (downloadable public datasets). |
| SQL | Every Postgres query uses bound parameters. DuckDB queries in `api/lookup.py` are parameterized; `api/verify.py` inlines NPI literals only after the `^[12]\d{9}$` check. The `search_providers` function is `stable`, invoker rights, parameterized. |
| Cross-site scripting | React escapes every rendered value; the case chat renders markdown without raw HTML; the PDF is built from text nodes. A reflected `<script>` in the search query does not appear in the page. |
| Secrets | Nothing sensitive in git history or in tracked files; `.env` and `web/.env.local` are ignored. `web/.env.local` was world-readable on disk and is now mode 600. |
| Dependencies | pip-audit: no known vulnerabilities. npm audit: only `postcss` inside `next` 15.5 (build-time, fix requires Next 16, a breaking upgrade; not applied). |
| Concurrency | Thirty parallel warehouse requests to the API all return 200; the API opens a fresh read-only DuckDB connection per call and never holds the single-writer lock. |

## Fixed in this audit

1. **Input validation on every write route** (`web/lib/validate.ts`, used by `/api/ask`, `/api/packets`, `/api/reviews`, the PDF route). Malformed JSON, non-string ids, objects where strings were expected, and path-like ids now return 400 instead of 500. Before, an object passed as `subject_id` reached the model and was billed. Subject ids must be a ten-digit NPI or a network id; packet ids must be UUIDs; chat history is limited to eight user or assistant turns with string content; questions and notes are length-capped.
2. **Network review re-weighting was silently broken.** `/api/reviews` embedded `clusters!inner(features)` through PostgREST, but `reviews` has no foreign key to `clusters`, so the query failed, the weights never moved and the message reported zero reviews. It now fetches the features by subject id. Verified end to end on a draft network packet, then reverted.
3. **Security headers** in `web/next.config.ts`: `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy`, `Permissions-Policy`, HSTS; `X-Powered-By` removed.
4. **FastAPI** (`api/main.py`): `check_subject` on packets and chat; UUID check on reviews; `/retrain` limited to D1, D2, D3; `/clusters` no longer errors on a state filter (`%s::text` cast) and clamps `limit`; `/verify*` answer 503 "warehouse busy" while a detector holds DuckDB instead of 500; Blue Button bundle upload rejects malformed FHIR with 400 (`api/bluebutton.py` skips entries that are not objects); the OAuth callback checks for a code and turns token exchange failures into 502.
5. **Provider page** rejects non-NPI paths before querying and URL-encodes the id when calling the local API.
6. **Tests**: `tests/test_api_hardening.py` (seven tests, no warehouse or key needed) cover the 400 paths; the full suite is 16 passing.

## Accepted risks (open console, hackathon demo)

- The console has no sign in by decision. Anyone who can reach it can draft packets (Claude Opus spend), post reviews and read reviewer notes, since `packets` and `reviews` are publicly readable. Before any public exposure, put the deployment behind Vercel deployment protection or the health plan's single sign-on and drop the public read policy on `reviews`.
- The FastAPI service allows every origin and has open write endpoints for the same reason.
- `/sam/lookup` proxies the SAM.gov key; its daily quota was already exhausted during the audit (HTTP 429 until 2026-09-06 00:00 UTC).

## How it was tested

- 25 hostile requests against the console (malformed JSON, wrong types, path traversal in ids, PostgREST filter characters, 5,000-character queries, null bytes, `page=abc`, `tier=abc`, script tags) and 30 against the API, before and after the fixes.
- Live checks with the publishable key against PostgREST and Storage.
- `npx tsc --noEmit`, `npm run build`, `pytest` (16 passed), `scripts/verify_all.py` (39 passed; the two warehouse failures were a detector holding the DuckDB lock at the time).
