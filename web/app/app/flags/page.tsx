import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
export const revalidate = 120;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
export default async function Flags({ searchParams }: { searchParams: Promise<{ detector?: string; state?: string; tier?: string }> }) {
  const { detector = "D3", state, tier = "A" } = await searchParams; const sb = publicClient();
  let q = sb.from("flags").select("*").eq("detector", detector).order("score", { ascending: false }).limit(300);
  if (state) q = q.eq("state", state); if (tier !== "all") q = q.eq("tier", tier);
  const { data } = await q;
  // one row per NPI for D3 (multiple sources) and per NPI for D2 (peak month)
  const byNpi = new Map<string, any>(); for (const f of data ?? []) if (!byNpi.has(f.npi)) byNpi.set(f.npi, f);
  const rows = [...byNpi.values()];
  return (
    <div>
      <h1 className="serif text-[36px] leading-none mb-2">{detector === "D3" ? "Revoked or excluded, still paid" : "Impossible days"}</h1>
      <p className="text-[13px] text-[var(--ink-3)] mb-5 max-w-3xl">{detector === "D3" ? "NPIs on a Medicare revocation, OIG exclusion or state exclusion list with Medicaid claims dated after the action. Tier A: integrity grounds and name-verified matches only." : "Rendering NPIs whose personal-service codes (E/M, psychotherapy, evaluations) imply more clinician hours than a day holds under conservative unit prices, organisations with more than 24 hours per patient per day, and Minnesota providers over the state's own per-child EIDBI caps. Tier A requires the impossible hours to have been billed by three or more different organisations in the same month, or a per-patient or Minnesota-cap breach; a single-organisation impossibility is tier B because several states let clinics bill under a supervising clinician's NPI."}</p>
      <div className="flex gap-2 mb-5 text-[12px]">{[["D3", "Revoked but paid"], ["D2", "Impossible days"]].map(([d, n]) => <Link key={d} href={`/app/flags?detector=${d}`} className={`pill border px-3 py-1 ${detector === d ? "bg-[var(--ink)] text-white" : "border-[var(--line)]"}`}>{n}</Link>)}
        <Link href={`/app/flags?detector=${detector}&tier=all`} className="pill border border-[var(--line)] px-3 py-1 text-[var(--ink-3)]">all tiers</Link>{state && <span className="tag">{state}</span>}</div>
      <div className="card bg-white overflow-x-auto"><table className="table w-full">
        {detector === "D3" ? <thead><tr><th>provider</th><th>state</th><th>source</th><th>action</th><th>months paid after</th><th>paid after</th><th>tier</th><th>score</th></tr></thead>
          : <thead><tr><th>provider</th><th>state</th><th>peak month</th><th>label</th><th>h/day (test)</th><th>lower bound</th><th>billing orgs</th><th>paid that month</th><th>score</th></tr></thead>}
        <tbody>{rows.map(f => { const e = ev(f.evidence); return detector === "D3"
          ? <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link-underline">{f.name || e.nppes_name || f.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{f.npi} · {f.entity_type === "2" ? "org" : "individual"}</div></td><td>{f.state}</td><td className="text-[12px]">{e.source}<div className="text-[11px] text-[var(--ink-3)] max-w-[280px]">{e.reason}</div></td><td>{e.event_dt}</td><td>{e.months_paid_after} <span className="text-[var(--ink-3)] text-[11px]">{e.first_month_after} to {e.last_month_after}</span></td><td>{money(e.paid_after)}</td><td>{f.tier}</td><td>{Number(f.score).toFixed(2)}</td></tr>
          : <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link-underline">{f.name || e.name || f.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{f.npi} · {e.entity_type === "2" ? "org" : "individual"} · {e.taxonomy}</div></td><td>{f.state}</td><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px]">{e.label}</td><td>{Number(f.value).toFixed(1)}</td><td>{Number(e.hours_lb_per_day).toFixed(1)}</td><td>{e.n_billing_orgs}</td><td>{money(e.paid)}</td><td>{Number(f.score).toFixed(2)}</td></tr>; })}</tbody>
      </table></div>
    </div>
  );
}
