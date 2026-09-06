import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { Tier } from "@/components/app/Tier";
import { Reasons } from "@/components/app/Reasons";
import { Filters, Pager } from "@/components/app/Filters";
import { withFallback } from "@/lib/fallback";
import { money, TIER_LABEL, titleCase } from "@/lib/labels";
export const revalidate = 120;
export default async function Candidates({ searchParams }: { searchParams: Promise<{ state?: string; tier?: string; detector?: string; page?: string }> }) {
  const { state, tier, detector, page = "1" } = await searchParams; const sb = publicClient(); const p = Math.max(1, Number(page) || 1); const per = 100;
  let q = sb.from("provider_risk").select("*").order("rank").range((p - 1) * per, p * per - 1);
  if (state) q = q.eq("state", state); if (tier) q = q.eq("tier", Number(tier)); if (detector) q = q.contains("detectors", JSON.stringify([detector]));
  const data = await withFallback<any[]>("provider_risk", () => q, rows => rows.filter(r => (!state || r.state === state) && (!tier || String(r.tier) === tier) && (!detector || (r.detectors ?? []).includes(detector))).slice((p - 1) * per, p * per));
  const tc: Record<number, number> = {};
  try { const cs = await Promise.all([1, 2, 3, 4, 5].map(t => { let c = sb.from("provider_risk").select("npi", { count: "exact", head: true }).eq("tier", t); if (state) c = c.eq("state", state); if (detector) c = c.contains("detectors", JSON.stringify([detector])); return c; })); cs.forEach((r, i) => { tc[i + 1] = r.count ?? 0; }); } catch {}
  const det: Record<string, string> = { D3: "Paid after a list action", D2: "Impossible hours", D1: "Provider networks", ENF: "Enforcement records" };
  const groups = [
    { name: "tier", chips: [{ key: "tier", label: "All tiers" }, ...[1, 2, 3, 4, 5].map(t => ({ key: "tier", value: String(t), label: `Tier ${t}`, count: tc[t] ?? 0, title: TIER_LABEL[t] }))] },
    { name: "detector", chips: [{ key: "detector", label: "All detectors" }, ...["D3", "D2", "D1", "ENF"].map(d => ({ key: "detector", value: d, label: det[d], accent: true }))] },
    ...(state ? [{ name: "state", chips: [{ key: "state", value: state, label: `${state}, clear`, accent: true }] }] : []),
  ];
  return (
    <div>
      <div className="eyebrow">Providers</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">Every flagged provider, ranked.</h1>
      <p className="text-[14px] text-[var(--ink-2)] mt-4 max-w-3xl leading-6">One row per provider. The tier says what the public record can prove; the score, out of 100, rises when independent detectors agree. Dollars at stake come from the strongest finding, never a sum. Every row is a candidate for a records review, not a finding. Use the search box above to look up any provider in the country.</p>
      <Filters groups={groups} query={{ state, tier, detector }} path="/app/candidates" resetTo="/app/candidates" note={tier ? TIER_LABEL[Number(tier)] : "Tiers: 1 on a public list and still paid; 2 more hours than a day holds across organizations; 3 part of a network that touches a public list; 4 network structure alone or hours beyond a day under one organization; 5 worth knowing."} />
      <div className="flex flex-wrap gap-2 mt-3 text-[12px]"><Link href="/app/flags?detector=D3" className="tag">Detail: paid after a list action</Link><Link href="/app/flags?detector=D2" className="tag">Detail: hours per day</Link></div>
      <div data-filtered className="is-settled">
        <div className="card mt-4 overflow-x-auto"><table className="table">
          <thead><tr><th>rank</th><th>tier</th><th>provider</th><th>state</th><th>score</th><th>at stake</th><th>why</th></tr></thead>
          <tbody className="rows-in">{data?.map(r => <tr key={r.npi}><td>{r.rank}</td><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.npi}, {r.entity_type === "2" ? "organization" : "individual"}{r.city ? `, ${titleCase(r.city)}` : ""}</div></td><td>{r.state}</td><td style={{ color: "var(--blue)" }}>{Number(r.score).toFixed(0)}</td><td>{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)] max-w-[480px] leading-5"><Reasons text={r.reasons} compact /></td></tr>)}</tbody>
        </table></div>
        {(data?.length ?? 0) === 0 && <div className="card-2 p-6 mt-4 text-[13px]">No provider matches these filters. Clear one of them, or use the search box above to look up a provider by name or NPI.</div>}
      </div>
      <Pager page={p} hasNext={(data?.length ?? 0) === per} query={{ state, tier, detector }} path="/app/candidates" />
    </div>
  );
}
