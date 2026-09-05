import Link from "next/link";
import { publicClient } from "@/lib/supabase";
export const revalidate = 300;
export default async function Plazas({ searchParams }: { searchParams: Promise<{ state?: string }> }) {
  const { state } = await searchParams; const sb = publicClient();
  let q = sb.from("hub_addresses").select("*").order("n_providers", { ascending: false }).limit(150); if (state) q = q.eq("state", state);
  const { data } = await q;
  return (
    <div>
      <div className="eyebrow">Provider plazas</div>
      <h1 className="display serif text-[54px] mt-2">Addresses that host many enrollments.</h1>
      <p className="text-[13.5px] text-[var(--ink-2)] mt-4 max-w-3xl leading-6">Los Angeles County counted 89 hospices registered at one Van Nuys office plaza. This table lists every address with eight or more hospice, home health or skilled nursing enrollments, how many formed since 2019, how many members are on a list, and whether a revoked or excluded entity is registered there. Large medical office buildings appear here too; the address is an indicator, not a finding.</p>
      <div className="card mt-6 overflow-x-auto"><table className="table">
        <thead><tr><th>address</th><th>city</th><th>providers</th><th>hospice</th><th>HHA</th><th>SNF</th><th>formed since 2019</th><th>on a list</th><th>revoked entity here</th><th>members</th></tr></thead>
        <tbody>{data?.map(r => <tr key={r.address}><td className="mono">{String(r.address).split("|")[0]}{r.level === "unit" ? " (suite)" : ""}</td><td>{r.city}, {r.state} {r.zip5}</td><td>{r.n_providers}</td><td>{r.n_hospice}</td><td>{r.n_hha}</td><td>{r.n_snf}</td><td>{r.n_since_2019}</td><td>{r.n_labelled}</td><td>{r.revoked_entity_here ? "yes" : ""}</td><td className="text-[11px]">{((r.npis as string[]) ?? []).slice(0, 6).map(n => <Link key={n} href={`/app/providers/${n}`} className="link mr-2">{n}</Link>)}{(r.npis as string[])?.length > 6 ? `+${(r.npis as string[]).length - 6}` : ""}</td></tr>)}</tbody>
      </table></div>
    </div>
  );
}
