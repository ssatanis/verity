import Link from "next/link";
import { publicClient, money, num } from "@/lib/supabase";
import { CountyMap } from "@/components/app/CountyMap";

export const revalidate = 120;
export default async function Overview() {
  const sb = publicClient();
  const [{ data: summ }, { data: counties }, { data: clusters }, { data: flags }] = await Promise.all([
    sb.from("summary").select("key,value"),
    sb.from("county_risk").select("*").order("dollars_at_risk", { ascending: false }).limit(3200),
    sb.from("clusters").select("id,rank,score,state,city,n_providers,n_hospice,n_hha,n_snf,dollars_at_risk,summary").eq("eligible", true).order("rank").limit(8),
    sb.from("flags").select("id,detector,npi,name,state,month,metric,value,dollars,tier,score").eq("tier", "A").order("score", { ascending: false }).limit(8),
  ]);
  const t = (summ?.find(s => s.key === "totals")?.value as any) ?? {};
  const kpis = [
    { l: "Medicaid paid after a federal or state action", v: money(t.d3_dollars_after), s: `${num(t.d3_npis_paid_after)} NPIs, tier A lists only` , href: "/app/flags?detector=D3" },
    { l: "Rendering NPIs with an impossible month", v: num(t.d2_npis_impossible), s: `${money(t.d2_dollars_impossible)} paid in those months`, href: "/app/flags?detector=D2" },
    { l: "Provider communities ranked", v: num(t.d1_clusters_eligible), s: `${money(t.d1_dollars_top200)} Medicaid 2024 in the top 200`, href: "/app/clusters" },
    { l: "Rows scanned", v: num(t.spend_rows), s: `${num(t.nppes)} NPIs, ${num(t.providers_with_state)} Medicaid providers`, href: "/app/methods" },
  ];
  return (
    <div>
      <div className="flex items-end justify-between mb-6">
        <div><h1 className="serif text-[36px] leading-none">National tripwire</h1><p className="text-[13px] text-[var(--ink-3)] mt-2">T-MSIS 2018 to 2024, CMS enrollment July 2026, LEIE and SAM September 2026. Generated {t.generated_at ? new Date(t.generated_at).toLocaleString() : ""}.</p></div>
        <Link href="/app/methods" className="link-underline text-[12px]">Every number, show the math</Link>
      </div>
      <div className="grid md:grid-cols-4 gap-4 mb-6">
        {kpis.map(k => <Link key={k.l} href={k.href} className="kpi block hover:border-[#c9c9cf]"><div className="text-[11px] text-[var(--ink-3)]">{k.l}</div><div className="serif text-[34px] mt-2">{k.v}</div><div className="text-[11px] text-[var(--ink-3)] mt-1">{k.s}</div></Link>)}
      </div>
      <div className="card bg-white p-2 mb-6"><CountyMap counties={(counties as any) ?? []} /></div>
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card bg-white p-5">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[22px]">Top communities</h2><Link href="/app/clusters" className="link-underline text-[12px]">All</Link></div>
          {clusters?.map(c => (
            <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 border-t border-[var(--line)] hover:bg-[var(--surface-2)] -mx-2 px-2 rounded">
              <div className="flex justify-between text-[13px]"><span className="font-medium">{c.id} · {c.city}</span><span>{Number(c.score).toFixed(1)}</span></div>
              <div className="text-[11.5px] text-[var(--ink-3)] mt-1 line-clamp-2">{c.summary}</div>
              <div className="text-[11px] text-[var(--ink-3)] mt-1">{c.n_providers} providers · {money(c.dollars_at_risk)} Medicaid 2024</div>
            </Link>
          ))}
        </div>
        <div className="card bg-white p-5">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[22px]">Top flags</h2><Link href="/app/flags" className="link-underline text-[12px]">All</Link></div>
          {flags?.map(f => (
            <Link key={String(f.id)} href={`/app/providers/${f.npi}`} className="block py-3 border-t border-[var(--line)] hover:bg-[var(--surface-2)] -mx-2 px-2 rounded">
              <div className="flex justify-between text-[13px]"><span className="font-medium">{f.name || f.npi} <span className="tag ml-1">{f.detector}</span> <span className="tag">{f.state}</span></span><span>{money(f.dollars)}</span></div>
              <div className="text-[11.5px] text-[var(--ink-3)] mt-1">{f.metric?.replace(/_/g, " ")} {Number(f.value).toLocaleString(undefined, { maximumFractionDigits: 1 })} · {f.month}</div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
