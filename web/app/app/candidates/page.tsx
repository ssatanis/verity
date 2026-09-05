import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { Tier } from "@/components/app/Tier";
import { withFallback } from "@/lib/fallback";
import { money, TIER_LABEL } from "@/lib/labels";
export const revalidate = 120;
export default async function Candidates({ searchParams }: { searchParams: Promise<{ state?: string; tier?: string; detector?: string; page?: string }> }) {
  const { state, tier, detector, page = "1" } = await searchParams; const sb = publicClient(); const p = Math.max(1, Number(page)); const per = 100;
  let q = sb.from("provider_risk").select("*").order("rank").range((p - 1) * per, p * per - 1);
  if (state) q = q.eq("state", state); if (tier) q = q.eq("tier", Number(tier)); if (detector) q = q.contains("detectors", [detector]);
  const data = await withFallback<any[]>("provider_risk", () => q, rows => rows.filter(r => (!state || r.state === state) && (!tier || String(r.tier) === tier) && (!detector || (r.detectors ?? []).includes(detector))).slice((p - 1) * per, p * per));
  const tc: Record<number, number> = {};
  try { const cs = await Promise.all([1, 2, 3, 4, 5].map(t => { let c = sb.from("provider_risk").select("npi", { count: "exact", head: true }).eq("tier", t); if (state) c = c.eq("state", state); if (detector) c = c.contains("detectors", [detector]); return c; })); cs.forEach((r, i) => { tc[i + 1] = r.count ?? 0; }); } catch {}
  const qs = (o: Record<string, string | undefined>) => "?" + Object.entries({ state, tier, detector, ...o }).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("&");
  const det: Record<string, string> = { D3: "Paid after a list action", D2: "Impossible hours", D1: "Provider networks" };
  return (
    <div>
      <div className="eyebrow">Providers</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">Every flagged provider, ranked.</h1>
      <p className="text-[14px] text-[var(--ink-2)] mt-4 max-w-3xl leading-6">One row per provider. The tier says what the public record can prove; the score, out of 100, rises when independent detectors agree. Dollars at stake come from the strongest finding, never a sum. Every row is a candidate for a records review, not a finding. Use the search box above to look up any provider in the country.</p>
      <div className="flex flex-wrap gap-2 mt-6 text-[12px] items-center">
        <Link href="/app/candidates" className={`tag ${!tier ? "tag-ink" : ""}`}>All tiers</Link>
        {[1, 2, 3, 4, 5].map(t => <Link key={t} href={qs({ tier: String(t), page: undefined })} className={`tag ${tier === String(t) ? "tag-ink" : ""}`} title={TIER_LABEL[t]}>Tier {t} <span className="opacity-60">{(tc[t] ?? 0).toLocaleString()}</span></Link>)}
        <span className="mx-1 text-[var(--ink-3)]">,</span>
        {["D3", "D2", "D1"].map(d => <Link key={d} href={qs({ detector: d, page: undefined })} className={`tag ${detector === d ? "tag-accent" : ""}`}>{det[d]}</Link>)}
        {state && <Link href={qs({ state: undefined, page: undefined })} className="tag tag-accent">{state}, clear</Link>}
        <span className="mx-1 text-[var(--ink-3)]">,</span>
        <Link href="/app/flags?detector=D3" className="tag">Detail: paid after a list action</Link><Link href="/app/flags?detector=D2" className="tag">Detail: hours per day</Link>
      </div>
      <div className="text-[11.5px] text-[var(--ink-3)] mt-3">{tier ? TIER_LABEL[Number(tier)] : "Tiers: 1 on a public list and still paid; 2 more hours than a day holds across organizations; 3 part of a network that touches a public list; 4 network structure alone or hours beyond a day under one organization; 5 worth knowing."}</div>
      <div className="card mt-4 overflow-x-auto"><table className="table">
        <thead><tr><th>rank</th><th>tier</th><th>provider</th><th>state</th><th>score</th><th>at stake</th><th>why</th></tr></thead>
        <tbody>{data?.map(r => <tr key={r.npi}><td>{r.rank}</td><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.npi}, {r.entity_type === "2" ? "organization" : "individual"}{r.city ? `, ${r.city}` : ""}</div></td><td>{r.state}</td><td className="serif text-[18px]" style={{ color: "var(--blue)" }}>{Number(r.score).toFixed(0)}</td><td>{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)] max-w-[480px] leading-5">{String(r.reasons ?? "").split("; ").map((x: string, i: number) => <div key={i}>{x}</div>)}</td></tr>)}</tbody>
      </table></div>
      <div className="flex gap-3 mt-4 text-[12px]">{p > 1 && <Link href={qs({ page: String(p - 1) })} className="link">Previous</Link>}{(data?.length ?? 0) === per && <Link href={qs({ page: String(p + 1) })} className="link">Next</Link>}</div>
    </div>
  );
}
