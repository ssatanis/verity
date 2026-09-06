import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { CountyMap } from "@/components/app/CountyMap";
import { Tier } from "@/components/app/Tier";
import { Reasons } from "@/components/app/Reasons";
import { withFallback } from "@/lib/fallback";
import { money, dateLong } from "@/lib/labels";
export const revalidate = 120;
const num = (v: any) => Number(v ?? 0).toLocaleString("en-US");
export default async function Overview() {
  const sb = publicClient();
  // A failed count is not a count of zero: keep it null so the tile can say the figure is unavailable instead of
  // reporting that no network has momentum.
  // The newest enforcement release the feed has matched to a provider. It is what makes the daily refresh visible.
  let lastEnf: string | null = null;
  try { const r = await sb.from("provider_risk").select("enf_first_event").not("enf_first_event", "is", null).order("enf_first_event", { ascending: false }).limit(1); if (!r.error) lastEnf = r.data?.[0]?.enf_first_event ?? null; } catch {}
  let rising: number | null = null;
  try { const r = await sb.from("network_factors").select("cluster_id", { count: "exact", head: true }).eq("factor", "momentum").eq("outlook", "rising fast"); if (!r.error) rising = r.count ?? 0; } catch {}
  const [summ, counties, clusters, top] = await Promise.all([
    withFallback<any[]>("summary", () => sb.from("summary").select("key,value").eq("key", "totals"), rows => rows.filter((r: any) => r.key === "totals")),
    withFallback<any[]>("county_risk", () => sb.from("county_risk").select("*").order("dollars_at_risk", { ascending: false }).limit(3200)),
    withFallback<any[]>("clusters", () => sb.from("clusters").select("id,rank,score,state,city,n_providers,dollars_at_risk,summary,features").eq("eligible", true).order("rank").limit(6), rows => rows.slice(0, 6)),
    withFallback<any[]>("provider_risk", () => sb.from("provider_risk").select("npi,name,state,tier,tier_label,detectors,score,dollars_at_risk,reasons").order("rank").limit(10), rows => rows.slice(0, 10)),
  ]);
  const t = (summ?.find((s: any) => s.key === "totals")?.value as any) ?? {};
  const kpis = [
    { l: "On a public list, still paid afterwards", v: num(t.risk_tier1), s: `${money(t.d3_dollars_after)} paid after the action`, href: "/app/candidates?tier=1" },
    { l: "More hours than a day holds, across organizations", v: num(t.risk_tier2), s: `${num(t.d2_npis_impossible)} clinicians with at least one such month`, href: "/app/candidates?tier=2" },
    { l: "Networks with momentum rising fast", v: rising == null ? "not available" : num(rising), s: `formation, ownership and billing all accelerating; ${num(t.risk_corroborated)} providers flagged by two detectors`, href: "/app/clusters" },
    { l: "Provider networks ranked", v: num(t.d1_clusters_eligible), s: `${money(t.d1_dollars_top200)} Medicaid 2024 in the top 200`, href: "/app/clusters" },
  ];
  return (
    <div>
      <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
        <div><div className="eyebrow">Overview</div><h1 className="display serif text-[34px] md:text-[44px] mt-2">Who to look at first, and why.</h1><p className="text-[13px] text-[var(--ink-3)] mt-3">Medicaid spending 2018 to 2024 for every state, across {num(t.spend_rows)} rows, with Medicare enrollments and exclusion lists to September 2026. Department of Justice and HHS-OIG enforcement records refresh every day{lastEnf ? `, the latest dated ${dateLong(lastEnf)}` : ""}.</p></div>
        <Link href="/app/methods" className="link text-[13px] shrink-0">How the numbers are made</Link>
      </div>
      <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-px mb-6" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
        {kpis.map(k => <Link key={k.l} href={k.href} className="kpi-card block p-5 hover:bg-[var(--paper-2)]" style={{ background: "var(--paper)" }}><div className="eyebrow">{k.l}</div><div className={`serif leading-none mt-3 ${k.v === "not available" ? "text-[22px] text-[var(--ink-3)]" : "text-[44px]"}`} style={{ color: k.v === "not available" ? undefined : "var(--blue)" }}>{k.v}</div><div className="text-[11px] text-[var(--ink-3)] mt-2">{k.s}</div></Link>)}
      </div>
      <div className="card p-2 mb-6"><CountyMap counties={(counties as any) ?? []} /></div>
      <div className="grid md:grid-cols-[1.3fr_1fr] gap-6">
        <div className="card p-5 overflow-x-auto">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[24px]">Providers to look at first</h2><Link href="/app/candidates" className="link text-[12px]">All providers</Link></div>
          <table className="table"><thead><tr><th>tier</th><th>provider</th><th>at stake</th></tr></thead>
            <tbody className="rows-in">{top?.map(r => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11.5px] text-[var(--ink-2)] max-w-[460px] leading-5 mt-1"><Reasons text={r.reasons} compact max={3} /></div></td><td>{money(r.dollars_at_risk)}</td></tr>)}</tbody></table>
        </div>
        <div className="card p-5">
          <div className="flex justify-between items-center mb-3"><h2 className="serif text-[24px]">Networks to look at first</h2><Link href="/app/clusters" className="link text-[12px]">All networks</Link></div>
          {clusters?.map(c => { const f = (typeof c.features === "string" ? JSON.parse(c.features) : c.features) ?? {}; const facts: string[] = f.facts ?? []; return (
            <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 rule hover:bg-[var(--paper-2)] transition-colors">
              <div className="flex justify-between text-[13px]"><span className="serif text-[17px]">{c.summary}</span><span style={{ color: "var(--blue)" }}>{Number(c.score).toFixed(0)}</span></div>
              <div className="text-[11.5px] text-[var(--ink-2)] mt-1 line-clamp-2">{facts.slice(0, 2).join(" ")}</div>
              <div className="text-[11px] text-[var(--ink-3)] mt-1">{c.id}, {money(c.dollars_at_risk)} Medicaid 2024</div>
            </Link>); })}
        </div>
      </div>
    </div>
  );
}
