import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { CountyMap } from "@/components/app/CountyMap";
import { Tier } from "@/components/app/Tier";
import { withFallback } from "@/lib/fallback";
import { money } from "@/lib/labels";
export const revalidate = 120;
const num = (v: any) => Number(v ?? 0).toLocaleString("en-US");
export default async function Overview() {
  const sb = publicClient();
  const [summ, counties, clusters, top] = await Promise.all([
    withFallback<any[]>("summary", () => sb.from("summary").select("key,value").eq("key", "totals"), rows => rows.filter((r: any) => r.key === "totals")),
    withFallback<any[]>("county_risk", () => sb.from("county_risk").select("*").order("dollars_at_risk", { ascending: false }).limit(3200)),
    withFallback<any[]>("clusters", () => sb.from("clusters").select("id,rank,score,state,city,n_providers,dollars_at_risk,summary,features").eq("eligible", true).order("rank").limit(6), rows => rows.slice(0, 6)),
    withFallback<any[]>("provider_risk", () => sb.from("provider_risk").select("npi,name,state,tier,tier_label,detectors,score,dollars_at_risk,reasons").order("rank").limit(10), rows => rows.slice(0, 10)),
  ]);
  const t = (summ?.find((s: any) => s.key === "totals")?.value as any) ?? {};
  const kpis = [
    { l: "On a public list, still paid afterwards", v: num(t.risk_tier1), s: `${money(t.d3_dollars_after)} paid after the action`, href: "/app/candidates?tier=1" },
    { l: "More hours than a day holds, across organisations", v: num(t.risk_tier2), s: `${num(t.d2_npis_impossible)} clinicians with at least one such month`, href: "/app/candidates?tier=2" },
    { l: "Flagged by two detectors independently", v: num(t.risk_corroborated), s: "the strongest signal the system produces", href: "/app/candidates" },
    { l: "Provider networks ranked", v: num(t.d1_clusters_eligible), s: `${money(t.d1_dollars_top200)} Medicaid 2024 in the top 200`, href: "/app/clusters" },
  ];
  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div><div className="eyebrow">Overview</div><h1 className="display serif text-[40px] md:text-[54px] mt-2">Who to look at first, and why.</h1><p className="text-[13px] text-[var(--ink-3)] mt-3">Medicaid spending 2018 to 2024 for every state, Medicare enrollments as of July 2026, exclusion lists as of September 2026. {num(t.spend_rows)} spending rows scanned.</p></div>
        <Link href="/app/methods" className="link text-[13px] shrink-0">How the numbers are made</Link>
      </div>
      <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-px mb-6" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
        {kpis.map(k => <Link key={k.l} href={k.href} className="block p-5 hover:bg-[var(--paper-2)]" style={{ background: "var(--paper)" }}><div className="eyebrow">{k.l}</div><div className="serif text-[44px] leading-none mt-3" style={{ color: "var(--blue)" }}>{k.v}</div><div className="text-[11px] text-[var(--ink-3)] mt-2">{k.s}</div></Link>)}
      </div>
      <div className="card p-2 mb-6"><CountyMap counties={(counties as any) ?? []} /></div>
      <div className="grid md:grid-cols-[1.3fr_1fr] gap-6">
        <div className="card p-5 overflow-x-auto">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[24px]">Providers to look at first</h2><Link href="/app/candidates" className="link text-[12px]">All providers</Link></div>
          <table className="table"><thead><tr><th>tier</th><th>provider</th><th>at stake</th></tr></thead>
            <tbody>{top?.map(r => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11.5px] text-[var(--ink-2)] max-w-[460px] leading-5">{r.reasons}</div></td><td>{money(r.dollars_at_risk)}</td></tr>)}</tbody></table>
        </div>
        <div className="card p-5">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[24px]">Networks to look at first</h2><Link href="/app/clusters" className="link text-[12px]">All networks</Link></div>
          {clusters?.map(c => { const f = (typeof c.features === "string" ? JSON.parse(c.features) : c.features) ?? {}; const facts: string[] = f.facts ?? []; return (
            <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 rule hover:bg-[var(--paper-2)]">
              <div className="flex justify-between text-[13px]"><span className="serif text-[17px]">{c.summary}</span><span className="serif text-[17px]" style={{ color: "var(--blue)" }}>{Number(c.score).toFixed(0)}</span></div>
              <div className="text-[11.5px] text-[var(--ink-2)] mt-1 line-clamp-2">{facts.slice(0, 2).join(" ")}</div>
              <div className="text-[11px] text-[var(--ink-3)] mt-1">{c.id} · {money(c.dollars_at_risk)} Medicaid 2024</div>
            </Link>); })}
        </div>
      </div>
    </div>
  );
}
