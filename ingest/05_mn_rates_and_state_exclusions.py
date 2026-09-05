#!/usr/bin/env python3
"""(1) Parse Minnesota DHS published rate tables (DHS-3945 versions, EIDBI billing grid) into ingest/mn_published_rates.csv and load mn_rates.
   (2) Load the California, New York and Texas Medicaid exclusion lists into state_exclusions with NPIs extracted."""
import csv, os, re, duckdb, pdfplumber, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
rows = []
LINE = re.compile(r"^(?P<desc>.+?)\s+(?P<unit>15 Minutes|30 Minutes|Daily|Visit|Per Month|Per Item|One Way Trip|Per Mile|Each Time|One Meal Per|Per Print|Hour)\s+(?P<code>[A-Z]\d{4}|\d{5})\s*(?P<mods>(?:[A-Z][A-Z0-9]\s+)*)\$(?P<rate>[\d,]+\.\d{2})")
def parse_dhs3945(path, version):
    n = 0
    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages):
            for l in (page.extract_text() or "").splitlines():
                m = LINE.match(l.strip())
                if not m: continue
                unit = {"15 Minutes": 15, "30 Minutes": 30, "Hour": 60}.get(m["unit"])
                rows.append(dict(hcpcs=m["code"], modifiers=m["mods"].strip(), program=m["desc"].strip(), unit=m["unit"], unit_minutes=unit or "",
                                 rate=float(m["rate"].replace(",", "")), version=version, source=f"{os.path.basename(path)} p{i+1}")); n += 1
    print(f"parsed {n} rate lines from {path}")
parse_dhs3945("data/mn_rates/DHS-3945_PCA_rates.pdf", "2026-04")
if os.path.exists("data/mn_rates/DHS-3945_PCA_rates_2022-01.pdf") and open("data/mn_rates/DHS-3945_PCA_rates_2022-01.pdf","rb").read(4) == b"%PDF":
    parse_dhs3945("data/mn_rates/DHS-3945_PCA_rates_2022-01.pdf", "2022-01")
# EIDBI billing grid (Jan 2026): CMDE 97151 UB at $94.80 per 15-min unit is the only dollar figure printed; other EIDBI codes are percentages of an unpublished base
rows.append(dict(hcpcs="97151", modifiers="UB", program="EIDBI Comprehensive Multi-Disciplinary Evaluation (QSP)", unit="15 Minutes", unit_minutes=15, rate=94.80, version="2026-01", source="MN_EIDBI_billing_grid_2026-01.pdf p2"))
# EIDBI agency-established rates from the approved state plan amendment MN-24-0010 (Attachment 4.19-B page 8g, effective 2024-01-01;
# Level II providers are paid 80% and Level III 50% of these, so the 100% figure is the highest variant)
for h, prog, mins, rate in [("97151","EIDBI CMDE by CMDE provider (SPA MN-24-0010)",15,50.112),("97153","EIDBI intervention (SPA MN-24-0010)",15,20.178),
                            ("0373T","EIDBI intervention with two providers (SPA MN-24-0010)",15,24.192),("97154","EIDBI group intervention (SPA MN-24-0010)",15,6.72),
                            ("97155","EIDBI observation and direction (SPA MN-24-0010)",15,20.178),("97156","EIDBI family/caregiver training (SPA MN-24-0010)",15,20.178),
                            ("97157","EIDBI group family/caregiver training (SPA MN-24-0010)",15,6.72),("T1024","EIDBI coordinated care conference per provider per session (SPA MN-24-0010)",None,112.678)]:
    rows.append(dict(hcpcs=h, modifiers="", program=prog, unit="15 Minutes" if mins else "Session", unit_minutes=mins or "", rate=rate, version="2024-01", source="MN-24-0010_EIDBI_SPA.pdf p4"))
# MN Mental Health procedure grid figures supplied in the build playbook (not re-verified against the PDF here; flagged as such)
for h, prog, mins, rate in [("H2011","Crisis intervention (MH procedure grid)",15,40.58),("H2014","Skills training and development / CTSS (MH procedure grid)",15,14.25),
                            ("H2017","ARMHS psychosocial rehabilitation (MH procedure grid)",15,19.12),("96130","Psychological testing evaluation first hour (MH procedure grid)",60,124.36),
                            ("96131","Psychological testing evaluation additional hour (MH procedure grid)",60,85.05),("T2024","Housing Consultation T2024 U8 (HSS manual)",None,174.22),
                            ("H2015","Housing Stabilization Services H2015 U8 (HSS manual)",15,17.17)]:
    rows.append(dict(hcpcs=h, modifiers="", program=prog, unit="15 Minutes" if mins == 15 else ("Hour" if mins == 60 else "Encounter"), unit_minutes=mins or "", rate=rate, version="2026-playbook", source="build playbook (MN DHS MH procedure grid 2026 / HSS manual)"))
seen = set(); rows = [r for r in rows if not ((r["hcpcs"], r["modifiers"], r["program"], r["rate"], r["version"]) in seen or seen.add((r["hcpcs"], r["modifiers"], r["program"], r["rate"], r["version"])))]
with open("ingest/mn_published_rates.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
con = duckdb.connect("data/verity.duckdb")
con.execute("CREATE OR REPLACE TABLE mn_rates AS SELECT hcpcs, modifiers, program, unit, TRY_CAST(unit_minutes AS DOUBLE) AS unit_minutes, TRY_CAST(rate AS DOUBLE) AS rate, version, source FROM read_csv_auto('ingest/mn_published_rates.csv', all_varchar=true, header=true)")
print("mn_rates:", con.execute("SELECT COUNT(*), COUNT(DISTINCT hcpcs) FROM mn_rates").fetchone())
print("T1019 rows:", con.execute("SELECT modifiers, program, rate, version FROM mn_rates WHERE hcpcs='T1019' AND modifiers IN ('', 'UC') ORDER BY version").fetchall())

# ---- state exclusion lists ----
ca = pd.read_csv("data/clean/state_exclusions/CA_medical_suspended_ineligible_2026-07.csv", dtype=str).fillna("")
ca.columns = ["last_name","first_name","middle_name","aka_dba","addresses","provider_type","license","provider_numbers","date_of_suspension","active_period"]
ca_rows = []
for r in ca.itertuples(index=False):
    npis = sorted(set(re.findall(r"\b[12]\d{9}\b", r.provider_numbers or "")))
    is_org = (r.first_name in ("", "N/A"))
    base = dict(state="CA", source="CA Medi-Cal Suspended & Ineligible Provider List (July 2026)", name=(r.last_name if is_org else f"{r.first_name} {r.last_name}").strip(),
                last_name="" if is_org else r.last_name, first_name="" if is_org else r.first_name, middle_name=r.middle_name, is_org=is_org, provider_type=r.provider_type,
                license=r.license, excl_dt=pd.to_datetime(r.date_of_suspension, errors="coerce"), reinstated_dt=pd.NaT, active_period=r.active_period, address=r.addresses, ids=r.provider_numbers)
    for n in (npis or [None]): ca_rows.append({**base, "npi": n})
ny = pd.read_csv("data/state_exclusions/NY_omig_exclusions.txt", sep="\t", dtype=str, encoding="latin-1").fillna("")
ny_rows = [dict(state="NY", source="NY OMIG Medicaid Exclusion List (tab-delimited, Sept 2026)", name=r.PROVIDER_NAME.strip(), last_name="", first_name="", middle_name="", is_org=None,
                provider_type=r.PROVIDER_TYPE, license=r.LICENSE_NUMBER, excl_dt=pd.to_datetime(r.EXCLUSION_EFFECTIVE_DATE, errors="coerce"), reinstated_dt=pd.NaT, active_period="",
                address="", ids=r.NPI_Number, npi=(r.NPI_Number.strip() if re.fullmatch(r"[12]\d{9}", r.NPI_Number.strip()) else None)) for r in ny.itertuples(index=False)]
tx = pd.read_csv("data/state_exclusions/TX_oig_exclusions.csv", dtype=str).fillna("")
tx_rows = [dict(state="TX", source="Texas HHSC OIG Exclusions file (Sept 5 2026)", name=(r.CompanyName or f"{r.FirstName} {r.LastName}").strip(), last_name=r.LastName, first_name=r.FirstName,
                middle_name=r.MidInitial, is_org=bool(r.CompanyName), provider_type=r.Occupation, license=r.LicenseNumber, excl_dt=pd.to_datetime(r.StartDate, errors="coerce"),
                reinstated_dt=pd.to_datetime(r.ReinstatedDate, errors="coerce"), eligible_dt=pd.to_datetime(r.EligibleToReapplyDate, errors="coerce"), active_period="", address="", ids=r.NPI,
                npi=(re.sub(r"\.0$", "", r.NPI.strip()) if re.fullmatch(r"[12]\d{9}(\.0)?", r.NPI.strip()) else None)) for r in tx.itertuples(index=False)]
df = pd.DataFrame(ca_rows + ny_rows + tx_rows)
df["excl_dt"] = pd.to_datetime(df["excl_dt"]).dt.date; df["reinstated_dt"] = pd.to_datetime(df["reinstated_dt"]).dt.date
if "eligible_dt" not in df: df["eligible_dt"] = pd.NaT
df["eligible_dt"] = pd.to_datetime(df["eligible_dt"], errors="coerce").dt.date
con.execute("CREATE OR REPLACE TABLE state_exclusions AS SELECT * FROM df")
print("state_exclusions:", con.execute("SELECT state, COUNT(*), COUNT(npi), COUNT(DISTINCT npi), MIN(excl_dt), MAX(excl_dt) FROM state_exclusions GROUP BY 1 ORDER BY 1").fetchall())
con.execute("CHECKPOINT"); con.close()
