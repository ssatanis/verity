// Referral candidate packet: evidence lines from the serving tables, grounds from the evidence-type mapping (never keyword matching), deterministic draft when no model is configured.
import { SupabaseClient } from "@supabase/supabase-js";
import { CFR, evidenceTypes, groundsFor } from "./grounds";
export { CFR };
const J = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
const $ = (v: any) => `$${Number(v ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
export type Line = [string, string];
export async function evidenceLines(sb: SupabaseClient, kind: "cluster" | "provider", id: string): Promise<{ lines: Line[]; types: string[] }> {
  const L: Line[] = [];
  if (kind === "cluster") {
    const { data: c } = await sb.from("clusters").select("*").eq("id", id).maybeSingle(); if (!c) return { lines: L, types: [] };
    const f = J(c.features); const { data: members } = await sb.from("cluster_members").select("*").eq("cluster_id", id).order("medicaid_2024", { ascending: false }).limit(40);
    const npis = (members ?? []).map(m => m.npi).filter(Boolean);
    const [{ data: rev }, { data: leie }, { data: flags }] = await Promise.all([sb.from("revoked").select("*").in("npi", npis), sb.from("leie").select("*").in("npi", npis), sb.from("flags").select("*").in("npi", npis).order("score", { ascending: false }).limit(20)]);
    L.push(["clusters", `Provider community ${c.id} (${c.n_providers} enrollments: ${c.n_hospice} hospice, ${c.n_hha} home health, ${c.n_snf} skilled nursing) centred on ${c.city}, ${c.state}; composite score ${Number(c.score).toFixed(2)}, rank ${c.rank} among eligible communities.`]);
    if ((f.burst_90 ?? 0) >= 2) L.push(["enrollment files, INCORPORATION DATE", `${f.burst_90} distinct organisations in the community were incorporated within one 90-day window ${JSON.stringify(f.burst_90_span)}.`]);
    if (Math.max(f.addr_share ?? 0, f.unit_share ?? 0) >= 2) L.push(["enrollment ADDRESS LINE 1 and NPPES practice location", `Up to ${Math.max(f.addr_share ?? 0, f.unit_share ?? 0)} members share one practice address${(f.unit_share ?? 0) >= 2 ? " down to the suite" : " at the building level"}.`]);
    if (f.owner_multi) L.push(["All-Owners files (ownership and managing roles only), resolved persons and organisations", `${f.owner_multi} owner(s) are tied to three or more members (largest: ${f.max_owner_degree} members).`]);
    if ((f.phone_share ?? 0) >= 2) L.push(["NPPES practice telephone", `${f.phone_share} members list the same telephone number.`]);
    if ((f.ao_share ?? 0) >= 2) L.push(["NPPES authorized official", `${f.ao_share} members list the same authorized official.`]);
    for (const [src, list] of Object.entries(f.prov_labels ?? {})) L.push([src, `Member NPI(s) ${(list as string[]).join(", ")} appear on ${src}.`]);
    for (const h of f.owner_hits ?? []) L.push([h[1], `Owner '${h[0]}' matches ${h[1]} at ${h[2]} confidence (effective ${h[3]}).`]);
    if (f.excluded_link) L.push(["Revocation_Extract and LEIE addresses", `${f.excluded_link} member(s) are registered at the address of a revoked or excluded entity (same suite weighted 1.0, same building 0.5).`]);
    if (f.sat_per_10k != null) L.push(["CMS Market Saturation and Utilization", `The county has ${Number(f.sat_per_10k).toFixed(1)} providers per 10,000 FFS beneficiaries (robust z ${Number(f.sat_z ?? 0).toFixed(1)} against all counties).`]);
    L.push(["T-MSIS provider spending 2024", `Members billed Medicaid ${$(c.dollars_at_risk)} in 2024${c.dollars_medicare ? `; Medicare 2023 hospice and home health payments ${$(c.dollars_medicare)}.` : "."}`]);
    for (const m of members ?? []) L.push(["cluster_members", `${m.ptype} ${m.org_name} (NPI ${m.npi}, ${m.city}, ${m.state}; incorporated ${m.inc_date ?? "not stated"}; Medicaid 2024 ${$(m.medicaid_2024)}; lists ${JSON.stringify(J(m.labels))}).`]);
    for (const r of rev ?? []) L.push(["Revocation_Extract", `NPI ${r.npi} revoked ${r.revoked_dt} under ${r.revocation_rsn} (re-enrollment bar to ${r.reenroll_bar_dt}).`]);
    for (const r of leie ?? []) L.push(["OIG LEIE", `NPI ${r.npi} excluded ${r.excl_dt} under section 1128 ${r.excltype}.`]);
    for (const fl of flags ?? []) { const e = J(fl.evidence); L.push([`flags/${fl.detector}`, `NPI ${fl.npi} ${fl.metric} = ${Number(fl.value).toFixed(2)} (threshold ${fl.threshold}) in ${String(fl.month).slice(0, 7)}; ${$(fl.dollars)}; ${e.label ?? e.source ?? ""}.`]); }
    return { lines: L, types: evidenceTypes("cluster", f, flags ?? [], rev ?? [], leie ?? []) };
  }
  const [{ data: p }, { data: flags }, { data: rev }, { data: leie }, { data: enr }, { data: cm }, { data: risk }] = await Promise.all([sb.from("providers").select("*").eq("npi", id).maybeSingle(), sb.from("flags").select("*").eq("npi", id).order("score", { ascending: false }), sb.from("revoked").select("*").eq("npi", id), sb.from("leie").select("*").eq("npi", id), sb.from("enrollments").select("*").eq("npi", id), sb.from("cluster_members").select("cluster_id, clusters(id,rank,score,summary,features)").eq("npi", id), sb.from("provider_risk").select("*").eq("npi", id).maybeSingle()]);
  if (!p && !(flags ?? []).length && !risk) return { lines: L, types: [] };
  L.push(["providers/NPPES", `NPI ${id} ${p?.name ?? risk?.name ?? ""} (${(p?.entity_type ?? risk?.entity_type) === "2" ? "organisation" : "individual"}), ${p?.city ?? risk?.city}, ${p?.state ?? risk?.state}; taxonomy ${p?.taxonomy ?? risk?.taxonomy}; Medicaid home state ${p?.medicaid_state ?? risk?.medicaid_state ?? "not stated"}.`]);
  if (risk) L.push(["provider_risk", `Evidence tier ${risk.tier} (${risk.tier_label}); detectors ${(risk.detectors ?? []).join(", ")}; dollars at risk ${$(risk.dollars_at_risk)} (figure of the detector that set the tier, not a sum); reasons: ${risk.reasons}.`]);
  for (const r of rev ?? []) L.push(["Revocation_Extract", `Medicare revocation effective ${r.revoked_dt} under ${r.revocation_rsn}; re-enrollment bar to ${r.reenroll_bar_dt}.`]);
  for (const r of leie ?? []) L.push(["OIG LEIE", `OIG exclusion ${r.excl_dt} under section 1128 ${r.excltype} (${r.general})${r.rein_dt ? `; reinstated ${r.rein_dt}` : ""}.`]);
  for (const fl of flags ?? []) { const e = J(fl.evidence);
    if (fl.detector === "D3") L.push(["flags/D3 + T-MSIS spending", `After the ${e.source} action of ${e.event_dt} (${e.reason}), Medicaid service months continued: ${$(e.paid_after)} across ${e.months_paid_after} months (${e.first_month_after} to ${e.last_month_after})${e.window_end ? `, window closed ${e.window_end}` : ""}; ${$(e.paid_before_12m)} in the 12 months before the action.`]);
    else if (fl.metric === "growth_and_concentration") L.push(["flags/D2 growth", `${String(fl.month).slice(0, 4)}: ${e.label}; ${$(fl.dollars)} paid, ${Number(e.concentration ?? 0) * 100 | 0}% on ${e.dominant_code}; intensity percentile ${Number(e.intensity_pct ?? 0).toFixed(2)}.`]);
    else L.push(["flags/D2 + T-MSIS spending", `${String(fl.month).slice(0, 7)}: ${e.label}; implied personal-service hours per ${e.test_basis ?? "day"} ${Number(fl.value).toFixed(1)} (rate-free lower bound ${Number(e.hours_lb_per_day ?? 0).toFixed(1)}, point ${Number(e.hours_pt_per_day ?? 0).toFixed(1)}); ${$(e.paid)}; codes ${(e.codes ?? []).join(" ")}; ${e.n_billing_orgs} billing organisation(s); rate source ${e.rate_sources}.`]); }
  for (const en of enr ?? []) L.push(["enrollments", `Enrolled as ${en.ptype} ${en.org_name} (${en.enrollment_id}), incorporated ${en.inc_date ?? "not stated"}, ${en.city}, ${en.state}.`]);
  const feats = (cm ?? []).map((c: any) => J(c.clusters?.features));
  for (const c of cm ?? []) L.push(["clusters", `Member of provider community ${(c as any).clusters?.id} (rank ${(c as any).clusters?.rank}): ${(c as any).clusters?.summary}`]);
  const types = new Set(evidenceTypes("provider", {}, flags ?? [], rev ?? [], leie ?? [])); for (const f of feats) for (const t of evidenceTypes("cluster", f, [], [], [])) types.add(t);
  return { lines: L, types: [...types] };
}
const CAVEATS: Record<string, string> = {
  MEDICARE_REVOKED_PAID_AFTER: "A revocation can be reversed on appeal or through a corrective action plan; confirm the current enrollment status with the state and in PECOS before acting.",
  OIG_LEIE_PAID_AFTER: "Check the LEIE for a reinstatement date; services dated before the exclusion but billed after it are lawful.",
  SAM_PAID_AFTER: "SAM debarments from agencies other than HHS restrict federal contracting; confirm that the state's own screening policy applies to them.",
  STATE_EXCL_PAID_AFTER: "State lists carry reinstatements and administrative terminations; confirm the action type with the listing agency.",
  NPPES_DEACTIVATED_PAID_AFTER: "An NPI deactivated after a death or retirement can still receive lawful late claims for services rendered before the deactivation date.",
  IMPOSSIBLE_HOURS: "The rendering NPI on Medicaid claims is often the supervising clinician under state convention; confirm which organisations employ or contract with this clinician before treating the hours as one person's work.",
  PER_PATIENT_IMPOSSIBLE: "Per-patient hours can exceed the calendar under legitimate group or crisis services when the code is billed per staff member; confirm the code's billing unit with the state.",
  MN_DAILY_CAP: "State caps carry prior-authorisation exceptions; confirm whether an exception was on file.",
  UMBRELLA_VOLUME: "One organisation billing under a supervising NPI is common and lawful in several states; this is a records request, not a finding.",
  GROWTH_ANOMALY: "Rapid growth and concentration on one code describe many legitimate new specialty agencies; this indicator is informational.",
  NETWORK_SHARED_OWNERS: "Common ownership across several enrollments is lawful and ordinary; the indicator is the combination with formation timing, shared suites and list links.",
  NETWORK_INCORPORATION_BURST: "Incorporation bursts also occur when a legitimate operator expands or restructures.",
  NETWORK_SHARED_ADDRESS: "Shared suites and phones are ordinary in medical office buildings and with registered-agent, accountant or answering-service addresses; the address alone proves nothing.",
  NETWORK_ADDRESS_OF_REVOKED_ENTITY: "A previous tenant's revocation does not attach to the current tenant; the link shows only that the address recurs.",
  NETWORK_OWNER_ON_LEIE: "An owner match to the LEIE or SAM is a name match at the stated confidence; confirm identity with date of birth or address before relying on it.",
  NETWORK_MEMBER_ON_LIST: "A list hit on one member does not extend to the other members without a records review.",
};
export function deterministicPacket(kind: "cluster" | "provider", id: string, lines: Line[], types: string[], name?: string) {
  const gs = groundsFor(types);
  return {
    title: kind === "cluster" ? `Referral candidate packet: provider community ${id}` : `Referral candidate packet: NPI ${id} ${name ?? ""}`.trim(),
    subject_type: kind, subject_id: id, generated_at: new Date().toISOString(), model: "deterministic", evidence_types: types,
    summary: lines[0]?.[1] ?? "", findings: lines.slice(1, 31).map((l, i) => ({ text: l[1], evidence_ids: [i + 1] })),
    grounds: gs,
    recommendation: "Route to the health plan special investigations unit, and to the state Medicaid program integrity unit where the payer is a Medicaid managed care plan, for a records request and a screening check under 42 CFR 455.436. Consider a pre-payment review pending that check; a payment suspension under 42 CFR 455.23 requires the state's own credible-allegation determination. Verify every fact against the cited rows before any action. This packet is a screening product, not a finding.",
    caveats: [...new Set(types.map(t => CAVEATS[t]).filter(Boolean))],
    evidence: lines.map((l, i) => ({ id: i, source: l[0], statement: l[1] })),
    plain_english: (kind === "cluster" ? "This provider community shows a structural pattern that program integrity reviewers look for: several organisations formed close together that share owners, suites or phone numbers, in a saturated market, with a link to a public exclusion or revocation record. " : "Public records show either an action that should have triggered a screening check, or billed hours that exceed what one clinician can deliver. ") + "Every numbered finding cites the public dataset and row it came from, and the caveats list the ordinary explanations a reviewer must rule out first.",
  };
}
