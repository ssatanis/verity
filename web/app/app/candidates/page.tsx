import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
import { Tier } from "@/components/app/Tier";
import { withFallback } from "@/lib/fallback";
export const revalidate = 120;
export default async function Candidates({ searchParams }: { searchParams: Promise<{ state?: string; tier?: string; detector?: string; page?: string }> }) {
  const { state, tier, detector, page = "1" } = await searchParams; const sb = publicClient(); const p = Math.max(1, Number(page)); const per = 100;
  let q = sb.from("provider_risk").select("*").order("rank").range((p - 1) * per, p * per - 1);
  if (state) q = q.eq("state", state); if (tier) q = q.eq("tier", Number(tier)); if (detector) q = q.contains("detectors", [detector]);
  const data = await withFallback<any[]>("provider_risk", () => q, rows => rows.filter(r => (!state || r.state === state) && (!tier || String(r.tier) === tier) && (!detector || (r.detectors ?? []).includes(detector))).slice((p - 1) * per, p * per));
  const tiers = await withFallback<any[]>("provider_risk", () => sb.from("provider_risk").select("tier").limit(20000));
  const tc = (tiers ?? []).reduce((a: any, r: any) => ((a[r.tier] = (a[r.tier] || 0) + 1), a), {});
  const qs = (o: Record<string, string | undefined>) => "?" + Object.entries({ state, tier, detector, ...o }).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("&");
  return (
    <div>
      <div className="eyebrow">Referral candidates</div>
      <h1 className="display serif text-[54px] mt-2">One row per provider, ranked by what the record can prove.</h1>
      <p className="text-[13.5px] text-[var(--ink-2)] mt-4 max-w-3xl leading-6">Tier is the evidence hierarchy; score adds a bonus for every strong finding that reached the provider independently (a tier A list action, concurrent impossible volume, or a ranked community) and a bounded dollar term. Dollars at risk is the figure from the detector that set the tier, never a sum and never borrowed from a weaker indicator. Every row is a candidate for records review, not a finding.</p>
      <div className="flex flex-wrap gap-2 mt-6 text-[12px] items-center">
        <Link href="/app/candidates" className={`tag ${!tier ? "tag-ink" : ""}`}>All tiers</Link>
        {[1, 2, 3, 4, 5].map(t => <Link key={t} href={qs({ tier: String(t), page: undefined })} className={`tag ${tier === String(t) ? "tag-ink" : ""}`}>Tier {t} <span className="opacity-60">{tc[t] ?? 0}</span></Link>)}
        <span className="mx-2 text-[var(--ink-3)]">·</span>
        {["D3", "D2", "D1"].map(d => <Link key={d} href={qs({ detector: d, page: undefined })} className={`tag ${detector === d ? "tag-accent" : ""}`}>{d}</Link>)}
        {state && <span className="tag tag-accent">{state}</span>}
      </div>
      <div className="card mt-6 overflow-x-auto"><table className="table">
        <thead><tr><th>rank</th><th>tier</th><th>provider</th><th>state</th><th>detectors</th><th>score</th><th>$ at risk</th><th>reasons</th></tr></thead>
        <tbody>{data?.map(r => <tr key={r.npi}><td>{r.rank}</td><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.npi} · {r.entity_type === "2" ? "organisation" : "individual"} · {r.city}</div></td><td>{r.state}</td><td>{(r.detectors as string[])?.join(" ")}</td><td>{Number(r.score).toFixed(0)}</td><td>{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)] max-w-[460px]">{r.reasons}</td></tr>)}</tbody>
      </table></div>
      <div className="flex gap-3 mt-4 text-[12px]">{p > 1 && <Link href={qs({ page: String(p - 1) })} className="link">Previous</Link>}{(data?.length ?? 0) === per && <Link href={qs({ page: String(p + 1) })} className="link">Next</Link>}</div>
    </div>
  );
}
