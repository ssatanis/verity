import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
import { PacketPanel } from "@/components/app/PacketPanel";
import { AskCase } from "@/components/app/AskCase";
import { Tier } from "@/components/app/Tier";
export const revalidate = 60;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
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
  const d2 = (flags ?? []).filter(f => f.detector === "D2" && f.metric !== "growth_and_concentration"); const d3 = (flags ?? []).filter(f => f.detector === "D3"); const growth = (flags ?? []).filter(f => f.metric === "growth_and_concentration");
  const name = p?.name || risk?.name || flags?.[0]?.name || npi;
  return (
    <div>
      <Link href="/app/candidates" className="eyebrow">Referral candidates</Link>
      <div className="flex items-start justify-between gap-6 mt-2">
        <div>
          <h1 className="display serif text-[48px]">{name}</h1>
          <p className="text-[13px] text-[var(--ink-3)] mt-3">NPI {npi} · {(p?.entity_type ?? risk?.entity_type) === "2" ? "organisation" : "individual"} · {p?.city ?? risk?.city}, {p?.state ?? risk?.state} · taxonomy {p?.taxonomy ?? risk?.taxonomy} · Medicaid home state {p?.medicaid_state ?? risk?.medicaid_state ?? "not stated"}{p?.deact_date ? ` · NPI deactivated ${p.deact_date}` : ""}</p>
        </div>
        {risk && <div className="kpi min-w-[260px]"><div className="flex items-center gap-3"><Tier n={risk.tier} /><div><div className="eyebrow">Evidence tier</div><div className="serif text-[20px]">{risk.tier_label}</div></div></div><div className="text-[12px] text-[var(--ink-2)] mt-3">{risk.reasons}</div><div className="text-[11px] text-[var(--ink-3)] mt-2">score {Number(risk.score).toFixed(0)} · rank {risk.rank} · {money(risk.dollars_at_risk)} at risk (highest single detector) · {(risk.detectors as string[])?.join(" ")}</div></div>}
      </div>
      <div className="grid md:grid-cols-[1.4fr_1fr] gap-6 mt-8">
        <div className="space-y-6">
          {(rev?.length || leie?.length) ? <div className="card p-5"><h2 className="serif text-[24px] mb-2">Public list actions</h2>
            {rev?.map((r, i) => <div key={i} className="text-[13px] py-2 rule"><span className="font-medium">Medicare revocation</span> effective {r.revoked_dt}, re-enrollment bar to {r.reenroll_bar_dt}<div className="text-[12px] text-[var(--ink-2)]">{r.revocation_rsn} · {r.provider_type_desc} · {r.state}</div></div>)}
            {leie?.map((r, i) => <div key={i} className="text-[13px] py-2 rule"><span className="font-medium">OIG exclusion</span> {r.excl_dt} under section {r.excltype}{r.rein_dt ? `, reinstated ${r.rein_dt}` : ""}<div className="text-[12px] text-[var(--ink-2)]">{r.general} · {r.specialty} · {r.city}, {r.state}</div></div>)}
          </div> : null}
          {d3.length ? <div className="card p-5 overflow-x-auto"><h2 className="serif text-[24px] mb-1">Service months after the action</h2><p className="text-[12px] text-[var(--ink-3)] mb-2">Medicaid service months dated after a public action that should have triggered a state screening check under 42 CFR 455.436. Not a determination that the payments were improper.</p>
            <table className="table"><thead><tr><th>source</th><th>identity</th><th>action date</th><th>window end</th><th>months after</th><th>first</th><th>last</th><th>paid after</th><th>12 months before</th><th>tier</th></tr></thead>
              <tbody>{d3.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td>{e.source}<div className="text-[11px] text-[var(--ink-3)] max-w-[260px]">{e.reason}</div></td><td className="text-[11px]">{String(e.id_match ?? "").replace(/_/g, " ")}</td><td>{e.event_dt}</td><td>{e.window_end ?? "open"}</td><td>{e.months_paid_after}</td><td>{e.first_month_after}</td><td>{e.last_month_after}</td><td>{money(e.paid_after)}</td><td>{money(e.paid_before_12m)}</td><td>{f.tier}</td></tr>; })}</tbody></table>
          </div> : null}
          {d2.length ? <div className="card p-5 overflow-x-auto"><h2 className="serif text-[24px] mb-1">Implied personal-service hours by month</h2>
            <p className="text-[12px] text-[var(--ink-3)] mb-2">Lower bound counts one unit per claim line and needs no price. Point and conservative divide paid dollars by the unit price (published for Minnesota, estimated elsewhere; conservative is 1.5 times the price). Labels use the conservative figure. The rendering NPI may be a supervising clinician under state convention.</p>
            <table className="table"><thead><tr><th>month</th><th>label</th><th>h/day lower bound</th><th>h/day point</th><th>h/day conservative</th><th>h/workday</th><th>patients</th><th>billing orgs</th><th>codes</th><th>paid</th></tr></thead>
              <tbody>{d2.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px]">{e.label}</td><td>{Number(e.hours_lb_per_day).toFixed(1)}</td><td>{Number(e.hours_pt_per_day).toFixed(1)}</td><td>{Number(e.hours_cons_per_day).toFixed(1)}</td><td>{e.hours_cons_personal_per_workday != null ? Number(e.hours_cons_personal_per_workday).toFixed(1) : ""}</td><td>{e.patients}</td><td>{e.n_billing_orgs}</td><td className="text-[11px]">{(e.codes || []).join(" ")}</td><td>{money(e.paid)}</td></tr>; })}</tbody></table>
          </div> : null}
          {growth.length ? <div className="card p-5"><h2 className="serif text-[24px] mb-1">Growth and concentration</h2><p className="text-[12px] text-[var(--ink-3)] mb-2">Informational. New billing NPIs with most dollars on one high-vector code and top-decile dollars per patient-month.</p>{growth.map(f => { const e = ev(f.evidence); return <div key={String(f.id)} className="text-[13px] py-2 rule">{String(f.month).slice(0, 4)}: {money(f.dollars)} paid, {Math.round(Number(e.concentration ?? 0) * 100)}% on {e.dominant_code}; {money(e.dollars_per_patient_month)} per patient-month (percentile {Number(e.intensity_pct ?? 0).toFixed(2)}){e.growth_yoy != null ? `; growth ${Number(e.growth_yoy).toFixed(1)}x` : ""}</div>; })}</div> : null}
          {members?.length ? <div className="card p-5"><h2 className="serif text-[24px] mb-2">Provider communities</h2>{members.map((m: any) => <Link key={m.cluster_id} href={`/app/clusters/${m.cluster_id}`} className="block py-2 rule text-[13px]"><span className="serif text-[17px]">{m.cluster_id}</span> <span className="text-[var(--ink-3)]">rank {m.clusters?.rank}</span><div className="text-[12px] text-[var(--ink-2)]">{m.clusters?.summary}</div></Link>)}</div> : null}
          {!d3.length && !d2.length && !growth.length && !members?.length && !rev?.length && !leie?.length && <div className="card-2 p-6 text-[13px]">No detector reached this NPI and it appears on none of the loaded lists.</div>}
        </div>
        <div className="space-y-6"><PacketPanel subjectType="provider" subjectId={npi} existing={packets ?? []} /><AskCase subjectType="provider" subjectId={npi} /></div>
      </div>
    </div>
  );
}
