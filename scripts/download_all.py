#!/usr/bin/env python3
"""Verity data downloader. Manifest-driven, resumable (curl -C -), parallel.
Usage: python3 download_all.py [--tier 1|2|all] [--workers N]
Re-run any time; finished files are skipped."""
import json, os, subprocess, sys, time, urllib.request, concurrent.futures as cf, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
ap = argparse.ArgumentParser(); ap.add_argument("--tier", default="all"); ap.add_argument("--workers", type=int, default=4)
args = ap.parse_args()

jobs = []  # (tier, subdir, filename, url)
def add(tier, sub, url, name=None):
    name = name or url.split("/")[-1].replace("%20", "_")
    jobs.append((tier, sub, name, url))

# ---------- data.cms.gov catalog ----------
cat = json.load(urllib.request.urlopen("https://data.cms.gov/data.json", timeout=120))["dataset"]
def by_title(t): 
    for x in cat:
        if x["title"].strip().lower() == t.lower(): return x
    raise KeyError(t)
def csvs(ds):
    out = []
    for d in ds.get("distribution", []):
        u = d.get("downloadURL", "")
        if u.lower().endswith((".csv", ".zip")): out.append((d.get("temporal", ""), d.get("title", ""), u))
    return out
def latest(ds): return sorted(csvs(ds), key=lambda z: z[0])[-1][2]

ENROLL = ["Hospice Enrollments","Hospice All Owners","Home Health Agency Enrollments","Home Health Agency All Owners",
 "Skilled Nursing Facility Enrollments","Skilled Nursing Facility All Owners","Skilled Nursing Facility Change of Ownership",
 "Skilled Nursing Facility Change of Ownership - Owner Information","Hospital Enrollments","Hospital All Owners",
 "Hospital Change of Ownership","Hospital Change of Ownership - Owner Information","Federally Qualified Health Center Enrollments",
 "Federally Qualified Health Center All Owners","Rural Health Clinic Enrollments","Rural Health Clinic All Owners",
 "Medicare Fee-For-Service  Public Provider Enrollment","Order and Referring","Revalidation Due Date List",
 "Revalidation Reassignment List","Revalidation Clinic Group Practice Reassignment","Opt Out Affidavits",
 "Revoked Medicare Providers and Suppliers","Nursing Home Chain Performance Measures"]
for t in ENROLL:
    try: add(1, "cms_enrollment", latest(by_title(t)))
    except Exception as e: print("SKIP", t, e)
for t in ["Market Saturation & Utilization State-County","Market Saturation & Utilization Core-Based Statistical Areas"]:
    add(1, "cms_program_integrity", latest(by_title(t)))
for t in ["Provider of Services File - Internet Quality Improvement and Evaluation System",
          "Provider of Services File - Quality Improvement and Evaluation System","Provider of Services File - Clinical Laboratories"]:
    add(1, "cms_pos", latest(by_title(t)))
# Post-acute PUFs: all years (small)
for t in ["Medicare Post-Acute Care Utilization - Hospice by Geography and Provider",
          "Medicare Post-Acute Care Utilization - Home Health Agency by Geography and Provider",
          "Medicare Post-Acute Care Utilization - Home Health Agency by Geography, Provider and Service",
          "Medicare Post-Acute Care Utilization - Skilled Nursing Facility by Geography and Provider",
          "Medicare Post-Acute Care Utilization - Skilled Nursing Facility by Geography, Provider and Service",
          "Medicare Post-Acute Care Utilization - Inpatient Rehabilitation Facility by Geography and Provider",
          "Medicare Post-Acute Care Utilization - Long-Term Care Hospital by Geography and Provider"]:
    for temporal, title, u in csvs(by_title(t)):
        add(1, "cms_utilization/post_acute", u, f"{temporal[:4]}_{u.split('/')[-1]}")
# Big utilization files: all years, latest year first (tier 2)
BIG = ["Medicare Physician & Other Practitioners - by Provider and Service","Medicare Physician & Other Practitioners - by Provider",
 "Medicare Part D Prescribers - by Provider and Drug","Medicare Part D Prescribers - by Provider",
 "Medicare Durable Medical Equipment, Devices & Supplies - by Referring Provider and Service",
 "Medicare Durable Medical Equipment, Devices & Supplies - by Referring Provider",
 "Medicare Durable Medical Equipment, Devices & Supplies - by Supplier and Service",
 "Medicare Durable Medical Equipment, Devices & Supplies - by Supplier",
 "Medicare Inpatient Hospitals - by Provider and Service","Medicare Inpatient Hospitals - by Provider",
 "Medicare Outpatient Hospitals - by Provider and Service"]
for t in BIG:
    sub = "cms_utilization/" + t.split(" - ")[0].replace("Medicare ","").replace(" & ","_").replace(", ","_").replace(" ","_")
    rows = sorted(csvs(by_title(t)), key=lambda z: z[0], reverse=True)
    for i,(temporal,title,u) in enumerate(rows):
        add(2 if i < 2 else 3, sub, u, f"{temporal[:4]}_{u.split('/')[-1]}")

# ---------- HHS Open Data (T-MSIS Medicaid) ----------
B = "https://stopendataprod.blob.core.windows.net/datasets"
add(1, "medicaid_tmsis", f"{B}/medicare-revoked-providers-and-suppliers/2026-03-02/dataset/medicare-revoked-providers-and-suppliers.parquet")
add(2, "medicaid_tmsis", f"{B}/medicaid-provider-enrollment-segments/2026-07-24/dataset/medicaid-provider-enrollment-segments.parquet")
add(2, "medicaid_tmsis", f"{B}/medicaid-provider-spending/2026-02-09/dataset/medicaid-provider-spending.parquet")
add(2, "medicaid_tmsis", f"{B}/medicaid-provider-spending-ndc/2026-07-24/dataset/medicaid-provider-spending-ndc.parquet")

# ---------- OIG, NPPES, openFDA, Open Payments ----------
add(1, "oig_leie", "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv", "LEIE_UPDATED.csv")
add(1, "openfda", "https://api.fda.gov/drug/shortages.json?limit=1000", "drug_shortages.json")
add(1, "openfda", "https://download.open.fda.gov/drug/enforcement/drug-enforcement-0001-of-0001.json.zip")
add(1, "openfda", "https://download.open.fda.gov/drug/ndc/drug-ndc-0001-of-0001.json.zip")
add(2, "nppes", "https://download.cms.gov/nppes/NPPES_Data_Dissemination_August_2026_V2.zip")
add(1, "nppes", "https://download.cms.gov/nppes/NPPES_Deactivated_NPI_Report_081026_V2.zip")
OP="https://download.cms.gov/openpayments"
add(1, "open_payments", f"{OP}/SMRY_RPTS_P06302026_06032026/PBLCTN_SMRY_BY_CR_BY_NTR_OF_PYMT_PGYRall_P06302026_06032026.csv")
add(1, "open_payments", f"{OP}/SMRY_RPTS_P06302026_06032026/PBLCTN_RPTG_ORG_SMRY_P06302026_06032026.csv")
add(2, "open_payments", f"{OP}/PGYR2025_P06302026_06032026/OP_DTL_OWNRSHP_PGYR2025_P06302026_06032026.csv")
add(3, "open_payments", f"{OP}/PGYR2025_P06302026_06032026/OP_DTL_GNRL_PGYR2025_P06302026_06032026.csv")
add(3, "open_payments", f"{OP}/PGYR2024_P06302026_06032026/OP_DTL_GNRL_PGYR2024_P06302026_06032026.csv")

# ---------- Care Compare (provider-data) ----------
pd_items = json.load(urllib.request.urlopen("https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items", timeout=120))
WANT = ["Hospice - General Information","Hospice - Provider Data","Hospice - State Data","Hospice - National Data","Hospice - Zip Data",
 "Home Health Care Agencies","Home Health Care - Zip Codes","Home Health Care - State by State Data","Hospital General Information",
 "Provider Information","Skilled Nursing Facility Quality Reporting Program - Provider Data","Long-Term Care Hospital - Provider Data",
 "Inpatient Rehabilitation Facility - Provider Data","Expanded Home Health Value-Based Purchasing (HHVBP) Model - Agency Data",
 "Hospice care - Provider CAHPS Hospice Survey Data","Veterans Health Administration Provider Level Data"]
for x in pd_items:
    if x.get("title") in WANT:
        for d in x.get("distribution", []):
            if d.get("downloadURL"): add(1, "care_compare", d["downloadURL"])
# national downloadable file (clinicians) + penalties etc.
for x in pd_items:
    t = x.get("title","").lower()
    if any(k in t for k in ["national downloadable file","penalt","ownership","fire safety","health deficiencies"]):
        for d in x.get("distribution", []):
            if d.get("downloadURL"): add(2, "care_compare", d["downloadURL"])

# ---------- run ----------
sel = [j for j in jobs if args.tier == "all" or int(args.tier) >= j[0]]
os.makedirs(DATA, exist_ok=True)
json.dump([dict(tier=t,subdir=s,file=f,url=u) for t,s,f,u in jobs], open(os.path.join(DATA,"manifest.json"),"w"), indent=1)
def run(j):
    tier, sub, name, url = j
    d = os.path.join(DATA, sub); os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, name); done = dst + ".done"
    if os.path.exists(done): return f"skip {sub}/{name}"
    t0 = time.time()
    r = subprocess.run(["curl","-sSL","--retry","5","--retry-all-errors","-C","-","-o",dst,url])
    if r.returncode == 0:
        open(done,"w").write(url); return f"ok   {sub}/{name} {os.path.getsize(dst)/1e6:.1f}MB {time.time()-t0:.0f}s"
    return f"FAIL {sub}/{name} rc={r.returncode} {url}"
sel.sort(key=lambda j: j[0])
with cf.ThreadPoolExecutor(args.workers) as ex:
    for res in ex.map(run, sel): print(res, flush=True)
print("ALL DONE", flush=True)
