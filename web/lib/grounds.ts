// Regulatory grounds selected from evidence types (mirror of api/grounds.py). Quoted text from the current eCFR via LII, 2026-09-05.
export const CFR: Record<string, string> = {
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
  "1003.200": "42 CFR 1003.200: civil monetary penalties for presenting claims for items or services not provided as claimed, for services furnished by an excluded person, or that are false or fraudulent.",
  "424.535(a)": "42 CFR 424.535(a): Medicare revocation grounds; the basis of the Medicare action cited in the evidence (for example (a)(2) exclusion, (a)(3) felony, (a)(4) false or misleading information, (a)(5) not operational at the practice location, (a)(8) abuse of billing privileges).",
  "424.518": "42 CFR 424.518: Medicare screening levels; newly enrolling home health agencies and hospices are screened at the high level (fingerprint background checks and site visits).",
};
export const MAP: Record<string, string[]> = {
  MEDICARE_REVOKED_PAID_AFTER: ["455.416(c)", "455.436", "455.23", "424.535(a)"],
  OIG_LEIE_PAID_AFTER: ["1001.1901", "455.436", "455.23", "1003.200"],
  STATE_EXCL_PAID_AFTER: ["455.416(c)", "455.436", "455.23"],
  SAM_PAID_AFTER: ["455.436", "1001.1901"],
  NPPES_DEACTIVATED_PAID_AFTER: ["455.436", "455.416(d)"],
  IMPOSSIBLE_HOURS: ["455.23", "1003.200", "455.410"],
  PER_PATIENT_IMPOSSIBLE: ["455.23", "1003.200"],
  MN_DAILY_CAP: ["455.23", "1003.200"],
  UMBRELLA_VOLUME: ["455.410", "455.104"],
  GROWTH_ANOMALY: ["455.410", "455.450"],
  NETWORK_SHARED_OWNERS: ["455.104", "455.432", "455.450", "424.518"],
  NETWORK_SHARED_ADDRESS: ["455.432", "455.416(g)", "455.450"],
  NETWORK_INCORPORATION_BURST: ["455.450", "455.432", "424.518"],
  NETWORK_OWNER_ON_LEIE: ["1001.1901", "455.416(b)", "455.104"],
  NETWORK_ADDRESS_OF_REVOKED_ENTITY: ["455.416(c)", "455.432", "455.416(g)"],
  NETWORK_MEMBER_ON_LIST: ["455.416(c)", "1001.1901", "455.436"],
};
const J = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
export function evidenceTypes(kind: "cluster" | "provider", features: any, flags: any[], revoked: any[], leie: any[]): string[] {
  const T: string[] = [];
  if (kind === "cluster") {
    const f = J(features);
    if ((f.owner_multi ?? 0) >= 1) T.push("NETWORK_SHARED_OWNERS");
    if (Math.max(f.addr_share ?? 0, f.unit_share ?? 0) >= 2 || (f.phone_share ?? 0) >= 2) T.push("NETWORK_SHARED_ADDRESS");
    if ((f.burst_90 ?? 0) >= 3) T.push("NETWORK_INCORPORATION_BURST");
    if ((f.owner_hits ?? []).some((h: any) => h[1] === "OIG_LEIE" || h[1] === "SAM")) T.push("NETWORK_OWNER_ON_LEIE");
    if ((f.excl_addr_hits ?? []).length) T.push("NETWORK_ADDRESS_OF_REVOKED_ENTITY");
    if (f.prov_labels && Object.keys(f.prov_labels).length) T.push("NETWORK_MEMBER_ON_LIST");
  }
  for (const fl of flags ?? []) {
    const e = J(fl.evidence);
    if (fl.detector === "D3") {
      const s = e.source ?? "";
      T.push(s === "MEDICARE_REVOKED" ? "MEDICARE_REVOKED_PAID_AFTER" : s === "OIG_LEIE" ? "OIG_LEIE_PAID_AFTER" : s.startsWith("STATE_EXCL") ? "STATE_EXCL_PAID_AFTER" : s.startsWith("SAM") ? "SAM_PAID_AFTER" : s === "NPPES_DEACTIVATED" ? "NPPES_DEACTIVATED_PAID_AFTER" : "");
    } else if (fl.detector === "D2") {
      const l = e.label ?? "";
      T.push(l === "IMPOSSIBLE_PER_PATIENT" ? "PER_PATIENT_IMPOSSIBLE" : l === "EXCEEDS_MN_DAILY_CAP" ? "MN_DAILY_CAP" : l.startsWith("IMPOSSIBLE") ? "IMPOSSIBLE_HOURS" : l === "UMBRELLA_VOLUME" ? "UMBRELLA_VOLUME" : l === "GROWTH_ANOMALY" ? "GROWTH_ANOMALY" : "");
    }
  }
  if (kind === "provider") { if (revoked?.length) T.push("MEDICARE_REVOKED_PAID_AFTER"); if (leie?.length) T.push("OIG_LEIE_PAID_AFTER"); }
  return [...new Set(T.filter(Boolean))];
}
export function groundsFor(types: string[]) {
  const seen: string[] = [];
  for (const t of types) for (const g of MAP[t] ?? []) if (!seen.includes(g)) seen.push(g);
  return (seen.length ? seen : ["455.410"]).map(c => ({ cfr: c, text: CFR[c] }));
}
