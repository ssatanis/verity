#!/usr/bin/env python3
"""Find which Supavisor pooler host serves this project (the direct db host is IPv6-only). Writes DATABASE_URL into .env."""
import os, re, sys, urllib.parse, psycopg
from dotenv import load_dotenv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); load_dotenv()
ref = os.environ["SUPABASE_PROJECT_REF"]; pw = os.environ["PGPASSWORD"]
regions = ["us-east-1","us-east-2","us-west-1","us-west-2","ca-central-1","eu-west-1","eu-west-2","eu-west-3","eu-central-1","eu-central-2","eu-north-1","ap-southeast-1","ap-southeast-2","ap-northeast-1","ap-northeast-2","ap-south-1","sa-east-1"]
found = None
for n in (0, 1):
    for r in regions:
        host = f"aws-{n}-{r}.pooler.supabase.com"
        try:
            with psycopg.connect(host=host, port=5432, user=f"postgres.{ref}", password=pw, dbname="postgres", connect_timeout=6, sslmode="require") as c:
                v = c.execute("select version()").fetchone()[0]; found = host; print("OK", host, v[:40]); break
        except Exception as e:
            msg = str(e).strip().splitlines()[0][:80]; print("no", host, msg)
    if found: break
if not found: sys.exit("no pooler host accepted the credentials")
url = f"postgresql://postgres.{ref}:{urllib.parse.quote(pw, safe='')}@{found}:5432/postgres?sslmode=require"
env = open(".env").read()
env = re.sub(r"^DATABASE_URL=.*$", f"DATABASE_URL={url}", env, flags=re.M)
env = re.sub(r"^POOLER_HOST=.*$\n?", "", env, flags=re.M) + f"POOLER_HOST={found}\n"
open(".env", "w").write(env); print("wrote DATABASE_URL to .env")
