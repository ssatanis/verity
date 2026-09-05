import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
export const revalidate = 120;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
export default async function Flags({ searchParams }: { searchParams: Promise<{ detector?: string; state?: string; tier?: string }> }) {
  const { detector = "D3", state, tier = "A" } = await searchParams; const sb = publicClient();
  let q = sb.from("flags").select("*").eq("detector", detector).order("score", { ascending: false }).limit(300);
  if (state) q = q.eq("state", state); if (tier !== "all") q = q.eq("tier", tier);
  const { data } = await q;
  const byNpi = new Map<string, any>(); for (const f of data ?? []) if (!byNpi.has(f.npi)) byNpi.set(f.npi, f);
  const rows = [...byNpi.values()];
  return (
    <div>
      <div className="eyebrow">Indicators</div>
      <h1 className="display serif text-[54px] mt-2">{detector === "D3" ? "Paid after a screening trigger" : "Impossible days"}</h1>
      <p className="text-[13.5px] text-[var(--ink-2)] mt-4 mb-5 max-w-3xl leading-6">{detector === "D3" ? "NPIs on a Medicare revocation, OIG exclusion, SAM debarment or state exclusion list with Medicaid service months dated after the action. Tier A: integrity grounds, check-digit valid, name agreement with NPPES. The dollars are service months after an action that should have triggered a state screening check under 42 CFR 455.436, not a determination of improper payment." : "Rendering NPIs whose personal-service codes imply more clinician hours than a day holds under conservative unit prices, organisations with more than 24 hours per patient per day, and Minnesota providers over the state's own per-child caps. Tier A needs three or more billing organisations in the same month, a per-patient breach, or a cap breach; a single-organisation impossibility is tier B because several states let clinics bill under a supervising clinician's NPI."}</p>
      <div className="flex flex-wrap gap-2 mb-5 text-[12px]">{[["D3", "Paid after a trigger"], ["D2", "Impossible days"]].map(([d, n]) => <Link key={d} href={`/app/flags?detector=${d}`} className={`tag ${detector === d ? "tag-ink" : ""}`}>{n}</Link>)}
        <Link href={`/app/flags?detector=${detector}&tier=all`} className={`tag ${tier === "all" ? "tag-ink" : ""}`}>all tiers</Link>{state && <span className="tag tag-accent">{state}</span>}</div>
      <div className="card overflow-x-auto"><table className="table">
        {detector === "D3" ? <thead><tr><th>provider</th><th>state</th><th>source</th><th>action</th><th>months after</th><th>paid after</th><th>tier</th><th>score</th></tr></thead>
          : <thead><tr><th>provider</th><th>state</th><th>peak month</th><th>label</th><th>h/day (test)</th><th>lower bound</th><th>billing orgs</th><th>paid that month</th><th>score</th></tr></thead>}
        <tbody>{rows.map(f => { const e = ev(f.evidence); return detector === "D3"
          ? <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link">{f.name || e.nppes_name || f.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{f.npi} · {f.entity_type === "2" ? "organisation" : "individual"}</div></td><td>{f.state}</td><td className="text-[12px]">{e.source}<div className="text-[11px] text-[var(--ink-3)] max-w-[280px]">{e.reason}</div></td><td>{e.event_dt}</td><td>{e.months_paid_after} <span className="text-[var(--ink-3)] text-[11px]">{e.first_month_after} to {e.last_month_after}</span></td><td>{money(e.paid_after)}</td><td>{f.tier}</td><td>{Number(f.score).toFixed(2)}</td></tr>
          : <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link">{f.name || e.name || f.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{f.npi} · {e.entity_type === "2" ? "organisation" : "individual"} · {e.taxonomy}</div></td><td>{f.state}</td><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px]">{e.label}</td><td>{Number(f.value).toFixed(1)}</td><td>{Number(e.hours_lb_per_day).toFixed(1)}</td><td>{e.n_billing_orgs}</td><td>{money(e.paid)}</td><td>{Number(f.score).toFixed(2)}</td></tr>; })}</tbody>
      </table></div>
    </div>
  );
}
