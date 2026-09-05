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
    factors = []
    try:
        with _pg() as pg2:
            fx = pg2.execute("SELECT label, unit, value, percentile, factor, outlook FROM public.network_factors WHERE cluster_id = %s AND ((percentile >= 90 AND factor <> 'momentum') OR factor = 'momentum') ORDER BY percentile DESC NULLS LAST LIMIT 7", (cluster_id,)).fetchall()
        for r in fx:
            if r["factor"] == "momentum":
                if r.get("outlook"): factors.append(f"Momentum across the rate-of-change factors is {r['outlook']} (robust z {float(r['value'] or 0):.2f}); this is an indicative reading, not a validated forecast.")
            elif r["value"] is not None and r["percentile"] is not None:
                v = float(r["value"]); u = r["unit"]; vv = f"${v:,.0f}" if u == "$" else (f"{round(v*100)}%" if u == "share" else (f"{v:.1f} years" if u == "years" else (str(int(v)) if v.is_integer() else f"{v:.1f}")))
                factors.append(f"{r['label']}: {vv}, in the top {max(1, round(100 - float(r['percentile'])))}% of networks in the risky direction.")
    except Exception:
        factors = []
    return dict(kind="cluster", factors=factors, cluster=dict(c, features=feats, graph=None), members=members, owners=owners, flags=flags, revoked=rev, leie=leie, saturation=sat[:6])

def provider_evidence(npi):
    with _pg() as pg:
        p = pg.execute("SELECT * FROM public.providers WHERE npi = %s", (npi,)).fetchone()
        flags = pg.execute("SELECT * FROM public.flags WHERE npi = %s ORDER BY score DESC", (npi,)).fetchall()
        rev = pg.execute("SELECT * FROM public.revoked WHERE npi = %s", (npi,)).fetchall()
        leie = pg.execute("SELECT * FROM public.leie WHERE npi = %s", (npi,)).fetchall()
        enr = pg.execute("SELECT * FROM public.enrollments WHERE npi = %s", (npi,)).fetchall()
        clusters = pg.execute("SELECT c.id, c.summary, c.score, c.rank FROM public.cluster_members m JOIN public.clusters c ON c.id = m.cluster_id WHERE m.npi = %s", (npi,)).fetchall()
        risk = pg.execute("SELECT npi, name, tier, tier_label, detectors, score, dollars_at_risk, reasons, rank FROM public.provider_risk WHERE npi = %s", (npi,)).fetchone()
        try: codes = pg.execute("SELECT hcpcs, description, paid, share, months, dpm, dpm_pct, dpm_median, high_vector FROM public.provider_codes WHERE npi = %s ORDER BY rk LIMIT 6", (npi,)).fetchall()
        except Exception: codes = []
        try: mcodes = pg.execute("SELECT hcpcs, description, services, beneficiaries, paid, share, avg_submitted, avg_allowed, charge_ratio, peer_ratio_median FROM public.provider_codes_medicare WHERE npi = %s ORDER BY rk LIMIT 4", (npi,)).fetchall()
        except Exception: mcodes = []
    if not p and not flags and not risk: return None
    procedures = [dict(program="Medicaid", code=c["hcpcs"], description=c["description"], paid=float(c["paid"] or 0), share=float(c["share"] or 0), per_patient_month=c["dpm"], percentile=c["dpm_pct"], typical=c["dpm_median"], high_vector=bool(c["high_vector"])) for c in codes] + \
                 [dict(program="Medicare 2024", code=c["hcpcs"], description=c["description"], paid=float(c["paid"] or 0), share=float(c["share"] or 0), charge_ratio=c["charge_ratio"], peer_ratio=c["peer_ratio_median"]) for c in mcodes]
    return dict(kind="provider", provider=p or dict(npi=npi, name=(risk or {}).get("name")), flags=flags, revoked=rev, leie=leie, enrollments=enr, clusters=clusters, risk=risk, codes=codes, mcodes=mcodes, procedures=procedures)

def _src(x):
    x = str(x or "")
    if x == "MEDICARE_REVOKED": return "the Medicare revocation list"
    if x == "OIG_LEIE": return "the OIG exclusion list"
    if x == "NPPES_DEACTIVATED": return "the deactivated NPI list"
    if x == "MEDICAID_TERM": return "a state Medicaid termination list"
    if x.startswith("STATE_EXCL_"): return f"the {x[11:]} Medicaid exclusion list"
    if x.startswith("SAM"): return "the SAM.gov exclusion list"
    return x.replace("_", " ").lower()
_LAB = {"IMPOSSIBLE_BY_LINE_COUNT": "more hours than a day holds, even counting one unit per claim line", "IMPOSSIBLE_CONSERVATIVE_RATE": "more hours than a day holds at a conservative unit price",
        "IMPOSSIBLE_PER_PATIENT": "more than 24 hours per patient per day", "EXCEEDS_MN_DAILY_CAP": "over the state's daily cap for every patient every day", "IMPLAUSIBLE_OVER_16H": "over 16 hours per day",
        "ELEVATED_OVER_12H": "over 12 hours per day", "UMBRELLA_VOLUME": "agency volume billed under one clinician's NPI", "GROWTH_ANOMALY": "new biller with rapid growth concentrated on one code"}
def _lab(x): return _LAB.get(str(x or ""), str(x or "").replace("_", " ").lower())

def evidence_lines(ev):
    """Flat list of (source, statement) pairs, the citation trail every packet sentence must map to."""
    L = []
    if ev["kind"] == "cluster":
        c = ev["cluster"]; f = c["features"]
        kinds = ", ".join(f"{n} {one if n == 1 else many}" for n, one, many in ((c["n_hospice"], "hospice", "hospices"), (c["n_hha"], "home health agency", "home health agencies"), (c["n_snf"], "nursing facility", "nursing facilities")) if n)
        L.append(("clusters", f"Provider network {c['id']}: {c['n_providers']} providers around {c['city']}, {c.get('state') or ''} ({kinds}); network score {float(c['score']):.0f} of 100, ranked {c['rank']} nationally."))
        for x in (f.get("facts") or []): L.append(("network facts", x))
        for src, npis in (f.get("prov_labels") or {}).items(): L.append((_src(src), f"Providers with NPI {', '.join(npis)} appear on {_src(src)}."))
        for h in f.get("owner_hits") or []: L.append((_src(h[1]), f"An owner named {str(h[0]).title()} matches {_src(h[1])} at {h[2]} confidence (action dated {h[3]})."))
        if f.get("sat_per_10k") is not None: L.append(("CMS market saturation", f"The county has {float(f['sat_per_10k']):.1f} providers of this kind per 10,000 Medicare fee-for-service beneficiaries, {'above' if float(f.get('sat_z') or 0) > 0 else 'below'} the national norm."))
        dm, dc = float(c.get("dollars_at_risk") or 0), float(c.get("dollars_medicare") or 0)
        L.append(("T-MSIS provider spending 2024", (f"The providers billed Medicaid ${dm:,.0f} in 2024" + (f" and received ${dc:,.0f} in Medicare hospice and home health payments in 2023." if dc else ".")) if dm > 0 else (f"The providers received ${dc:,.0f} in Medicare hospice and home health payments in 2023 and billed no Medicaid in 2024." if dc else "The providers billed no Medicaid in 2024 and no Medicare hospice or home health payments are recorded for 2023.")))
        for fx in (ev.get("factors") or [])[:6]: L.append(("factor desk", fx))
        for m in ev["members"][:40]:
            labs = m.get("labels") or []; labs = json.loads(labs) if isinstance(labs, str) else labs
            kind = {"HHA": "Home health agency", "SNF": "Nursing facility"}.get(m["ptype"], "Hospice")
            L.append(("network members", f"{kind} {m['org_name']} (NPI {m['npi']}, {m['city']}, {m['state']})" + (f", incorporated {m['inc_date']}" if m.get("inc_date") else "") + (f", billed Medicaid ${float(m['medicaid_2024']):,.0f} in 2024" if float(m.get("medicaid_2024") or 0) > 0 else ", no Medicaid billing in 2024") + (f", on {' and '.join(_src(l) for l in labs)}" if labs else "") + "."))
        for r in ev["revoked"]: L.append(("Medicare revocation list", f"NPI {r['npi']} was revoked on {r['revoked_dt']} under {str(r['revocation_rsn'] or '').replace('_', ' ')}, barred from re-enrolling until {r['reenroll_bar_dt']}."))
        for r in ev["leie"]: L.append(("OIG exclusion list", f"NPI {r['npi']} was excluded on {r['excl_dt']} under section 1128 {r['excltype']}."))
        for fl in ev["flags"][:20]:
            e = fl["evidence"] if isinstance(fl["evidence"], dict) else json.loads(fl["evidence"] or "{}")
            if fl["detector"] == "D3": L.append(("paid after a list action", f"NPI {fl['npi']}: after the {_src(e.get('source'))} action of {e.get('event_dt')}, Medicaid paid ${float(e.get('paid_after') or 0):,.0f} across {e.get('months_paid_after')} later months."))
            else: L.append(("hours per day", f"NPI {fl['npi']}: {_lab(e.get('label'))} in {str(fl['month'])[:7]}, {float(fl['value'] or 0):,.1f} hours per day, ${float(fl['dollars'] or 0):,.0f} paid."))
    else:
        p = ev["provider"] or {}
        L.append(("providers/NPPES", f"NPI {p.get('npi')} {p.get('name')} ({'organization' if p.get('entity_type')=='2' else 'individual'}), {p.get('city')}, {p.get('state')}; taxonomy {p.get('taxonomy')}; Medicaid home state {p.get('medicaid_state')}."))
        r = ev.get("risk")
        for c in ev.get("codes") or []:
            L.append(("procedures billed, Medicaid", f"Code {c['hcpcs']}" + (f" ({c['description']})" if c.get("description") else "") + f": ${float(c['paid'] or 0):,.0f} paid over {c['months']} months, {round(float(c['share'] or 0)*100)}% of this provider's Medicaid dollars" + (f", ${float(c['dpm']):,.0f} per patient-month" if c.get("dpm") is not None else "") + (f", which ranks at the {round(float(c['dpm_pct'])*100)}th percentile of all providers billing this code (typical ${float(c['dpm_median'] or 0):,.0f})" if c.get("dpm_pct") is not None else "") + ("; this code family has a history of abuse" if c.get("high_vector") else "") + "."))
        for c in ev.get("mcodes") or []:
            L.append(("procedures billed, Medicare 2024", f"Code {c['hcpcs']} ({c['description']}): {int(c['services'] or 0):,} services for {int(c['beneficiaries'] or 0):,} beneficiaries, ${float(c['paid'] or 0):,.0f} paid; submitted ${float(c['avg_submitted'] or 0):,.0f} per service against ${float(c['avg_allowed'] or 0):,.0f} allowed, a ratio of {float(c['charge_ratio'] or 0):.1f}x" + (f" where the usual ratio for this code is {float(c['peer_ratio_median']):.1f}x" if c.get("peer_ratio_median") is not None else "") + "."))
        if r: L.append(("provider_risk", f"Evidence tier {r['tier']} ({r['tier_label']}); detectors {', '.join(r['detectors'] or [])}; dollars at risk ${float(r['dollars_at_risk'] or 0):,.0f} (figure of the detector that set the tier, not a sum); reasons: {r['reasons']}."))
        for r in ev["revoked"]: L.append(("Revocation_Extract", f"Revoked {r['revoked_dt']} under {r['revocation_rsn']}; re-enrollment bar to {r['reenroll_bar_dt']}."))
        for r in ev["leie"]: L.append(("OIG LEIE", f"Excluded {r['excl_dt']} under section 1128 {r['excltype']} ({r['general']})."))
        for fl in ev["flags"]:
            e = fl["evidence"] if isinstance(fl["evidence"], dict) else json.loads(fl["evidence"] or "{}")
            if fl["detector"] == "D3": L.append(("flags/D3 + T-MSIS spending", f"After the {e.get('source')} action of {e.get('event_dt')} ({e.get('reason')}), Medicaid paid ${float(e.get('paid_after') or 0):,.0f} across {e.get('months_paid_after')} service months ({e.get('first_month_after')} to {e.get('last_month_after')}); ${float(e.get('paid_before_12m') or 0):,.0f} in the 12 months before."))
            else: L.append(("flags/D2 + T-MSIS spending", f"{fl['month']}: {e.get('label')}; implied hours per {e.get('test_basis','day')} {float(fl['value'] or 0):.1f} (lower bound {float(e.get('hours_lb_per_day') or 0):.1f}, point {float(e.get('hours_pt_per_day') or 0):.1f}); ${float(e.get('paid') or 0):,.0f}; codes {e.get('codes')}; {e.get('n_billing_orgs')} billing organizations; rate source {e.get('rate_sources')}."))
        for en in ev["enrollments"]: L.append(("enrollments", f"Enrolled as {en['ptype']} {en['org_name']} ({en['enrollment_id']}), incorporated {en['inc_date']}, {en['city']}, {en['state']}."))
        for c in ev["clusters"]: L.append(("clusters", f"Member of community {c['id']} (rank {c['rank']}, score {float(c['score']):.2f}): {c['summary']}"))
    return L
