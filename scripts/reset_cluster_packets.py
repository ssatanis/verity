"""Remove pre-generated network packets (network ids are rank-based and change when Detector 1 reruns)."""
import os, psycopg
from dotenv import load_dotenv; load_dotenv(".env")
with psycopg.connect(os.environ["DATABASE_URL"]) as c:
    n = c.execute("DELETE FROM public.packets WHERE subject_type = 'cluster' AND created_by = 'pregenerated'").rowcount; c.commit(); print("removed", n, "pregenerated network packets")
