import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { PacketPanel } from "@/components/app/PacketPanel";
import { AskCase } from "@/components/app/AskCase";
import { Tier } from "@/components/app/Tier";
import { sourceName, labelName, idMatchName, money } from "@/lib/labels";
export const revalidate = 60;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
const API = process.env.VERITY_API_URL ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
export default async function Provider({ params }: { params: Promise<{ npi: string }> }) {
  const { npi } = await params; const sb = publicClient();
  const [{ data: p }, { data: risk }, { data: flags }, { data: rev }, { data: leie }, { data: members }, { data: packets }] = await Promise.all([
    sb.from("providers").select("*").eq("npi", npi).maybeSingle(),
    sb.from("provider_risk").select("*").eq("npi", npi).maybeSingle(),
    sb.from("flags").select("*").eq("npi", npi).order("month"),
    sb.from("revoked").select("*").eq("npi", npi), sb.from("leie").select("*").eq("npi", npi),
    sb.from("cluster_members").select("cluster_id, clusters(id,rank,score,summary)").eq("npi", npi),
    sb.from("packets").select("id,status,packet,created_at,model").eq("subject_id", npi).order("created_at", { ascending: false }).limit(1),
  ]);
  // any NPI in the country: when the serving tables have nothing, read the registry record through the local API
  let reg: any = null;
  if (API && (!p || !risk)) { try { const r = await fetch(`${API}/provider/${npi}`, { next: { revalidate: 300 }, signal: AbortSignal.timeout(5000) }); if (r.ok) reg = await r.json(); } catch {} }
  const d2 = (flags ?? []).filter(f => f.detector === "D2" && f.metric !== "growth_and_concentration"); const d3 = (flags ?? []).filter(f => f.detector === "D3"); const growth = (flags ?? []).filter(f => f.metric === "growth_and_concentration");
  const name = p?.name || risk?.name || reg?.name || flags?.[0]?.name || npi;
  const entity = p?.entity_type ?? risk?.entity_type ?? reg?.entity_type; const city = p?.city ?? risk?.city ?? reg?.city; const state = p?.state ?? risk?.state ?? reg?.state; const tax = p?.taxonomy ?? risk?.taxonomy ?? reg?.taxonomy;
  const nothing = !d3.length && !d2.length && !growth.length && !members?.length && !rev?.length && !leie?.length;
  return (
    <div>
      <Link href="/app/candidates" className="eyebrow">Providers</Link>
      <div className="flex flex-col md:flex-row items-start justify-between gap-6 mt-2">
        <div>
          <h1 className="display serif text-[40px] md:text-[48px]">{name}</h1>
          <p className="text-[13px] text-[var(--ink-3)] mt-3">NPI {npi} · {entity === "2" ? "organisation" : "individual"}{city ? ` · ${city}, ${state}` : state ? ` · ${state}` : ""}{tax ? ` · taxonomy ${tax}` : ""}{reg?.deact_date ? ` · NPI deactivated ${reg.deact_date}` : p?.deact_date ? ` · NPI deactivated ${p.deact_date}` : ""}</p>
        </div>
        {risk ? <div className="kpi min-w-[260px]"><div className="flex items-center gap-3"><Tier n={risk.tier} /><div><div className="eyebrow">Evidence tier</div><div className="serif text-[20px]">{risk.tier_label}</div></div></div><div className="text-[12.5px] text-[var(--ink-2)] mt-3 leading-5">{risk.reasons}</div><div className="text-[11px] text-[var(--ink-3)] mt-2">score {Number(risk.score).toFixed(0)} of 100 · rank {risk.rank} · {money(risk.dollars_at_risk)} at stake</div></div>
          : <div className="kpi min-w-[260px]"><div className="eyebrow">Evidence tier</div><div className="serif text-[20px]">No indicators</div><div className="text-[12.5px] text-[var(--ink-2)] mt-2 leading-5">No detector reached this NPI and it appears on none of the loaded lists.</div></div>}
      </div>
      <div className="grid md:grid-cols-[1.4fr_1fr] gap-6 mt-8">
        <div className="space-y-6">
          {(rev?.length || leie?.length) ? <div className="card p-5"><h2 className="serif text-[24px] mb-2">Public list actions</h2>
            {rev?.map((r, i) => <div key={i} className="text-[13px] py-2 rule"><span className="font-semibold">Medicare revocation</span> effective {r.revoked_dt}, barred from re-enrolling until {r.reenroll_bar_dt}<div className="text-[12px] text-[var(--ink-2)]">{String(r.revocation_rsn ?? "").replace(/_/g, " ")} · {r.provider_type_desc} · {r.state}</div></div>)}
            {leie?.map((r, i) => <div key={i} className="text-[13px] py-2 rule"><span className="font-semibold">OIG exclusion</span> {r.excl_dt} under section {r.excltype}{r.rein_dt ? `, reinstated ${r.rein_dt}` : ""}<div className="text-[12px] text-[var(--ink-2)]">{r.general} · {r.specialty} · {r.city}, {r.state}</div></div>)}
          </div> : null}
          {d3.length ? <div className="card p-5 overflow-x-auto"><h2 className="serif text-[24px] mb-1">Paid after the action</h2><p className="text-[12.5px] text-[var(--ink-3)] mb-2">Months in which Medicaid paid claims for this provider after a public action that should have triggered a screening check. This is a record of payments, not a determination that they were improper.</p>
            <table className="table"><thead><tr><th>list</th><th>identity check</th><th>action date</th><th>window closed</th><th>months paid after</th><th>first</th><th>last</th><th>paid after</th><th>12 months before</th></tr></thead>
              <tbody>{d3.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td>{sourceName(e.source)}<div className="text-[11px] text-[var(--ink-3)] max-w-[260px]">{String(e.reason ?? "").replace(/_/g, " ")}</div></td><td className="text-[11px]">{idMatchName(e.id_match)}</td><td>{e.event_dt}</td><td>{e.window_end ?? "still open"}</td><td>{e.months_paid_after}</td><td>{e.first_month_after}</td><td>{e.last_month_after}</td><td>{money(e.paid_after)}</td><td>{money(e.paid_before_12m)}</td></tr>; })}</tbody></table>
          </div> : null}
          {d2.length ? <div className="card p-5 overflow-x-auto"><h2 className="serif text-[24px] mb-1">Hours billed per day</h2>
            <p className="text-[12.5px] text-[var(--ink-3)] mb-2">Medicaid billing converted into hours of hands-on care per day. The lower bound counts one unit per claim line and needs no price; the other two divide dollars by a unit price, the conservative one at 1.5 times the price. The clinician on the claim may be a supervisor under state rules, so billing organisations are counted too.</p>
            <table className="table"><thead><tr><th>month</th><th>what was found</th><th>hours per day, lower bound</th><th>hours per day, at price</th><th>hours per day, conservative</th><th>per working day</th><th>patients</th><th>billing organisations</th><th>codes</th><th>paid</th></tr></thead>
              <tbody>{d2.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px] max-w-[200px]">{labelName(e.label)}</td><td>{Number(e.hours_lb_per_day).toFixed(1)}</td><td>{Number(e.hours_pt_per_day).toFixed(1)}</td><td>{Number(e.hours_cons_per_day).toFixed(1)}</td><td>{e.hours_cons_personal_per_workday != null ? Number(e.hours_cons_personal_per_workday).toFixed(1) : ""}</td><td>{e.patients}</td><td>{e.n_billing_orgs}</td><td className="text-[11px]">{(e.codes || []).join(" ")}</td><td>{money(e.paid)}</td></tr>; })}</tbody></table>
          </div> : null}
          {growth.length ? <div className="card p-5"><h2 className="serif text-[24px] mb-1">Growth and concentration</h2><p className="text-[12.5px] text-[var(--ink-3)] mb-2">Informational: a new billing organisation with most of its dollars on one high-risk code and unusually high dollars per patient.</p>{growth.map(f => { const e = ev(f.evidence); return <div key={String(f.id)} className="text-[13px] py-2 rule">{String(f.month).slice(0, 4)}: {money(f.dollars)} paid, {Math.round(Number(e.concentration ?? 0) * 100)}% on code {e.dominant_code}; {money(e.dollars_per_patient_month)} per patient per month{e.growth_yoy != null ? `; ${Number(e.growth_yoy).toFixed(1)} times the year before` : ""}</div>; })}</div> : null}
          {members?.length ? <div className="card p-5"><h2 className="serif text-[24px] mb-2">Provider networks</h2>{members.map((m: any) => <Link key={m.cluster_id} href={`/app/clusters/${m.cluster_id}`} className="block py-2 rule text-[13px]"><span className="serif text-[17px]">{m.cluster_id}</span> <span className="text-[var(--ink-3)]">ranked {m.clusters?.rank}</span><div className="text-[12px] text-[var(--ink-2)]">{m.clusters?.summary}</div></Link>)}</div> : null}
          {reg && (reg.spend_by_year?.length || reg.medicaid_states?.length) ? <div className="card p-5"><h2 className="serif text-[24px] mb-2">Registry and Medicaid record</h2>
            <div className="text-[13px] text-[var(--ink-2)]">{reg.enum_date ? `NPI issued ${reg.enum_date}. ` : ""}{reg.medicaid_states?.length ? `Enrolled in Medicaid in ${reg.medicaid_states.join(", ")}. ` : ""}{reg.lists && Object.values(reg.lists).some((v: any) => v > 0) ? "Appears on at least one public list (see above)." : "Not on any loaded exclusion or revocation list."}</div>
            {reg.spend_by_year?.length ? <table className="table mt-3"><thead><tr><th>year</th><th>Medicaid paid</th><th>months with claims</th></tr></thead><tbody>{reg.spend_by_year.map((r: any) => <tr key={r.year}><td>{r.year}</td><td>{money(r.paid)}</td><td>{r.months}</td></tr>)}</tbody></table> : null}
          </div> : null}
          {nothing && !reg && <div className="card-2 p-6 text-[13px]">No detector reached this NPI and it appears on none of the loaded lists.{!p && " The provider is not in the serving tables; the full registry lookup needs the local API."}</div>}
        </div>
        <div className="space-y-6"><PacketPanel subjectType="provider" subjectId={npi} existing={packets ?? []} /><AskCase subjectType="provider" subjectId={npi} /></div>
      </div>
    </div>
  );
}
