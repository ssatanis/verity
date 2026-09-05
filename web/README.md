# Verity web

Next.js 15 (App Router, Tailwind v4) on Supabase. `/` is the landing page, `/app` the console (overview map, communities, flags,
provider pages, Minnesota "show the math", methods), `/api/packets` and `/api/reviews` are the agent and feedback-loop endpoints.

## Run locally

```
source ../.envrc          # Node from ~/.local/node
npm install
npm run dev               # http://localhost:3000
```

## Deploy to Vercel

Import the `web/` directory as the project root. Environment variables:

| name | scope | value |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | all | https://kdyvtsajakswyxmfrygv.supabase.co |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | all | the `sb_publishable_...` key |
| `SUPABASE_SECRET_KEY` | server | the `sb_secret_...` key (packets and reviews) |
| `OPENAI_API_KEY` | server, optional | enables model-drafted packets; without it the deterministic builder is used |
| `OPENAI_MODEL` | server, optional | defaults to `gpt-5` |

Nothing in the app needs the DuckDB warehouse; every page reads Supabase tables that `ingest/sync_outputs.py` fills.
