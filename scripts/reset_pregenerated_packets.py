"""Remove every pre-generated packet so pregenerate_packets.py redrafts them with the current builder and prompts."""
import os, psycopg
from dotenv import load_dotenv; load_dotenv(".env")
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    n = c.execute("DELETE FROM public.packets WHERE created_by = 'pregenerated'").rowcount; c.commit(); print("removed", n, "pregenerated packets")
