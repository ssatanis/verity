"""Evidence assembly for the investigator agent: every fact comes from a named table with the row it came from.
Works against Supabase Postgres (the serving layer) so the same code runs locally and behind the API."""
import json, os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
def _pg(): return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)

CFR = {
    "424.535(a)(2)": "Provider or supplier conduct: exclusion, debarment or suspension by a federal program",
    "424.535(a)(3)": "Felony conviction within the preceding 10 years detrimental to the best interests of the program",
    "424.535(a)(4)": "False or misleading information on the enrollment application",
    "424.535(a)(5)": "On-site review: the provider is no longer operational at the practice location",
    "424.535(a)(8)": "Abuse of billing privileges (claims that could not have been furnished, or a pattern of non-compliant claims)",
    "424.535(a)(9)": "Failure to report changes required by 424.516",
    "424.535(a)(12)": "Termination, revocation or suspension by another federal program or a state Medicaid agency",
    "424.535(a)(19)": "Affiliation with a previously sanctioned entity that poses an undue risk of fraud, waste or abuse",
    "455.416(c)": "State Medicaid agencies must terminate providers terminated by Medicare or another state's Medicaid program for cause",
    "455.23": "Suspension of Medicaid payments upon a credible allegation of fraud",
    "1001.1901": "Scope and effect of an OIG exclusion: no federal health care program payment for items or services furnished by an excluded person",
    "455.410": "Enrollment and screening of all Medicaid providers",
}

def cluster_evidence(cluster_id):
    with _pg() as pg:
        c = pg.execute("SELECT * FROM public.clusters WHERE id = %s", (cluster_id,)).fetchone()
        if not c: return None
        members = pg.execute("SELECT * FROM public.cluster_members WHERE cluster_id = %s ORDER BY medicaid_2024 DESC NULLS LAST", (cluster_id,)).fetchall()
        npis = [m["npi"] for m in members if m["npi"]]
        flags = pg.execute("SELECT * FROM public.flags WHERE npi = ANY(%s) ORDER BY score DESC", (npis,)).fetchall() if npis else []
        rev = pg.execute("SELECT * FROM public.revoked WHERE npi = ANY(%s)", (npis,)).fetchall() if npis else []
        leie = pg.execute("SELECT * FROM public.leie WHERE npi = ANY(%s)", (npis,)).fetchall() if npis else []
        owners = pg.execute("SELECT * FROM public.owners WHERE enrollment_id = ANY(%s) ORDER BY enrollment_id", ([m["enrollment_id"] for m in members],)).fetchall()
        sat = pg.execute("SELECT * FROM public.saturation_county WHERE county_fips = %s AND aggregation_level = 'COUNTY' ORDER BY reference_period DESC", (c["county_fips"],)).fetchall() if c["county_fips"] else []
    feats = c["features"] if isinstance(c["features"], dict) else json.loads(c["features"] or "{}")
    return dict(kind="cluster", cluster=dict(c, features=feats, graph=None), members=members, owners=owners, flags=flags, revoked=rev, leie=leie, saturation=sat[:6])

def provider_evidence(npi):
    with _pg() as pg:
        p = pg.execute("SELECT * FROM public.providers WHERE npi = %s", (npi,)).fetchone()
        flags = pg.execute("SELECT * FROM public.flags WHERE npi = %s ORDER BY score DESC", (npi,)).fetchall()
        rev = pg.execute("SELECT * FROM public.revoked WHERE npi = %s", (npi,)).fetchall()
        leie = pg.execute("SELECT * FROM public.leie WHERE npi = %s", (npi,)).fetchall()
        enr = pg.execute("SELECT * FROM public.enrollments WHERE npi = %s", (npi,)).fetchall()
        clusters = pg.execute("SELECT c.id, c.summary, c.score, c.rank FROM public.cluster_members m JOIN public.clusters c ON c.id = m.cluster_id WHERE m.npi = %s", (npi,)).fetchall()
        risk = pg.execute("SELECT npi, name, tier, tier_label, detectors, score, dollars_at_risk, reasons, rank FROM public.provider_risk WHERE npi = %s", (npi,)).fetchone()
    if not p and not flags and not risk: return None
    return dict(kind="provider", provider=p or dict(npi=npi, name=(risk or {}).get("name")), flags=flags, revoked=rev, leie=leie, enrollments=enr, clusters=clusters, risk=risk)

def evidence_lines(ev):
    """Flat list of (source, statement) pairs, the citation trail every packet sentence must map to."""
    L = []
    if ev["kind"] == "cluster":
        c = ev["cluster"]; f = c["features"]
        L.append(("clusters", f"Community {c['id']} ({c['n_providers']} providers: {c['n_hospice']} hospice, {c['n_hha']} home health, {c['n_snf']} SNF) centred on {c['city']}; risk score {float(c['score']):.2f}, rank {c['rank']}."))
        if f.get("burst_90", 0) >= 2: L.append(("hospice/hha/snf enrollment files, INCORPORATION DATE", f"{f['burst_90']} members were incorporated within a 90-day window {f.get('burst_90_span')}."))
        if max(f.get("addr_share", 0), f.get("unit_share", 0)) >= 2: L.append(("enrollment ADDRESS LINE 1 / NPPES practice location", f"Up to {max(f['addr_share'], f['unit_share'])} members share one practice address{' (same suite)' if f.get('unit_share',0) >= 2 else ''}."))
        if f.get("owner_multi", 0): L.append(("All-Owners files, resolved persons and organisations", f"{f['owner_multi']} owner(s) are tied to three or more members (largest: {f['max_owner_degree']})."))
        if f.get("phone_share", 0) >= 2: L.append(("NPPES practice telephone", f"{f['phone_share']} members list the same telephone number."))
        for src, npis in (f.get("prov_labels") or {}).items(): L.append((src, f"Member NPI(s) {', '.join(npis)} appear on {src}."))
        for h in f.get("owner_hits") or []: L.append((h[1], f"Owner '{h[0]}' matches {h[1]} at {h[2]} confidence (effective {h[3]})."))
        if f.get("sat_per_10k") is not None: L.append(("CMS Market Saturation and Utilization", f"The county has {float(f['sat_per_10k']):.1f} providers per 10,000 FFS beneficiaries (robust z {float(f.get('sat_z') or 0):+.1f})."))
        L.append(("T-MSIS provider spending 2024", f"Members billed Medicaid ${float(c['dollars_at_risk'] or 0):,.0f} in 2024" + (f"; Medicare 2023 hospice/HHA payments ${float(c['dollars_medicare'] or 0):,.0f}." if c.get("dollars_medicare") else ".")))
        for m in ev["members"][:40]: L.append(("cluster_members", f"{m['ptype']} {m['org_name']} (NPI {m['npi']}, {m['city']}, {m['state']}; incorporated {m['inc_date']}; Medicaid 2024 ${float(m['medicaid_2024'] or 0):,.0f}; labels {m['labels']})."))
        for r in ev["revoked"]: L.append(("Revocation_Extract", f"NPI {r['npi']} revoked {r['revoked_dt']} under {r['revocation_rsn']} (bar to {r['reenroll_bar_dt']})."))
        for r in ev["leie"]: L.append(("OIG LEIE", f"NPI {r['npi']} excluded {r['excl_dt']} under section 1128 {r['excltype']}."))
        for fl in ev["flags"][:20]:
            e = fl["evidence"] if isinstance(fl["evidence"], dict) else json.loads(fl["evidence"] or "{}")
            L.append((f"flags/{fl['detector']}", f"NPI {fl['npi']} {fl['metric']} = {float(fl['value'] or 0):,.2f} (threshold {fl['threshold']}) in {fl['month']}; ${float(fl['dollars'] or 0):,.0f}; {e.get('label') or e.get('source') or ''}."))
    else:
        p = ev["provider"] or {}
        L.append(("providers/NPPES", f"NPI {p.get('npi')} {p.get('name')} ({'organisation' if p.get('entity_type')=='2' else 'individual'}), {p.get('city')}, {p.get('state')}; taxonomy {p.get('taxonomy')}; Medicaid home state {p.get('medicaid_state')}."))
        r = ev.get("risk")
        if r: L.append(("provider_risk", f"Evidence tier {r['tier']} ({r['tier_label']}); detectors {', '.join(r['detectors'] or [])}; dollars at risk ${float(r['dollars_at_risk'] or 0):,.0f} (figure of the detector that set the tier, not a sum); reasons: {r['reasons']}."))
        for r in ev["revoked"]: L.append(("Revocation_Extract", f"Revoked {r['revoked_dt']} under {r['revocation_rsn']}; re-enrollment bar to {r['reenroll_bar_dt']}."))
        for r in ev["leie"]: L.append(("OIG LEIE", f"Excluded {r['excl_dt']} under section 1128 {r['excltype']} ({r['general']})."))
        for fl in ev["flags"]:
            e = fl["evidence"] if isinstance(fl["evidence"], dict) else json.loads(fl["evidence"] or "{}")
            if fl["detector"] == "D3": L.append(("flags/D3 + T-MSIS spending", f"After the {e.get('source')} action of {e.get('event_dt')} ({e.get('reason')}), Medicaid paid ${float(e.get('paid_after') or 0):,.0f} across {e.get('months_paid_after')} service months ({e.get('first_month_after')} to {e.get('last_month_after')}); ${float(e.get('paid_before_12m') or 0):,.0f} in the 12 months before."))
            else: L.append(("flags/D2 + T-MSIS spending", f"{fl['month']}: {e.get('label')}; implied hours per {e.get('test_basis','day')} {float(fl['value'] or 0):.1f} (lower bound {float(e.get('hours_lb_per_day') or 0):.1f}, point {float(e.get('hours_pt_per_day') or 0):.1f}); ${float(e.get('paid') or 0):,.0f}; codes {e.get('codes')}; {e.get('n_billing_orgs')} billing organisations; rate source {e.get('rate_sources')}."))
        for en in ev["enrollments"]: L.append(("enrollments", f"Enrolled as {en['ptype']} {en['org_name']} ({en['enrollment_id']}), incorporated {en['inc_date']}, {en['city']}, {en['state']}."))
        for c in ev["clusters"]: L.append(("clusters", f"Member of community {c['id']} (rank {c['rank']}, score {float(c['score']):.2f}): {c['summary']}"))
    return L
