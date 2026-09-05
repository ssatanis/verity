#!/usr/bin/env python3
"""Ground truth: named cases from DOJ, HHS-OIG and state press releases (2025 to 2026) and a control set of large, well-known systems.
For each, find the NPI(s) in NPPES and the enrollment files, then report what each detector shows. Writes docs/validation.md. Honest by
design: the data snapshots end in 2024 (spending) and July 2026 (enrollment), so entities charged in 2026 may already have left the files."""
import json, os, sys, time, duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "detectors")
from _methods import md_table
CASES = [  # (label, name pattern, state, source)
  ("Gentle Touch Hospice Care (Shachar, June 2026 takedown)", "GENTLE TOUCH HOSPICE", "CA", "DOJ CDCA 2026-06"),
  ("Oxford Hospice Care (Shachar)", "OXFORD HOSPICE", "CA", "DOJ CDCA 2026-06"),
  ("Art of Hospice (Shachar)", "ART OF HOSPICE", "CA", "DOJ CDCA 2026-06"),
  ("Holly Trinity Hospice (Shachar)", "HOLLY TRINITY HOSPICE", "CA", "DOJ CDCA 2026-06"),
  ("Chateau d'Lumina Hospice (Shaklian plea, 2025)", "CHATEAU D%LUMINA", "CA", "DOJ CDCA 2025-11"),
  ("One Up Hospice Care (Palma sentence)", "ONE UP HOSPICE", "CA", "DOJ CDCA"),
  ("Rosewood Hospice and Palliative Care (Palma)", "ROSEWOOD HOSPICE & PALLIATIV", "CA", "DOJ CDCA"),
  ("Advance Hospice and Palliative Care (Palma)", "ADVANCE HOSPICE AND PALLIATI", "CA", "DOJ CDCA"),
  ("Smart Therapy Center (EIDBI, MN 2025)", "SMART THERAPY CENTER", "MN", "DOJ MN 2025-09"),
  ("Star Autism Center (EIDBI, MN 2025)", "STAR AUTISM CENTER", "MN", "DOJ MN 2025-12"),
  ("SafeLodgings (HSS, MN 2025)", "SAFELODGINGS", "MN", "MN AG 2025-12"),
  ("Leo Human Services (HSS, MN 2025)", "LEO HUMAN SERVICES", "MN", "DOJ MN 2025-09"),
  ("Liberty Plus (HSS, MN 2025)", "LIBERTY PLUS", "MN", "DOJ MN 2025-09"),
  ("Faladcare (HSS, MN 2025)", "FALADCARE", "MN", "DOJ MN 2025-09"),
]
CONTROLS = [("Mayo Clinic (Rochester)", "MAYO CLINIC", "MN"), ("Kaiser Foundation Hospitals", "KAISER FOUNDATION HOSPITALS", "CA"), ("Cleveland Clinic Foundation", "CLEVELAND CLINIC FOUNDATION", "OH"),
            ("Hennepin Healthcare", "HENNEPIN HEALTHCARE", "MN"), ("Cedars-Sinai Medical Center", "CEDARS-SINAI MEDICAL CENTER", "CA"), ("Massachusetts General Hospital", "MASSACHUSETTS GENERAL HOSPITAL", "MA")]
con = duckdb.connect("data/verity.duckdb", read_only=True)
have = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
def npis_for(pat, st):
    rows = con.execute("SELECT npi, org_name, city FROM nppes WHERE entity_type='2' AND upper(org_name) LIKE ? AND state = ? LIMIT 6", [f"%{pat}%", st]).fetchall()
    return rows
def profile(npis):
    if not npis: return {}
    lit = ",".join(f"'{n}'" for n in npis); out = {}
    out["risk"] = con.execute(f"SELECT npi, tier, ROUND(score,1), detectors, reasons FROM provider_risk WHERE npi IN ({lit})").fetchall() if "provider_risk" in have else []
    out["cluster"] = con.execute(f"SELECT m.npi, m.cluster_id, c.rank, c.eligible, ROUND(c.risk_score,1) FROM cluster_members m JOIN clusters c ON c.cluster_id=m.cluster_id WHERE m.npi IN ({lit})").fetchall() if "cluster_members" in have else []
    out["d3"] = con.execute(f"SELECT npi, source, tier, event_dt, ROUND(paid_after) FROM d3_top WHERE npi IN ({lit})").fetchall() if "d3_top" in have else []
    out["d2"] = con.execute(f"SELECT servicing_npi, months_impossible, months_umbrella, ROUND(peak_hours_per_day,1), max_patients FROM d2_top WHERE servicing_npi IN ({lit})").fetchall() if "d2_top" in have else []
    out["growth"] = con.execute(f"SELECT billing_npi, year, ROUND(paid_year), ROUND(concentration,2), ROUND(intensity_pct,2), label FROM d2_growth_flags WHERE billing_npi IN ({lit}) ORDER BY 1,2").fetchall() if "d2_growth_flags" in have else []
    out["lists"] = con.execute(f"SELECT npi, 'revoked' FROM revoked WHERE npi IN ({lit}) UNION SELECT npi, 'leie' FROM leie WHERE npi IN ({lit}) UNION SELECT npi, 'state:' || state FROM state_exclusions WHERE npi IN ({lit})").fetchall()
    out["medicaid"] = con.execute(f"SELECT npi, ROUND(SUM(paid)) FROM spend_any_month WHERE npi IN ({lit}) GROUP BY 1").fetchall()
    out["enrolled"] = con.execute(f"""SELECT "NPI", 'HOSPICE' FROM hospice WHERE "NPI" IN ({lit}) UNION SELECT "NPI", 'HHA' FROM hha WHERE "NPI" IN ({lit})""").fetchall()
    return out
def summarize(npis, p):
    if not npis: return "not found in NPPES"
    bits = []
    if p["cluster"]: bits.append("; ".join(f"community {c[1]} rank {c[2]} ({'ranked' if c[3] else 'held out'})" for c in p["cluster"]))
    if p["d3"]: bits.append("; ".join(f"D3 {d[1]} tier {d[2]} {d[3]} ${d[4]:,.0f} after" for d in p["d3"]))
    if p["d2"]: bits.append("; ".join(f"D2 impossible {d[1]} mo, umbrella {d[2]} mo, peak {d[3]} h/day, {d[4]} patients" for d in p["d2"]))
    if p["growth"]: bits.append("; ".join(f"growth {g[1]}: ${g[2]:,.0f}, {g[3]:.0%} in one code, intensity pct {g[4]}{' GROWTH_ANOMALY' if g[5] else ''}" for g in p["growth"]))
    if p["lists"]: bits.append("lists: " + ", ".join(f"{l[1]}" for l in p["lists"]))
    if p["risk"]: bits.append("; ".join(f"risk tier {r[1]} score {r[2]}" for r in p["risk"]))
    if not p["enrolled"] and not p["medicaid"]: bits.append("no Medicaid spending and not in CMS enrollment files (Medicare-only or already gone)")
    elif not p["enrolled"]: bits.append("Medicaid biller only (not a CMS hospice/HHA/SNF enrollment)")
    return " | ".join(bits) or "in data, no detector output"
rows = []; hits = 0
for label, pat, st, src in CASES:
    found = npis_for(pat, st); npis = [f[0] for f in found]; p = profile(npis)
    hit = bool(p.get("cluster") or p.get("d3") or (p.get("d2") and any(d[1] > 0 for d in p["d2"])) or any(g[5] for g in p.get("growth", [])) or p.get("lists"))
    hits += hit; rows.append((label, src, ", ".join(npis) or "", "yes" if hit else "no", summarize(npis, p)))
crows = []
for label, pat, st in CONTROLS:
    found = npis_for(pat, st); npis = [f[0] for f in found][:3]; p = profile(npis)
    flagged = bool(p.get("d3") or (p.get("d2") and any(d[1] > 0 for d in p["d2"])) or any(r[1] <= 2 for r in p.get("risk", [])))
    crows.append((label, ", ".join(npis), "flagged" if flagged else "clean", summarize(npis, p)))
md = f"""# Validation against named cases and controls

Generated {time.strftime('%Y-%m-%d %H:%M')} by scripts/ground_truth_check.py. Cases are providers named in DOJ, HHS-OIG and Minnesota Attorney General releases in 2025 and 2026; controls are large, well-known systems that should not be tier 1 or tier 2. Data snapshots: T-MSIS spending through 2024-12, CMS enrollment July 2026, LEIE and SAM September 2026, so an entity charged in 2026 may already have left the enrollment file, and Medicare-only hospices have no Medicaid spending to test.

**Named cases reached by at least one detector: {hits} of {len(CASES)}.**

{md_table(rows, ["case", "source", "NPI(s)", "reached", "what Verity shows"])}

**Controls.**

{md_table(crows, ["control", "NPI(s)", "result", "what Verity shows"])}

Reading the table: the Los Angeles hospices are Medicare-billing entities, so the network detector is the only one that can reach them, and it reaches them through shared owners, suites and addresses of revoked entities. The Minnesota housing stabilization and EIDBI companies are Medicaid-only billers that never appear in CMS enrollment files; they are visible to the growth and concentration indicator, and their per-patient volumes are not physically impossible in the aggregated data, which is why the fraud was proven with records, not arithmetic. A detector that flagged them as impossible would be wrong.
"""
open("docs/validation.md", "w").write(md); print(md)
