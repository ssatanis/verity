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
      <div className="eyebrow">Ghost network indicator</div>
      <h1 className="display serif text-[54px] mt-2">Provider communities</h1>
      <p className="text-[13.5px] text-[var(--ink-2)] mt-4 mb-5 max-w-3xl leading-6">Communities of hospice, home health and skilled nursing enrollments linked through owners, suites, phones, officials and the addresses of revoked entities, ranked by a robust-z composite. A community ranks only with three or more distinct organisations, at least one formed since 2021, two independent evidence families, and less than half its members in a known chain. Chains and platforms are scored but held out.</p>
      <div className="flex flex-wrap gap-2 mb-5 text-[12px]">
        <Link href="/app/clusters" className={`tag ${!state ? "tag-ink" : ""}`}>All</Link>
        {counts.map(([s, n]: any) => <Link key={s} href={`/app/clusters?state=${s}`} className={`tag ${state === s ? "tag-ink" : ""}`}>{s} <span className="opacity-60">{n}</span></Link>)}
        <Link href={`/app/clusters?all=1${state ? `&state=${state}` : ""}`} className={`tag ${all ? "tag-ink" : ""}`}>include chains</Link>
      </div>
      <div className="card overflow-x-auto"><table className="table">
        <thead><tr><th>rank</th><th>community</th><th>where</th><th>enrollments</th><th>score</th><th>Medicaid 2024</th><th>Medicare 2023</th><th>why</th></tr></thead>
        <tbody>{data?.map(c => <tr key={c.id}><td>{c.rank}</td><td><Link href={`/app/clusters/${c.id}`} className="link">{c.id}</Link>{c.chain_or_pe && <span className="tag ml-1">chain</span>}</td><td>{c.city}, {c.state}</td><td>{c.n_providers} <span className="text-[var(--ink-3)]">({c.n_hospice} hospice, {c.n_hha} HHA, {c.n_snf} SNF)</span></td><td>{Number(c.score).toFixed(2)}</td><td>{money(c.dollars_at_risk)}</td><td>{money(c.dollars_medicare)}</td><td className="max-w-[420px] text-[12px] text-[var(--ink-2)]">{c.summary}</td></tr>)}</tbody>
      </table></div>
    </div>
  );
}
