// Referral candidate packet: evidence lines from the serving tables, grounds from the evidence-type mapping (never keyword matching), deterministic draft when no model is configured.
import { SupabaseClient } from "@supabase/supabase-js";
import { CFR, evidenceTypes, groundsFor } from "./grounds";
import { sourceName as srcName, labelName } from "./labels";
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
    const [{ data: rev }, { data: leie }, { data: flags }, { data: factors }] = await Promise.all([sb.from("revoked").select("*").in("npi", npis), sb.from("leie").select("*").in("npi", npis), sb.from("flags").select("*").in("npi", npis).order("score", { ascending: false }).limit(20), sb.from("network_factors").select("*").eq("cluster_id", id)]);
    const kinds = [[c.n_hospice, "hospice", "hospices"], [c.n_hha, "home health agency", "home health agencies"], [c.n_snf, "nursing facility", "nursing facilities"]].filter(k => Number(k[0]) > 0).map(k => `${k[0]} ${Number(k[0]) === 1 ? k[1] : k[2]}`).join(", ");
    L.push(["clusters", `Provider network ${c.id}: ${c.n_providers} providers around ${c.city}, ${c.state} (${kinds}); network score ${Number(c.score).toFixed(0)} of 100, ranked ${c.rank} nationally.`]);
    for (const x of (f.facts ?? []) as string[]) L.push(["network facts", x]);
    const fx = (factors ?? []) as any[]; const mom = fx.find(r => r.factor === "momentum");
    for (const r of fx.filter(r => r.factor !== "momentum" && r.percentile != null && r.percentile >= 90).sort((a, b) => b.percentile - a.percentile).slice(0, 6)) L.push(["factor desk", `${r.label}: ${r.unit === "$" ? $(r.value) : r.unit === "share" ? `${Math.round(r.value * 100)}%` : r.unit === "years" ? `${Number(r.value).toFixed(1)} years` : Number.isInteger(r.value) ? r.value : Number(r.value).toFixed(1)}, in the top ${Math.max(1, Math.round(100 - r.percentile))}% of networks in the risky direction.`]);
    if (mom?.outlook) L.push(["factor desk", `Momentum across the rate-of-change factors is ${mom.outlook} (robust z ${Number(mom.value).toFixed(2)}); this is an indicative reading, not a validated forecast.`]);
    for (const [src, list] of Object.entries(f.prov_labels ?? {})) L.push([srcName(src), `Providers with NPI ${(list as string[]).join(", ")} appear on ${srcName(src)}.`]);
    for (const h of f.owner_hits ?? []) L.push([srcName(h[1]), `An owner named ${String(h[0]).replace(/\b\w/g, ch => ch.toUpperCase())} matches ${srcName(h[1])} at ${h[2]} confidence (action dated ${h[3]}).`]);
    if (f.sat_per_10k != null) L.push(["CMS market saturation", `The county has ${Number(f.sat_per_10k).toFixed(1)} providers of this kind per 10,000 Medicare fee-for-service beneficiaries, ${Number(f.sat_z ?? 0) > 0 ? "above" : "below"} the national norm.`]);
    L.push(["T-MSIS provider spending 2024", Number(c.dollars_at_risk) > 0 ? `The providers billed Medicaid ${$(c.dollars_at_risk)} in 2024${c.dollars_medicare ? ` and received ${$(c.dollars_medicare)} in Medicare hospice and home health payments in 2023` : ""}.` : c.dollars_medicare ? `The providers received ${$(c.dollars_medicare)} in Medicare hospice and home health payments in 2023 and billed no Medicaid in 2024.` : `The providers billed no Medicaid in 2024 and no Medicare hospice or home health payments are recorded for 2023.`]);
    for (const m of members ?? []) { const labs = (J(m.labels) as string[]) ?? []; const kind = m.ptype === "HHA" ? "Home health agency" : m.ptype === "SNF" ? "Nursing facility" : "Hospice"; L.push(["network members", `${kind} ${m.org_name} (NPI ${m.npi}, ${m.city}, ${m.state})${m.inc_date ? `, incorporated ${m.inc_date}` : ""}${Number(m.medicaid_2024) > 0 ? `, billed Medicaid ${$(m.medicaid_2024)} in 2024` : ", no Medicaid billing in 2024"}${labs.length ? `, on ${labs.map(srcName).join(" and ")}` : ""}.`]); }
    for (const r of rev ?? []) L.push(["Medicare revocation list", `NPI ${r.npi} was revoked on ${r.revoked_dt} under ${String(r.revocation_rsn ?? "").replace(/_/g, " ")}, barred from re-enrolling until ${r.reenroll_bar_dt}.`]);
    for (const r of leie ?? []) L.push(["OIG exclusion list", `NPI ${r.npi} was excluded on ${r.excl_dt} under section 1128 ${r.excltype}.`]);
    for (const fl of flags ?? []) { const e = J(fl.evidence); if (fl.detector === "D3") L.push(["paid after a list action", `NPI ${fl.npi}: after the ${srcName(e.source)} action of ${e.event_dt}, Medicaid paid ${$(e.paid_after)} across ${e.months_paid_after} later months.`]); else L.push(["hours per day", `NPI ${fl.npi}: ${labelName(e.label)} in ${String(fl.month).slice(0, 7)}, ${Number(fl.value).toFixed(1)} hours per day, ${$(fl.dollars)} paid.`]); }
    return { lines: L, types: evidenceTypes("cluster", f, flags ?? [], rev ?? [], leie ?? []) };
  }
  const [{ data: p }, { data: flags }, { data: rev }, { data: leie }, { data: enr }, { data: cm }, { data: risk }] = await Promise.all([sb.from("providers").select("*").eq("npi", id).maybeSingle(), sb.from("flags").select("*").eq("npi", id).order("score", { ascending: false }), sb.from("revoked").select("*").eq("npi", id), sb.from("leie").select("*").eq("npi", id), sb.from("enrollments").select("*").eq("npi", id), sb.from("cluster_members").select("cluster_id, clusters(id,rank,score,summary,features)").eq("npi", id), sb.from("provider_risk").select("*").eq("npi", id).maybeSingle()]);
  if (!p && !(flags ?? []).length && !risk) return { lines: L, types: [] };
  const who = p?.name ?? risk?.name ?? `NPI ${id}`; const entityKind = (p?.entity_type ?? risk?.entity_type) === "2" ? "an organization" : "an individual";
  L.push(["national provider registry", `${who} (NPI ${id}) is ${entityKind} in ${p?.city ?? risk?.city ?? "an unstated city"}, ${p?.state ?? risk?.state ?? ""}${(p?.taxonomy ?? risk?.taxonomy) ? `, taxonomy ${p?.taxonomy ?? risk?.taxonomy}` : ""}${(p?.medicaid_state ?? risk?.medicaid_state) ? `, enrolled in Medicaid in ${p?.medicaid_state ?? risk?.medicaid_state}` : ""}.`]);
  if (risk) L.push(["Verity risk tier", `Evidence tier ${risk.tier}, ${risk.tier_label}. ${risk.reasons}. Dollars at stake ${$(risk.dollars_at_risk)}, taken from the detector that set the tier.`]);
  for (const r of rev ?? []) L.push(["Medicare revocation list", `Medicare revoked billing privileges effective ${r.revoked_dt} under ${String(r.revocation_rsn ?? "").replace(/_/g, " ")}, with a re-enrollment bar until ${r.reenroll_bar_dt}.`]);
  for (const r of leie ?? []) L.push(["OIG exclusion list", `The OIG excluded this provider on ${r.excl_dt} under section 1128 ${r.excltype}${r.general ? ` (${r.general})` : ""}${r.rein_dt ? `, reinstated ${r.rein_dt}` : ""}.`]);
  for (const fl of flags ?? []) { const e = J(fl.evidence);
    if (fl.detector === "D3") L.push(["paid after a list action", `After the ${srcName(e.source)} action of ${e.event_dt}, Medicaid paid ${$(e.paid_after)} across ${e.months_paid_after} later months (${e.first_month_after} to ${e.last_month_after})${e.window_end ? `, until the window closed on ${e.window_end}` : ""}. In the 12 months before the action Medicaid paid ${$(e.paid_before_12m)}.`]);
    else if (fl.metric === "growth_and_concentration") L.push(["growth and concentration", `In ${String(fl.month).slice(0, 4)} this new billing organization was paid ${$(fl.dollars)}, ${Math.round(Number(e.concentration ?? 0) * 100)}% of it on code ${e.dominant_code}, with dollars per patient in the top ${Math.round((1 - Number(e.intensity_pct ?? 0)) * 100)}% nationally.`]);
    else L.push(["hours per day", `In ${String(fl.month).slice(0, 7)}: ${labelName(e.label)}. Conservative estimate ${Number(fl.value).toFixed(1)} hours per ${e.test_basis ?? "day"} (rate-free lower bound ${Number(e.hours_lb_per_day ?? 0).toFixed(1)}), ${$(e.paid)} paid on codes ${(e.codes ?? []).join(" ")}, billed through ${e.n_billing_orgs} organization${Number(e.n_billing_orgs) === 1 ? "" : "s"}.`]); }
  for (const en of enr ?? []) L.push(["Medicare enrollment", `Enrolled in Medicare as ${en.ptype === "HHA" ? "a home health agency" : en.ptype === "SNF" ? "a nursing facility" : "a hospice"}, ${en.org_name}${en.inc_date ? `, incorporated ${en.inc_date}` : ""}, ${en.city}, ${en.state}.`]);
  const feats = (cm ?? []).map((c: any) => J(c.clusters?.features));
  for (const c of cm ?? []) L.push(["provider network", `Part of provider network ${(c as any).clusters?.id}, ranked ${(c as any).clusters?.rank}: ${(c as any).clusters?.summary}`]);
  const types = new Set(evidenceTypes("provider", {}, flags ?? [], rev ?? [], leie ?? [])); for (const f of feats) for (const t of evidenceTypes("cluster", f, [], [], [])) types.add(t);
  return { lines: L, types: [...types] };
}
const CAVEATS: Record<string, string> = {
  MEDICARE_REVOKED_PAID_AFTER: "A revocation can be reversed on appeal or through a corrective action plan; confirm the current enrollment status with the state and in PECOS before acting.",
  OIG_LEIE_PAID_AFTER: "Check the LEIE for a reinstatement date; services dated before the exclusion but billed after it are lawful.",
  SAM_PAID_AFTER: "SAM debarments from agencies other than HHS restrict federal contracting; confirm that the state's own screening policy applies to them.",
  STATE_EXCL_PAID_AFTER: "State lists carry reinstatements and administrative terminations; confirm the action type with the listing agency.",
  NPPES_DEACTIVATED_PAID_AFTER: "An NPI deactivated after a death or retirement can still receive lawful late claims for services rendered before the deactivation date.",
  IMPOSSIBLE_HOURS: "The rendering NPI on Medicaid claims is often the supervising clinician under state convention; confirm which organizations employ or contract with this clinician before treating the hours as one person's work.",
  PER_PATIENT_IMPOSSIBLE: "Per-patient hours can exceed the calendar under legitimate group or crisis services when the code is billed per staff member; confirm the code's billing unit with the state.",
  MN_DAILY_CAP: "State caps carry prior-authorization exceptions; confirm whether an exception was on file.",
  UMBRELLA_VOLUME: "One organization billing under a supervising NPI is common and lawful in several states; this is a records request, not a finding.",
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
    title: kind === "cluster" ? `Referral packet: provider network ${id}` : `Referral packet: ${name ?? `NPI ${id}`}`,
    subject_type: kind, subject_id: id, generated_at: new Date().toISOString(), model: "deterministic", evidence_types: types,
    summary: lines[0]?.[1] ?? "", findings: lines.slice(1, 31).map((l, i) => ({ text: l[1], evidence_ids: [i + 1] })),
    grounds: gs,
    recommendation: "Route to the health plan special investigations unit, and to the state Medicaid program integrity unit where the payer is a Medicaid managed care plan, for a records request and a screening check under 42 CFR 455.436. Consider a pre-payment review pending that check; a payment suspension under 42 CFR 455.23 requires the state's own credible-allegation determination. Verify every fact against the cited rows before any action. This packet is a screening product, not a finding.",
    caveats: [...new Set(types.map(t => CAVEATS[t]).filter(Boolean))],
    evidence: lines.map((l, i) => ({ id: i, source: l[0], statement: l[1] })),
    plain_english: lines.filter(l => l[0] === "network facts" || l[0] === "Verity risk tier" || l[0] === "paid after a list action" || l[0] === "hours per day").slice(0, 4).map(l => l[1]).join(" ") || lines[0]?.[1] || "",
  };
}
