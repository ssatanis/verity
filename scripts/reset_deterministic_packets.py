"""Remove pre-generated packets that were built without a model so pregenerate_packets.py can redraft them with Claude."""
import os, psycopg
from dotenv import load_dotenv; load_dotenv(".env")
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    n = c.execute("DELETE FROM public.packets WHERE created_by = 'pregenerated' AND (model IS NULL OR model LIKE 'deterministic%')").rowcount; c.commit(); print("removed", n, "deterministic pregenerated packets")
