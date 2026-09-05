#!/usr/bin/env python3
"""Upsert one public.datasets row per object in the verity-raw and verity-derived bucket manifests, so the app can list what is loaded."""
import json, os, httpx, psycopg
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); load_dotenv()
URL = os.environ["SUPABASE_URL"]; src = {}
for m in json.load(open("data/manifest.json")): src[m["file"]] = m.get("url")
rows = []
for bucket in ("verity-raw", "verity-derived"):
    # authenticated endpoint bypasses the CDN cache in front of public objects (a just-uploaded manifest can be stale there for minutes)
    K = os.environ["SUPABASE_SECRET_KEY"]
    man = httpx.get(f"{URL}/storage/v1/object/authenticated/{bucket}/manifest.json", headers={"apikey": K, "Authorization": f"Bearer {K}"}, timeout=60).json()
    for o in man["objects"]:
        base = os.path.basename(o["obj"]).removesuffix(".gz")
        rows.append((f"{bucket}/{o['obj']}", base, src.get(base), o.get("local"), bucket, o["obj"], o.get("bytes"), o.get("rows"), "2026-09-05", o.get("sha256"),
                     o.get("sql") or ("gzipped source snapshot" if o["obj"].endswith(".gz") else "source snapshot")))
with psycopg.connect(os.environ["DATABASE_URL"]) as pg:
    pg.execute("DELETE FROM public.datasets WHERE id LIKE 'verity-raw/%' OR id LIKE 'verity-derived/%'")
    pg.cursor().executemany("""INSERT INTO public.datasets (id, name, source_url, local_path, storage_bucket, storage_path, bytes, rows, snapshot_date, sha256, notes)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET bytes=excluded.bytes, rows=excluded.rows, sha256=excluded.sha256, loaded_at=now()""", rows)
    n = pg.execute("SELECT COUNT(*) FROM public.datasets").fetchone()[0]
print(f"registered {len(rows)} storage objects; datasets table now has {n} rows")
