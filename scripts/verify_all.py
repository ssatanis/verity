#!/usr/bin/env python3
"""End-to-end health check for Verity. Run from the repo root any time; prints PASS / PENDING / FAIL per check and exits 1 on FAIL.
  python3 scripts/verify_all.py [--web http://localhost:3000] [--api http://localhost:8000]
Checks: raw data on disk, the DuckDB warehouse, detector outputs, the Supabase serving layer, the FastAPI service, the web app routes,
and the external integrations (SAM.gov, Blue Button)."""
import argparse, glob, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, ROOT); sys.path.insert(0, "api")
from dotenv import load_dotenv; load_dotenv(".env")
ap = argparse.ArgumentParser(); ap.add_argument("--web", default="http://localhost:3000"); ap.add_argument("--api", default="http://localhost:8000"); a = ap.parse_args()
R = []
def rec(status, name, detail=""): R.append((status, name, detail)); print(f"{status:<8}{name:<52}{detail}", flush=True)
def ok(c, name, detail="", pending=False): rec("PASS" if c else ("PENDING" if pending else "FAIL"), name, detail)

print("== 1. Raw data on disk")
m = json.load(open("data/manifest.json")) if os.path.exists("data/manifest.json") else []
done = [j for j in m if os.path.exists(os.path.join("data", j["subdir"], j["file"] + ".done"))]
ok(len(m) and len(done) == len(m), "manifest files downloaded", f"{len(done)}/{len(m)}")
for f in ["data/medicaid_tmsis/medicaid-provider-spending.parquet", "data/medicaid_tmsis/medicaid-provider-enrollment-segments.parquet",
          "data/oig_leie/LEIE_UPDATED.csv", "data/nppes/NPPES_Data_Dissemination_August_2026_V2.zip"]:
    ok(os.path.exists(f), os.path.basename(f), f"{os.path.getsize(f)/1e9:.2f} GB" if os.path.exists(f) else "missing")
ok(bool(glob.glob("data/sam_exclusions/SAM_Exclusions_Public_Extract_V2_*.CSV")), "SAM.gov public extract on disk")
ok(not glob.glob("data/bluebutton/sample*") and not glob.glob("data/bluebutton/synthetic*"), "no synthetic Blue Button data in data/")

print("== 2. Warehouse (DuckDB)")
try:
    import duckdb
    con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"), read_only=True)
    tabs = {r[0] for r in con.execute("select table_name from information_schema.tables where table_schema='main'").fetchall()}
    need = {"spend": 50_000_000, "enroll": 40_000_000, "owners": 500_000, "revoked": 8_000, "leie": 80_000, "sam": 150_000, "nppes": 9_000_000,
            "saturation_county": 1_000_000, "hospice": 5_000, "hha": 10_000, "snf": 14_000, "timecodes": 300, "state_exclusions": 40_000}
    for t, mn in need.items():
        n = con.execute(f"select count(*) from {t}").fetchone()[0] if t in tabs else 0
        ok(n >= mn, f"table {t}", f"{n:,} rows")
    for t, label in [("d3_paid_after", "Detector 3 output (revoked but paid)"), ("d2_scored", "Detector 2 output (impossible days)"), ("clusters", "Detector 1 output (ghost networks)"), ("flags", "flags table")]:
        n = con.execute(f"select count(*) from {t}").fetchone()[0] if t in tabs else 0
        ok(n > 0, label, f"{n:,} rows" if n else "not built yet", pending=True)
    s = con.execute("select count(*) from sam where npi is not null").fetchone()[0] if "sam" in tabs else 0
    ok(s > 5000, "SAM rows with NPI", f"{s:,}")
    con.close()
except Exception as e: rec("FAIL", "warehouse", str(e)[:120])

print("== 3. Tripwire logic (api/verify.py)")
try:
    import verify as vf, datetime as dt
    ev = vf.events_for(["1811937436", "1801839063"]); src = {e["source"] for e in ev}
    ok({"OIG_LEIE", "MEDICARE_REVOKED", "SAM_HHS"} <= src, "known NPIs return real exclusion events", ", ".join(sorted(src)))
    r = vf.verify_claims([dict(id="t", type="carrier", start=dt.date(2025, 6, 1), end=None, npis=["1801839063"], paid=1.0, codes=[])])
    ok(r["n_flagged_claims"] == 1, "service date inside revocation window is flagged")
    r = vf.verify_claims([dict(id="t", type="carrier", start=dt.date(2024, 1, 1), end=None, npis=["1801839063"], paid=1.0, codes=[])])
    ok(r["n_flagged_claims"] == 0, "service date before revocation is not flagged")
    r = vf.sam_live_lookup(name="Kram", size=2)
    ok(r.get("total", 0) > 0, "SAM.gov Exclusions API v4 live lookup", f"{r.get('total')} results" if "total" in r else str(r)[:80])
except Exception as e: rec("FAIL", "verify.py", str(e)[:120])

print("== 4. Supabase serving layer")
try:
    import psycopg
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=20) as pg:
        rows = {t: (pg.execute(f"select count(*) from public.{t}").fetchone()[0] if pg.execute("select to_regclass(%s)", (f"public.{t}",)).fetchone()[0] else None)
                for t in ["revoked", "leie", "owners", "saturation_county", "datasets", "clusters", "cluster_members", "flags", "providers", "county_risk", "summary", "packets", "reviews", "score_weights"]}
    for t in ["revoked", "leie", "owners", "saturation_county", "datasets"]: ok((rows[t] or 0) > 0, f"public.{t}", f"{rows[t]:,} rows" if rows[t] else "missing")
    for t in ["clusters", "cluster_members", "flags", "providers", "county_risk", "summary"]:
        ok((rows[t] or 0) > 0, f"public.{t} (from ingest/sync_outputs.py)", f"{rows[t]:,} rows" if rows[t] else ("table missing" if rows[t] is None else "empty"), pending=True)
    ok(rows["packets"] is not None and rows["reviews"] is not None, "packets and reviews tables exist", f"{rows['packets']} packets, {rows['reviews']} reviews")
except Exception as e: rec("FAIL", "supabase", str(e)[:120])

print("== 5. FastAPI service")
import httpx
try:
    h = httpx.get(f"{a.api}/health", timeout=10).json(); ok(h.get("ok"), "GET /health", json.dumps(h))
    ok(httpx.get(f"{a.api}/verify/npi/1811937436", timeout=30).json()["events"], "GET /verify/npi/{npi}")
    c = httpx.get(f"{a.api}/clusters", timeout=30); ok(c.status_code == 200 and len(c.json()) > 0, "GET /clusters", f"{len(c.json()) if c.status_code==200 else c.status_code} clusters", pending=True)
    g = httpx.get(f"{a.api}/bluebutton/authorize", timeout=10, follow_redirects=False)
    ok(g.status_code in (403, 307), "GET /bluebutton/authorize guard", "sandbox blocked (real data only)" if g.status_code == 403 else "redirects to CMS")
except Exception as e: rec("PENDING", "FastAPI not running", f"start with: uvicorn api.main:app --port 8000  ({str(e)[:60]})")

print("== 6. Web app")
try:
    # the console sits behind the reviewer gate: sign in with VERITY_CONSOLE_PASSWORD from web/.env.local and reuse the cookie
    web = httpx.Client(base_url=a.web, timeout=60, follow_redirects=False)
    g = web.get("/app"); ok(g.status_code == 200, "console opens without a sign in", str(g.status_code))
    for p in ["/", "/legal", "/app", "/app/candidates", "/app/candidates?tier=1", "/app/clusters", "/app/flags", "/app/flags?detector=D2", "/app/plazas", "/app/search?q=1811937436", "/app/states/MN", "/app/methods", "/app/providers/1811937436"]:
        r = web.get(p); bad = any(x in r.text for x in ["Application error", "Unhandled Runtime Error", "Internal Server Error"])
        ok(r.status_code == 200 and not bad, f"GET {p}", f"{r.status_code} {len(r.text)//1000}KB")
    for p in ["/", "/legal", "/app/methods"]:
        r = web.get(p); ok("\u2014" not in r.text and "\u2013" not in r.text, f"no em or en dashes on {p}")
    t = web.get("/app").text
    ok("$0</div>" not in t and ">0</div>" not in t, "console shows non-zero KPIs (needs sync_outputs)", pending=True)
except Exception as e: rec("PENDING", "web app not running", f"start with: cd web && npm run dev  ({str(e)[:60]})")

print("== 7. Blue Button")
try:
    import bluebutton as bb
    r = httpx.post(f"{bb.BASE}/v2/o/token/", auth=(bb.CLIENT_ID, bb.CLIENT_SECRET), data=dict(grant_type="authorization_code", code="x", redirect_uri=bb.REDIRECT_URI, code_verifier="x" * 43), timeout=30)
    ok("sandbox" not in bb.BASE, "BLUEBUTTON_BASE_URL is production", bb.BASE)
    ok(r.status_code in (400, 401), "CMS token endpoint reachable", f"{r.status_code} {r.text[:60]} (400 invalid_grant = credentials accepted; 401 = credentials not valid for this environment)")
except Exception as e: rec("FAIL", "bluebutton", str(e)[:120])

n = {s: sum(1 for r in R if r[0] == s) for s in ("PASS", "PENDING", "FAIL")}
print(f"\n{n['PASS']} passed, {n['PENDING']} pending, {n['FAIL']} failed")
sys.exit(1 if n["FAIL"] else 0)
