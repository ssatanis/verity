import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { money } from "@/lib/labels";
export const revalidate = 120;
export default async function Clusters({ searchParams }: { searchParams: Promise<{ state?: string; all?: string }> }) {
  const { state, all } = await searchParams; const sb = publicClient();
  let q = sb.from("clusters").select("id,rank,score,state,city,county,n_providers,n_hospice,n_hha,n_snf,dollars_at_risk,dollars_medicare,summary,features,eligible,chain_or_pe").order("rank").limit(200);
  q = all ? q : q.eq("eligible", true); if (state) q = q.eq("state", state);
  const [{ data }, { data: states }, { data: plazas }] = await Promise.all([q, sb.from("clusters").select("state").eq("eligible", true).limit(1000), sb.from("hub_addresses").select("address,city,state,zip5,n_providers,n_since_2019,n_labelled,revoked_entity_here").order("n_providers", { ascending: false }).limit(6)]);
  const counts = Object.entries((states ?? []).reduce((a: any, r: any) => ((a[r.state] = (a[r.state] || 0) + 1), a), {})).sort((a: any, b: any) => b[1] - a[1]).slice(0, 12);
  return (
    <div>
      <div className="eyebrow">Provider networks</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">Groups of providers that belong together.</h1>
      <p className="text-[14px] text-[var(--ink-2)] mt-4 mb-5 max-w-3xl leading-6">Hospices, home health agencies and nursing facilities linked through shared owners, suites, phone numbers, officials and the addresses of revoked companies. A network is ranked only when it has three or more separate companies, at least one formed since 2021, two independent kinds of evidence, and fewer than half its members in a known chain. The score runs from 0 to 100 within the ranked networks.</p>
      <div className="flex flex-wrap gap-2 mb-5 text-[12px]">
        <Link href="/app/clusters" className={`tag ${!state ? "tag-ink" : ""}`}>All states</Link>
        {counts.map(([s, n]: any) => <Link key={s} href={`/app/clusters?state=${s}`} className={`tag ${state === s ? "tag-ink" : ""}`}>{s} <span className="opacity-60">{n}</span></Link>)}
        <Link href={`/app/clusters?all=1${state ? `&state=${state}` : ""}`} className={`tag ${all ? "tag-ink" : ""}`}>include chains</Link>
        <Link href="/app/plazas" className="tag">Addresses hosting many providers</Link>
      </div>
      <div className="card overflow-x-auto"><table className="table">
        <thead><tr><th>rank</th><th>network</th><th>providers</th><th>score</th><th>Medicaid 2024</th><th>what stands out</th></tr></thead>
        <tbody>{data?.map(c => { const f = (typeof c.features === "string" ? JSON.parse(c.features) : c.features) ?? {}; const facts: string[] = f.facts ?? []; return <tr key={c.id}><td>{c.rank}</td><td><Link href={`/app/clusters/${c.id}`} className="link serif text-[16px]">{c.summary}</Link><div className="text-[11px] text-[var(--ink-3)]">{c.id}{c.chain_or_pe ? ", chain" : ""}</div></td><td>{c.n_providers}</td><td className="serif text-[18px]" style={{ color: "var(--blue)" }}>{Number(c.score).toFixed(0)}</td><td>{money(c.dollars_at_risk)}</td><td className="max-w-[460px] text-[12px] text-[var(--ink-2)]"><ul className="space-y-1">{facts.slice(0, 3).map((x, i) => <li key={i}>{x}</li>)}</ul></td></tr>; })}</tbody>
      </table></div>
      {plazas?.length ? <div className="card p-5 mt-6"><div className="flex justify-between items-center"><h2 className="serif text-[24px]">Addresses hosting many providers</h2><Link href="/app/plazas" className="link text-[12px]">All addresses</Link></div><p className="text-[12.5px] text-[var(--ink-3)] mt-1 mb-2">One Van Nuys office plaza hosts dozens of hospice enrollments. Large medical buildings appear here too; an address is a lead, not a finding.</p>
        <table className="table"><thead><tr><th>address</th><th>providers</th><th>formed since 2019</th><th>on a list</th><th>revoked company here</th></tr></thead><tbody>{plazas.map((r: any) => <tr key={r.address}><td className="mono">{String(r.address).split("|")[0]}, {r.city} {r.state}</td><td>{r.n_providers}</td><td>{r.n_since_2019}</td><td>{r.n_labelled}</td><td>{r.revoked_entity_here ? "yes" : ""}</td></tr>)}</tbody></table></div> : null}
    </div>
  );
}
