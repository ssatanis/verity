import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
import { PacketPanel } from "@/components/app/PacketPanel";
export const revalidate = 60;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
export default async function Provider({ params }: { params: Promise<{ npi: string }> }) {
  const { npi } = await params; const sb = publicClient();
  const [{ data: p }, { data: flags }, { data: rev }, { data: leie }, { data: members }, { data: packets }] = await Promise.all([
    sb.from("providers").select("*").eq("npi", npi).maybeSingle(),
    sb.from("flags").select("*").eq("npi", npi).order("month"),
    sb.from("revoked").select("*").eq("npi", npi), sb.from("leie").select("*").eq("npi", npi),
    sb.from("cluster_members").select("cluster_id, clusters(id,rank,score,summary)").eq("npi", npi),
    sb.from("packets").select("id,status,packet,created_at,model").eq("subject_id", npi).order("created_at", { ascending: false }).limit(1),
  ]);
  const d2 = (flags ?? []).filter(f => f.detector === "D2"); const d3 = (flags ?? []).filter(f => f.detector === "D3");
  return (
    <div>
      <Link href="/app/flags" className="text-[12px] text-[var(--ink-3)]">Flags</Link>
      <h1 className="serif text-[36px] leading-none mt-1">{p?.name || flags?.[0]?.name || npi}</h1>
      <p className="text-[13px] text-[var(--ink-3)] mt-2">NPI {npi} · {p?.entity_type === "2" ? "organisation" : "individual"} · {p?.city}, {p?.state} · taxonomy {p?.taxonomy} · Medicaid home state {p?.medicaid_state ?? "n/a"}{p?.deact_date ? ` · NPI deactivated ${p.deact_date}` : ""}</p>
      <div className="grid md:grid-cols-[1.4fr_1fr] gap-6 mt-6">
        <div className="space-y-6">
          {(rev?.length || leie?.length) ? <div className="card bg-white p-5"><h2 className="serif text-[22px] mb-2">Federal actions</h2>
            {rev?.map((r, i) => <div key={i} className="text-[13px] py-2 border-t border-[var(--line)]"><span className="font-medium">Medicare revocation</span> effective {r.revoked_dt}, bar to {r.reenroll_bar_dt}<div className="text-[12px] text-[var(--ink-2)]">{r.revocation_rsn} · {r.provider_type_desc} · {r.state}</div></div>)}
            {leie?.map((r, i) => <div key={i} className="text-[13px] py-2 border-t border-[var(--line)]"><span className="font-medium">OIG exclusion</span> {r.excl_dt} under section {r.excltype}<div className="text-[12px] text-[var(--ink-2)]">{r.general} · {r.specialty} · {r.city}, {r.state}</div></div>)}
          </div> : null}
          {d3.length ? <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-2">Paid after the action</h2>
            <table className="table w-full"><thead><tr><th>source</th><th>action date</th><th>window end</th><th>months paid after</th><th>first</th><th>last</th><th>paid after</th><th>12 months before</th><th>tier</th></tr></thead>
              <tbody>{d3.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td>{e.source}<div className="text-[11px] text-[var(--ink-3)] max-w-[260px]">{e.reason}</div></td><td>{e.event_dt}</td><td>{e.window_end ?? "open"}</td><td>{e.months_paid_after}</td><td>{e.first_month_after}</td><td>{e.last_month_after}</td><td>{money(e.paid_after)}</td><td>{money(e.paid_before_12m)}</td><td>{f.tier}</td></tr>; })}</tbody></table>
          </div> : null}
          {d2.length ? <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-2">Implied hours by month</h2>
            <p className="text-[12px] text-[var(--ink-3)] mb-2">Lower bound uses claim lines only (one unit per line). Point and conservative use the state unit price (published for Minnesota, estimated elsewhere, conservative is 1.5x). Labels need the conservative figure.</p>
            <table className="table w-full"><thead><tr><th>month</th><th>label</th><th>h/day lower bound</th><th>h/day point</th><th>h/day conservative</th><th>patients</th><th>billing orgs</th><th>codes</th><th>paid</th><th>robust z</th></tr></thead>
              <tbody>{d2.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px]">{e.label}</td><td>{Number(e.hours_lb_per_day).toFixed(1)}</td><td>{Number(e.hours_pt_per_day).toFixed(1)}</td><td>{Number(e.hours_cons_per_day).toFixed(1)}</td><td>{e.patients}</td><td>{e.n_billing_orgs}</td><td className="text-[11px]">{(e.codes || []).join(" ")}</td><td>{money(e.paid)}</td><td>{e.robust_z != null ? Number(e.robust_z).toFixed(1) : ""}</td></tr>; })}</tbody></table>
          </div> : null}
          {members?.length ? <div className="card bg-white p-5"><h2 className="serif text-[22px] mb-2">Communities</h2>{members.map((m: any) => <Link key={m.cluster_id} href={`/app/clusters/${m.cluster_id}`} className="block py-2 border-t border-[var(--line)] text-[13px]"><span className="font-medium">{m.cluster_id}</span> <span className="text-[var(--ink-3)]">rank {m.clusters?.rank}</span><div className="text-[12px] text-[var(--ink-2)]">{m.clusters?.summary}</div></Link>)}</div> : null}
        </div>
        <PacketPanel subjectType="provider" subjectId={npi} existing={packets ?? []} />
      </div>
    </div>
  );
}
