import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { titleCase } from "@/lib/labels";
export const revalidate = 300;
export default async function Plazas({ searchParams }: { searchParams: Promise<{ state?: string }> }) {
  const { state } = await searchParams; const sb = publicClient();
  let q = sb.from("hub_addresses").select("*").order("n_providers", { ascending: false }).limit(150); if (state) q = q.eq("state", state);
  const { data } = await q;
  return (
    <div>
      <div className="eyebrow">Provider networks, addresses</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">Addresses that host many providers.</h1>
      <p className="text-[13.5px] text-[var(--ink-2)] mt-4 max-w-3xl leading-6">Los Angeles County counted dozens of hospices registered at one Van Nuys office plaza. This table lists every address with eight or more hospice, home health or nursing facility enrollments, how many formed since 2019, how many are on a public list, and whether a revoked or excluded company is registered there. Large medical office buildings appear here too; an address is a lead, not a finding.</p>
      <div className="card mt-6 overflow-x-auto"><table className="table">
        <thead><tr><th>address</th><th>city</th><th>providers</th><th>hospice</th><th>HHA</th><th>SNF</th><th>formed since 2019</th><th>on a list</th><th>revoked company here</th><th>providers</th></tr></thead>
        <tbody>{data?.map(r => <tr key={r.address}><td className="mono">{String(r.address).split("|")[0]}{r.level === "unit" ? " (suite)" : ""}</td><td>{titleCase(r.city)}, {r.state} {r.zip5}</td><td>{r.n_providers}</td><td>{r.n_hospice}</td><td>{r.n_hha}</td><td>{r.n_snf}</td><td>{r.n_since_2019}</td><td>{r.n_labelled}</td><td>{r.revoked_entity_here ? "yes" : ""}</td><td className="text-[11px]">{(() => { const npis = [...new Set(((r.npis as string[]) ?? []))]; return <>{npis.slice(0, 6).map(n => <Link key={n} href={`/app/providers/${n}`} className="link mr-2">{n}</Link>)}{npis.length > 6 ? `+${npis.length - 6}` : ""}</>; })()}</td></tr>)}</tbody>
      </table></div>
    </div>
  );
}
