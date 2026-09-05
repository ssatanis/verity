// Deterministic referral-packet builder (TypeScript port of api/packet.py) so the deployed app works without a model key.
import { SupabaseClient } from "@supabase/supabase-js";
export const CFR: Record<string, string> = {
  "424.535(a)(2)": "Provider or supplier conduct: exclusion, debarment or suspension by a federal program",
  "424.535(a)(3)": "Felony conviction within the preceding 10 years detrimental to the best interests of the program",
  "424.535(a)(4)": "False or misleading information on the enrollment application",
  "424.535(a)(5)": "On-site review: the provider is no longer operational at the practice location",
  "424.535(a)(8)": "Abuse of billing privileges (claims that could not have been furnished, or a pattern of non-compliant claims)",
  "424.535(a)(12)": "Termination, revocation or suspension by another federal program or a state Medicaid agency",
  "424.535(a)(19)": "Affiliation with a previously sanctioned entity that poses an undue risk of fraud, waste or abuse",
  "455.416(c)": "State Medicaid agencies must terminate providers terminated by Medicare or another state's Medicaid program for cause",
  "455.23": "Suspension of Medicaid payments upon a credible allegation of fraud",
  "1001.1901": "No federal health care program payment for items or services furnished by an excluded person",
  "455.410": "Enrollment and screening of all Medicaid providers",
};
const J = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
const $ = (v: any) => `$${Number(v ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
export async function evidenceLines(sb: SupabaseClient, kind: "cluster" | "provider", id: string): Promise<[string, string][]> {
  const L: [string, string][] = [];
  if (kind === "cluster") {
    const { data: c } = await sb.from("clusters").select("*").eq("id", id).maybeSingle(); if (!c) return L;
    const f = J(c.features); const { data: members } = await sb.from("cluster_members").select("*").eq("cluster_id", id).order("medicaid_2024", { ascending: false }).limit(40);
    const npis = (members ?? []).map(m => m.npi).filter(Boolean);
    const [{ data: rev }, { data: leie }, { data: flags }] = await Promise.all([sb.from("revoked").select("*").in("npi", npis), sb.from("leie").select("*").in("npi", npis), sb.from("flags").select("*").in("npi", npis).order("score", { ascending: false }).limit(20)]);
    L.push(["clusters", `Community ${c.id} (${c.n_providers} providers: ${c.n_hospice} hospice, ${c.n_hha} home health, ${c.n_snf} SNF) centred on ${c.city}; risk score ${Number(c.score).toFixed(2)}, rank ${c.rank}.`]);
    if ((f.burst_90 ?? 0) >= 2) L.push(["enrollment files, INCORPORATION DATE", `${f.burst_90} members were incorporated within a 90-day window ${JSON.stringify(f.burst_90_span)}.`]);
    if (Math.max(f.addr_share ?? 0, f.unit_share ?? 0) >= 2) L.push(["enrollment ADDRESS LINE 1 / NPPES practice location", `Up to ${Math.max(f.addr_share, f.unit_share)} members share one practice address${(f.unit_share ?? 0) >= 2 ? " (same suite)" : ""}.`]);
    if (f.owner_multi) L.push(["All-Owners files, resolved persons and organisations", `${f.owner_multi} owner(s) are tied to three or more members (largest: ${f.max_owner_degree}).`]);
    if ((f.phone_share ?? 0) >= 2) L.push(["NPPES practice telephone", `${f.phone_share} members list the same telephone number.`]);
    for (const [src, list] of Object.entries(f.prov_labels ?? {})) L.push([src, `Member NPI(s) ${(list as string[]).join(", ")} appear on ${src}.`]);
    for (const h of f.owner_hits ?? []) L.push([h[1], `Owner '${h[0]}' matches ${h[1]} at ${h[2]} confidence (effective ${h[3]}).`]);
    if (f.sat_per_10k != null) L.push(["CMS Market Saturation and Utilization", `The county has ${Number(f.sat_per_10k).toFixed(1)} providers per 10,000 FFS beneficiaries (robust z ${Number(f.sat_z ?? 0).toFixed(1)}).`]);
    L.push(["T-MSIS provider spending 2024", `Members billed Medicaid ${$(c.dollars_at_risk)} in 2024${c.dollars_medicare ? `; Medicare 2023 hospice/HHA payments ${$(c.dollars_medicare)}.` : "."}`]);
    for (const m of members ?? []) L.push(["cluster_members", `${m.ptype} ${m.org_name} (NPI ${m.npi}, ${m.city}, ${m.state}; incorporated ${m.inc_date}; Medicaid 2024 ${$(m.medicaid_2024)}; labels ${JSON.stringify(J(m.labels))}).`]);
    for (const r of rev ?? []) L.push(["Revocation_Extract", `NPI ${r.npi} revoked ${r.revoked_dt} under ${r.revocation_rsn} (bar to ${r.reenroll_bar_dt}).`]);
    for (const r of leie ?? []) L.push(["OIG LEIE", `NPI ${r.npi} excluded ${r.excl_dt} under section 1128 ${r.excltype}.`]);
    for (const fl of flags ?? []) { const e = J(fl.evidence); L.push([`flags/${fl.detector}`, `NPI ${fl.npi} ${fl.metric} = ${Number(fl.value).toFixed(2)} (threshold ${fl.threshold}) in ${fl.month}; ${$(fl.dollars)}; ${e.label ?? e.source ?? ""}.`]); }
  } else {
    const [{ data: p }, { data: flags }, { data: rev }, { data: leie }, { data: enr }, { data: cm }] = await Promise.all([sb.from("providers").select("*").eq("npi", id).maybeSingle(), sb.from("flags").select("*").eq("npi", id).order("score", { ascending: false }), sb.from("revoked").select("*").eq("npi", id), sb.from("leie").select("*").eq("npi", id), sb.from("enrollments").select("*").eq("npi", id), sb.from("cluster_members").select("cluster_id, clusters(id,rank,score,summary)").eq("npi", id)]);
    L.push(["providers/NPPES", `NPI ${id} ${p?.name ?? ""} (${p?.entity_type === "2" ? "organisation" : "individual"}), ${p?.city}, ${p?.state}; taxonomy ${p?.taxonomy}; Medicaid home state ${p?.medicaid_state}.`]);
    for (const r of rev ?? []) L.push(["Revocation_Extract", `Revoked ${r.revoked_dt} under ${r.revocation_rsn}; re-enrollment bar to ${r.reenroll_bar_dt}.`]);
    for (const r of leie ?? []) L.push(["OIG LEIE", `Excluded ${r.excl_dt} under section 1128 ${r.excltype} (${r.general}).`]);
    for (const fl of flags ?? []) { const e = J(fl.evidence);
      if (fl.detector === "D3") L.push(["flags/D3 + T-MSIS spending", `After the ${e.source} action of ${e.event_dt} (${e.reason}), Medicaid paid ${$(e.paid_after)} across ${e.months_paid_after} service months (${e.first_month_after} to ${e.last_month_after}); ${$(e.paid_before_12m)} in the 12 months before.`]);
      else L.push(["flags/D2 + T-MSIS spending", `${String(fl.month).slice(0, 7)}: ${e.label}; implied hours per ${e.test_basis ?? "day"} ${Number(fl.value).toFixed(1)} (lower bound ${Number(e.hours_lb_per_day ?? 0).toFixed(1)}, point ${Number(e.hours_pt_per_day ?? 0).toFixed(1)}); ${$(e.paid)}; codes ${(e.codes ?? []).join(" ")}; ${e.n_billing_orgs} billing organisations; rate source ${e.rate_sources}.`]); }
    for (const en of enr ?? []) L.push(["enrollments", `Enrolled as ${en.ptype} ${en.org_name} (${en.enrollment_id}), incorporated ${en.inc_date}, ${en.city}, ${en.state}.`]);
    for (const c of cm ?? []) L.push(["clusters", `Member of community ${(c as any).clusters?.id} (rank ${(c as any).clusters?.rank}): ${(c as any).clusters?.summary}`]);
  }
  return L;
}
export function grounds(lines: [string, string][]) {
  const t = lines.map(l => l[1]).join(" "); const g: string[] = [];
  if (/OIG LEIE|OIG_LEIE/.test(t)) g.push("1001.1901", "424.535(a)(2)");
  if (/revoked/i.test(t)) g.push("424.535(a)(12)", "455.416(c)");
  if (/90-day window|share one practice address|three or more members/.test(t)) g.push("424.535(a)(19)", "424.535(a)(5)");
  if (/implied hours|IMPOSSIBLE/.test(t)) g.push("424.535(a)(8)", "455.23");
  if (/medicaid paid \$/i.test(t) && /after the/i.test(t)) g.push("455.416(c)", "455.23");
  if (/STATE_EXCL/.test(t)) g.push("455.416(c)");
  return [...new Set(g.length ? g : ["455.410"])];
}
export function deterministicPacket(kind: "cluster" | "provider", id: string, lines: [string, string][], name?: string) {
  const gs = grounds(lines);
  return {
    title: kind === "cluster" ? `Referral packet: provider community ${id}` : `Referral packet: NPI ${id} ${name ?? ""}`.trim(),
    subject_type: kind, subject_id: id, generated_at: new Date().toISOString(), model: "deterministic",
    summary: lines[0]?.[1] ?? "", findings: lines.slice(1, 31).map((l, i) => ({ text: l[1], evidence_ids: [i + 1] })),
    grounds: gs.map(c => ({ cfr: c, text: CFR[c] })),
    recommendation: "Refer to the state Medicaid program integrity unit and the CMS Center for Program Integrity for payment suspension review under 42 CFR 455.23 and enrollment action under the grounds listed. Verify every fact against the source rows cited before any action; this packet is a screening product, not a finding.",
    evidence: lines.map((l, i) => ({ id: i, source: l[0], statement: l[1] })),
    plain_english: (kind === "cluster" ? "This provider community shows the structural fingerprint of a ghost network: several newly formed entities sharing owners and addresses in a saturated market, with at least one link to a federal exclusion or revocation. " : "Public federal records show an action that should have stopped Medicaid payment, and the state spending data shows payments continuing afterwards. ") + "Each numbered finding cites the exact public dataset and row it came from.",
  };
}
export async function polishWithOpenAI(packet: any) {
  const key = process.env.OPENAI_API_KEY; if (!key || !key.startsWith("sk-") || key === "sk-...") return packet;
  try {
    const r = await fetch("https://api.openai.com/v1/chat/completions", { method: "POST", headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: process.env.OPENAI_MODEL ?? "gpt-5", response_format: { type: "json_object" }, messages: [
        { role: "system", content: "You draft CMS-style referral packets for a human reviewer. Return JSON {summary, plain_english, findings:[{text, evidence_ids}], recommendation}. Every finding must cite evidence ids that support it verbatim; never add facts; never assert guilt, describe records and dates." },
        { role: "user", content: JSON.stringify({ evidence: packet.evidence, grounds: packet.grounds }) }] }) });
    const j = await r.json(); const out = JSON.parse(j.choices?.[0]?.message?.content ?? "{}");
    const ok = (out.findings ?? []).filter((f: any) => Array.isArray(f.evidence_ids) && f.evidence_ids.every((i: any) => Number.isInteger(i) && i >= 0 && i < packet.evidence.length));
    return { ...packet, model: process.env.OPENAI_MODEL ?? "gpt-5", summary: out.summary ?? packet.summary, plain_english: out.plain_english ?? packet.plain_english, findings: ok.length ? ok : packet.findings, recommendation: out.recommendation ?? packet.recommendation };
  } catch { return packet; }
}
