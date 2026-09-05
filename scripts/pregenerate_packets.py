#!/usr/bin/env python3
"""Draft referral packets for the demo subjects (top communities and top flagged providers) and store them in Supabase, so the
console shows packets even before a reviewer clicks Generate. Uses the deterministic builder unless OPENAI_API_KEY is set."""
import json, os, sys, uuid
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "api")); os.chdir(ROOT)
from dotenv import load_dotenv; load_dotenv(".env")
import psycopg, httpx
from packet import build_packet
n_clusters = int(sys.argv[1]) if len(sys.argv) > 1 else 5; n_providers = int(sys.argv[2]) if len(sys.argv) > 2 else 6
with psycopg.connect(os.environ["DATABASE_URL"]) as pg:
    clusters = [r[0] for r in pg.execute("SELECT id FROM public.clusters WHERE eligible ORDER BY rank LIMIT %s", (n_clusters,)).fetchall()]
    d3 = [r[0] for r in pg.execute("SELECT npi FROM public.flags WHERE detector='D3' AND tier='A' ORDER BY dollars DESC LIMIT %s", (n_providers,)).fetchall()]
    d2 = [r[0] for r in pg.execute("SELECT DISTINCT ON (npi) npi FROM public.flags WHERE detector='D2' AND tier='A' ORDER BY npi, score DESC LIMIT %s", (n_providers,)).fetchall()]
    K = os.environ["SUPABASE_SECRET_KEY"]
    for kind, ids in (("cluster", clusters), ("provider", d3 + d2)):
        for sid in ids:
            if pg.execute("SELECT 1 FROM public.packets WHERE subject_type=%s AND subject_id=%s LIMIT 1", (kind, sid)).fetchone(): print("have", kind, sid); continue
            p = build_packet(kind, sid)
            if not p: print("no evidence", kind, sid); continue
            pid = str(uuid.uuid4())
            pg.execute("INSERT INTO public.packets (id, subject_type, subject_id, status, packet, created_by, title, cluster_id, npi, model) VALUES (%s,%s,%s,'draft',%s,'pregenerated',%s,%s,%s,%s)",
                       (pid, kind, sid, json.dumps(p, default=str), p["title"], sid if kind == "cluster" else None, sid if kind == "provider" else None, p["model"]))
            try: httpx.post(f"{os.environ['SUPABASE_URL']}/storage/v1/object/verity-packets/{kind}/{sid}/{pid}.json", headers={"apikey": K, "Authorization": f"Bearer {K}", "Content-Type": "application/json", "x-upsert": "true"}, content=json.dumps(p, default=str).encode(), timeout=60)
            except Exception as e: print("storage copy failed", e)
            print("packet", kind, sid, p["model"], len(p["findings"]), "findings")
    pg.commit()
