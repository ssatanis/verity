import Link from "next/link";
import { publicClient, money, num } from "@/lib/supabase";
import { CountyMap } from "@/components/app/CountyMap";
import { Tier } from "@/components/app/Tier";
import { withFallback } from "@/lib/fallback";
export const revalidate = 120;
export default async function Overview() {
  const sb = publicClient();
  const [summ, counties, clusters, top] = await Promise.all([
    withFallback<any[]>("summary", () => sb.from("summary").select("key,value"), rows => [{ key: "totals", value: rows }]),
    withFallback<any[]>("county_risk", () => sb.from("county_risk").select("*").order("dollars_at_risk", { ascending: false }).limit(3200)),
    withFallback<any[]>("clusters", () => sb.from("clusters").select("id,rank,score,state,city,n_providers,dollars_at_risk,summary").eq("eligible", true).order("rank").limit(6), rows => rows.slice(0, 6)),
    withFallback<any[]>("provider_risk", () => sb.from("provider_risk").select("npi,name,state,tier,tier_label,detectors,score,dollars_at_risk,reasons").order("rank").limit(10), rows => rows.slice(0, 10)),
  ]);
  const t = (summ?.find((s: any) => s.key === "totals")?.value as any) ?? {};
  const kpis = [
    { l: "Tier 1: documented action, then payment", v: num(t.risk_tier1), s: `${money(t.d3_dollars_after)} of service months after a list action`, href: "/app/candidates?tier=1" },
    { l: "Tier 2: impossible volume with concurrency", v: num(t.risk_tier2), s: `${num(t.d2_npis_impossible)} rendering NPIs with an impossible month`, href: "/app/candidates?tier=2" },
    { l: "Reached by two or more detectors", v: num(t.risk_corroborated), s: "the strongest signal in the system", href: "/app/candidates" },
    { l: "Provider communities ranked", v: num(t.d1_clusters_eligible), s: `${money(t.d1_dollars_top200)} Medicaid 2024 in the top 200`, href: "/app/clusters" },
  ];
  return (
    <div>
      <div className="flex items-end justify-between mb-6 gap-6">
        <div><div className="eyebrow">National tripwire</div><h1 className="display serif text-[54px] mt-2">Referral candidates from public data.</h1><p className="text-[13px] text-[var(--ink-3)] mt-3">T-MSIS 2018 to 2024, CMS enrollment July 2026, LEIE and SAM September 2026, {num(t.spend_rows)} spending rows. Built {t.generated_at ? new Date(t.generated_at).toLocaleString() : ""}.</p></div>
        <Link href="/app/methods" className="link text-[13px] shrink-0">Every number, show the math</Link>
      </div>
      <div className="grid md:grid-cols-4 gap-px mb-6" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
        {kpis.map(k => <Link key={k.l} href={k.href} className="block p-5 hover:bg-[var(--paper-2)]" style={{ background: "var(--paper)" }}><div className="eyebrow">{k.l}</div><div className="serif text-[44px] leading-none mt-3">{k.v}</div><div className="text-[11px] text-[var(--ink-3)] mt-2">{k.s}</div></Link>)}
      </div>
      <div className="card p-2 mb-6"><CountyMap counties={(counties as any) ?? []} /></div>
      <div className="grid md:grid-cols-[1.3fr_1fr] gap-6">
        <div className="card p-5 overflow-x-auto">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[24px]">Top referral candidates</h2><Link href="/app/candidates" className="link text-[12px]">All candidates</Link></div>
          <table className="table"><thead><tr><th>tier</th><th>provider</th><th>detectors</th><th>$ at risk</th></tr></thead>
            <tbody>{top?.map(r => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)] max-w-[420px]">{r.reasons}</div></td><td>{(r.detectors as string[])?.join(" ")}</td><td>{money(r.dollars_at_risk)}</td></tr>)}</tbody></table>
        </div>
        <div className="card p-5">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[24px]">Top provider communities</h2><Link href="/app/clusters" className="link text-[12px]">All</Link></div>
          {clusters?.map(c => (
            <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 rule hover:bg-[var(--paper-2)]">
              <div className="flex justify-between text-[13px]"><span className="serif text-[17px]">{c.id} · {c.city}</span><span>{Number(c.score).toFixed(1)}</span></div>
              <div className="text-[11.5px] text-[var(--ink-3)] mt-1 line-clamp-2">{c.summary}</div>
              <div className="text-[11px] text-[var(--ink-3)] mt-1">{c.n_providers} enrollments · {money(c.dollars_at_risk)} Medicaid 2024</div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
