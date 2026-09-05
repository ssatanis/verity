import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
export const revalidate = 120;
export default async function Clusters({ searchParams }: { searchParams: Promise<{ state?: string; all?: string }> }) {
  const { state, all } = await searchParams; const sb = publicClient();
  let q = sb.from("clusters").select("id,rank,score,state,city,county,n_providers,n_hospice,n_hha,n_snf,dollars_at_risk,dollars_medicare,summary,eligible,chain_or_pe").order("rank").limit(200);
  q = all ? q : q.eq("eligible", true); if (state) q = q.eq("state", state);
  const { data } = await q;
  const { data: states } = await sb.from("clusters").select("state").eq("eligible", true).limit(5000);
  const counts = Object.entries((states ?? []).reduce((a: any, r: any) => ((a[r.state] = (a[r.state] || 0) + 1), a), {})).sort((a: any, b: any) => b[1] - a[1]).slice(0, 14);
  return (
    <div>
      <h1 className="serif text-[36px] leading-none mb-2">Provider communities</h1>
      <p className="text-[13px] text-[var(--ink-3)] mb-5 max-w-3xl">Ranked by the robust-z composite. Chains and private-equity platforms are scored but held out of this list. A community needs at least two independent evidence families to rank.</p>
      <div className="flex flex-wrap gap-2 mb-5 text-[12px]">
        <Link href="/app/clusters" className={`pill border px-3 py-1 ${!state ? "bg-[var(--ink)] text-white" : "border-[var(--line)]"}`}>All</Link>
        {counts.map(([s, n]: any) => <Link key={s} href={`/app/clusters?state=${s}`} className={`pill border px-3 py-1 ${state === s ? "bg-[var(--ink)] text-white" : "border-[var(--line)]"}`}>{s} <span className="opacity-60">{n}</span></Link>)}
        <Link href={`/app/clusters?all=1${state ? `&state=${state}` : ""}`} className="pill border border-[var(--line)] px-3 py-1 text-[var(--ink-3)]">include chains</Link>
      </div>
      <div className="card bg-white overflow-x-auto"><table className="table w-full">
        <thead><tr><th>rank</th><th>community</th><th>where</th><th>providers</th><th>score</th><th>Medicaid 2024</th><th>Medicare 2023</th><th>why</th></tr></thead>
        <tbody>{data?.map(c => <tr key={c.id}><td>{c.rank}</td><td><Link href={`/app/clusters/${c.id}`} className="link-underline">{c.id}</Link>{c.chain_or_pe && <span className="tag ml-1">chain</span>}</td><td>{c.city}</td><td>{c.n_providers} <span className="text-[var(--ink-3)]">({c.n_hospice}H {c.n_hha}HHA {c.n_snf}SNF)</span></td><td>{Number(c.score).toFixed(2)}</td><td>{money(c.dollars_at_risk)}</td><td>{money(c.dollars_medicare)}</td><td className="max-w-[420px] text-[12px] text-[var(--ink-2)]">{c.summary}</td></tr>)}</tbody>
      </table></div>
    </div>
  );
}
