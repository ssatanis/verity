"""Regulatory grounds for Medicaid referral packets, selected from evidence types, never from keyword matching on prose.
Verity's packets go to state Medicaid program integrity units and payers; the operative rules are 42 CFR part 455 and 42 CFR 1001.
Medicare revocation grounds (42 CFR 424.535) are cited only as the basis of the Medicare action that the state must act on.
Quoted text is from the current eCFR (retrieved through the Legal Information Institute on 2026-09-05)."""
CFR = {
    "455.416(c)": "42 CFR 455.416(c): the State Medicaid agency must deny or terminate the enrollment of any provider that is terminated on or after January 1, 2011 under Medicare or under the Medicaid program or CHIP of any other State and is included in the termination database under 455.417.",
    "455.416(b)": "42 CFR 455.416(b): the State Medicaid agency must deny or terminate enrollment where a person with a 5 percent or greater direct or indirect ownership interest has been convicted of a criminal offense related to Medicare, Medicaid or CHIP in the last 10 years.",
    "455.416(d)": "42 CFR 455.416(d): termination where the provider, or a person with an ownership or control interest, or an agent or managing employee, fails to submit timely or accurate information.",
    "455.416(g)": "42 CFR 455.416(g): the agency may terminate or deny enrollment if the provider falsified any information on the application or the identity of the applicant cannot be verified.",
    "455.436": "42 CFR 455.436: states must confirm identity and determine exclusion status through routine checks of the Social Security Death Master File, NPPES, the LEIE and the EPLS (now SAM), upon enrollment and reenrollment and, for the LEIE and EPLS, no less frequently than monthly.",
    "455.23": "42 CFR 455.23(a): the State Medicaid agency must suspend all Medicaid payments to a provider after determining there is a credible allegation of fraud for which an investigation is pending, unless there is good cause not to suspend or to suspend only in part; 455.23(d) requires referral to the Medicaid Fraud Control Unit.",
    "455.410": "42 CFR 455.410: all providers must be screened under subpart E as a condition of enrollment, and states must revalidate enrollment at least every 5 years.",
    "455.104": "42 CFR 455.104: providers must disclose every person with an ownership or control interest of 5 percent or more, managing employees, and family or business relationships among them; the agency must obtain the disclosures before enrolling and at revalidation.",
    "455.432": "42 CFR 455.432: the State Medicaid agency must conduct pre-enrollment and post-enrollment site visits of providers designated as moderate or high risk to verify that the information submitted is accurate and to determine compliance with enrollment requirements.",
    "455.450": "42 CFR 455.450: screening levels; newly enrolling home health agencies and providers subject to a payment suspension or previously excluded are screened at the high risk level (fingerprint criminal background checks and site visits).",
    "1001.1901": "42 CFR 1001.1901: no payment will be made by Medicare, Medicaid or any other federal health care program for any item or service furnished by an excluded individual or entity, directly or indirectly, on or after the effective date of the exclusion.",
    "1001.1901(c)": "42 CFR 1001.1901(c): payment prohibition extends to items or services furnished at the medical direction or on the prescription of an excluded physician when the person furnishing the item knew or had reason to know of the exclusion.",
    "1003.200": "42 CFR 1003.200: civil monetary penalties for presenting claims for items or services not provided as claimed, for services furnished by an excluded person, or that are false or fraudulent.",
    "424.535(a)": "42 CFR 424.535(a): Medicare revocation grounds; the basis of the Medicare action cited in the evidence (for example (a)(2) exclusion, (a)(3) felony, (a)(4) false or misleading information, (a)(5) not operational at the practice location, (a)(8) abuse of billing privileges).",
    "424.518": "42 CFR 424.518: Medicare screening levels; newly enrolling home health agencies and hospices are screened at the high level (fingerprint background checks and site visits).",
}
# evidence type -> ordered grounds
MAP = {
    "MEDICARE_REVOKED_PAID_AFTER": ["455.416(c)", "455.436", "455.23", "424.535(a)"],
    "OIG_LEIE_PAID_AFTER": ["1001.1901", "455.436", "455.23", "1003.200"],
    "STATE_EXCL_PAID_AFTER": ["455.416(c)", "455.436", "455.23"],
    "SAM_PAID_AFTER": ["455.436", "1001.1901"],
    "NPPES_DEACTIVATED_PAID_AFTER": ["455.436", "455.416(d)"],
    "CROSS_STATE_TERMINATION": ["455.416(c)", "455.436"],
    "IMPOSSIBLE_HOURS": ["455.23", "1003.200", "455.410"],
    "PER_PATIENT_IMPOSSIBLE": ["455.23", "1003.200"],
    "MN_DAILY_CAP": ["455.23", "1003.200"],
    "UMBRELLA_VOLUME": ["455.410", "455.104"],
    "NETWORK_SHARED_OWNERS": ["455.104", "455.432", "455.450", "424.518"],
    "NETWORK_SHARED_ADDRESS": ["455.432", "455.416(g)", "455.450"],
    "NETWORK_INCORPORATION_BURST": ["455.450", "455.432", "424.518"],
    "NETWORK_OWNER_ON_LEIE": ["1001.1901", "455.416(b)", "455.104"],
    "NETWORK_ADDRESS_OF_REVOKED_ENTITY": ["455.416(c)", "455.432", "455.416(g)"],
    "NETWORK_MEMBER_ON_LIST": ["455.416(c)", "1001.1901", "455.436"],
}
def grounds_for_types(types):
    seen = []
    for t in types:
        for g in MAP.get(t, []):
            if g not in seen: seen.append(g)
    return [dict(cfr=g, text=CFR[g]) for g in (seen or ["455.410"])]
def evidence_types(ev):
    """Derive evidence types from the structured evidence bundle (api/evidence.py), not from prose."""
    T = []
    if ev["kind"] == "cluster":
        f = ev["cluster"]["features"] or {}
        if (f.get("owner_multi") or 0) >= 1: T.append("NETWORK_SHARED_OWNERS")
        if max(f.get("addr_share") or 0, f.get("unit_share") or 0) >= 2 or (f.get("phone_share") or 0) >= 2: T.append("NETWORK_SHARED_ADDRESS")
        if (f.get("burst_90") or 0) >= 3: T.append("NETWORK_INCORPORATION_BURST")
        if any(h[1] in ("OIG_LEIE", "SAM") for h in (f.get("owner_hits") or [])): T.append("NETWORK_OWNER_ON_LEIE")
        if f.get("excl_addr_hits"): T.append("NETWORK_ADDRESS_OF_REVOKED_ENTITY")
        if f.get("prov_labels"): T.append("NETWORK_MEMBER_ON_LIST")
    for fl in ev.get("flags", []):
        e = fl.get("evidence") or {}
        if isinstance(e, str):
            import json; e = json.loads(e)
        if fl.get("detector") == "D3":
            src = (e.get("source") or "")
            if src == "MEDICARE_REVOKED": T.append("MEDICARE_REVOKED_PAID_AFTER")
            elif src == "OIG_LEIE": T.append("OIG_LEIE_PAID_AFTER")
            elif src.startswith("STATE_EXCL"): T.append("STATE_EXCL_PAID_AFTER")
            elif src.startswith("SAM"): T.append("SAM_PAID_AFTER")
            elif src == "NPPES_DEACTIVATED": T.append("NPPES_DEACTIVATED_PAID_AFTER")
        elif fl.get("detector") == "D2":
            lab = e.get("label") or ""
            if lab == "IMPOSSIBLE_PER_PATIENT": T.append("PER_PATIENT_IMPOSSIBLE")
            elif lab == "EXCEEDS_MN_DAILY_CAP": T.append("MN_DAILY_CAP")
            elif lab.startswith("IMPOSSIBLE"): T.append("IMPOSSIBLE_HOURS")
            elif lab == "UMBRELLA_VOLUME": T.append("UMBRELLA_VOLUME")
    for r in ev.get("revoked", []): T.append("MEDICARE_REVOKED_PAID_AFTER") if ev["kind"] == "provider" else None
    for r in ev.get("leie", []): T.append("OIG_LEIE_PAID_AFTER") if ev["kind"] == "provider" else None
    seen = []; [seen.append(t) for t in T if t and t not in seen]
    return seen
