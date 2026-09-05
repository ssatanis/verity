import Link from "next/link";
import { publicClient, money, num } from "@/lib/supabase";
export const revalidate = 120;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
export default async function StatePage({ params }: { params: Promise<{ st: string }> }) {
  const { st } = await params; const S = st.toUpperCase(); const sb = publicClient();
  const [{ data: counties }, { data: clusters }, { data: d3 }, { data: d2 }, { data: summ }] = await Promise.all([
    sb.from("county_risk").select("*").eq("state", S).order("dollars_at_risk", { ascending: false }).limit(20),
    sb.from("clusters").select("id,rank,score,city,n_providers,dollars_at_risk,summary").eq("state", S).eq("eligible", true).order("rank").limit(10),
    sb.from("flags").select("*").eq("detector", "D3").eq("state", S).eq("tier", "A").order("dollars", { ascending: false }).limit(15),
    sb.from("flags").select("*").eq("detector", "D2").eq("state", S).order("score", { ascending: false }).limit(15),
    sb.from("summary").select("key,value"),
  ]);
  const tot = (counties ?? []).reduce((a, c) => ({ d1: a.d1 + Number(c.d1_dollars || 0), d2: a.d2 + Number(c.d2_dollars || 0), d3: a.d3 + Number(c.d3_dollars || 0) }), { d1: 0, d2: 0, d3: 0 });
  const d2s = (summ?.find(s => s.key === "d2_summary")?.value as any) ?? {}; const mnCodes = S === "MN" ? d2s.mn_codes ?? [] : []; const val = S === "MN" ? d2s.validation ?? [] : [];
  const seen = new Set<string>(); const d2rows = (d2 ?? []).filter(f => !seen.has(f.npi) && seen.add(f.npi));
  return (
    <div>
      <h1 className="serif text-[36px] leading-none">{S}: show the math</h1>
      <p className="text-[13px] text-[var(--ink-3)] mt-2 max-w-3xl">Dollars at risk decomposed by detector for the counties in this state, every figure traceable to a public row. Deferral-style totals are sums of flagged Medicaid dollars, not estimates.</p>
      <div className="grid md:grid-cols-3 gap-4 mt-6 mb-6">
        {[["Ghost networks (Medicaid 2024, top communities)", tot.d1], ["Impossible days (paid in flagged months)", tot.d2], ["Revoked but paid (after the action)", tot.d3]].map(([l, v]) => <div key={String(l)} className="kpi"><div className="text-[11px] text-[var(--ink-3)]">{l}</div><div className="serif text-[34px] mt-2">{money(v as number)}</div></div>)}
      </div>
      {S === "MN" && (
        <div className="grid md:grid-cols-2 gap-6 mb-6">
          <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-1">EIDBI, CTSS, HSS and PCA codes</h2><p className="text-[12px] text-[var(--ink-3)] mb-2">Rendering NPIs, Medicaid dollars 2018 to 2024, implied hours, and where the unit price came from.</p>
            <table className="table w-full"><thead><tr><th>code</th><th>NPIs</th><th>$M</th><th>implied hours (M)</th><th>rate source</th></tr></thead><tbody>{mnCodes.map((r: any[]) => <tr key={r[0]}><td>{r[0]}</td><td>{num(Number(r[1]))}</td><td>{r[2]}</td><td>{r[3]}</td><td className="text-[11px]">{r[4]}</td></tr>)}</tbody></table></div>
          <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-1">Unit price validation</h2><p className="text-[12px] text-[var(--ink-3)] mb-2">Data-driven estimates against Minnesota's published DHS-3945 and EIDBI rates. Positive error means the estimate sits above the published price, which keeps implied hours conservative.</p>
            <table className="table w-full"><thead><tr><th>estimator</th><th>median signed error</th><th>median abs error</th><th>code-years</th></tr></thead><tbody>{val.map((r: any[]) => <tr key={r[0]}><td>{r[0]}</td><td>{r[1] ?? ""}{r[1] != null ? "%" : ""}</td><td>{r[2] ?? ""}{r[2] != null ? "%" : ""}</td><td>{r[3]}</td></tr>)}</tbody></table></div>
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="card bg-white p-5"><h2 className="serif text-[22px] mb-2">Counties</h2><table className="table w-full"><thead><tr><th>county</th><th>communities</th><th>flagged NPIs</th><th>at risk</th></tr></thead><tbody>{counties?.map(c => <tr key={c.county_fips}><td>{c.county_name}</td><td>{c.n_clusters}</td><td>{c.n_providers_flagged}</td><td>{money(c.dollars_at_risk)}</td></tr>)}</tbody></table></div>
        <div className="card bg-white p-5"><h2 className="serif text-[22px] mb-2">Communities</h2>{clusters?.map(c => <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-2 border-t border-[var(--line)] text-[13px]"><span className="font-medium">{c.id} · {c.city}</span> <span className="text-[var(--ink-3)]">{Number(c.score).toFixed(1)} · {money(c.dollars_at_risk)}</span><div className="text-[12px] text-[var(--ink-2)] line-clamp-2">{c.summary}</div></Link>)}</div>
        <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-2">Revoked or excluded, still paid</h2><table className="table w-full"><thead><tr><th>provider</th><th>source</th><th>action</th><th>paid after</th></tr></thead><tbody>{d3?.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link-underline">{f.name || f.npi}</Link></td><td className="text-[11px]">{e.source}</td><td>{e.event_dt}</td><td>{money(e.paid_after)}</td></tr>; })}</tbody></table></div>
        <div className="card bg-white p-5 overflow-x-auto"><h2 className="serif text-[22px] mb-2">Impossible days</h2><table className="table w-full"><thead><tr><th>provider</th><th>month</th><th>label</th><th>h/day</th><th>paid</th></tr></thead><tbody>{d2rows.map(f => { const e = ev(f.evidence); return <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link-underline">{f.name || f.npi}</Link></td><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px]">{e.label}</td><td>{Number(f.value).toFixed(1)}</td><td>{money(e.paid)}</td></tr>; })}</tbody></table></div>
      </div>
    </div>
  );
}
