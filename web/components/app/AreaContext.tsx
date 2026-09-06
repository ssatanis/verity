import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { withFallback } from "@/lib/fallback";
import { listReleases, sourceShort, actionLabel } from "@/lib/news";
import { money, titleCase, dateShort, TIER_LABEL } from "@/lib/labels";
import { Tier } from "./Tier";
import { Reasons } from "./Reasons";
// What surrounds a provider: the other providers with indicators in the same county, city or state, ranked, with the
// pattern that recurs among them; and the newest enforcement releases for the state. Shown on every provider page, and
// it is the whole story for a provider that carries no indicators of its own.
const DET: Record<string, string> = { D3: "paid after a public list action", D2: "more hours than a day holds", D1: "part of a provider network", ENF: "named in an enforcement record" };
export async function AreaContext({ npi, state, city, countyFips, countyName }: { npi: string; state?: string | null; city?: string | null; countyFips?: string | null; countyName?: string | null }) {
  if (!state) return null;
  const sb = publicClient();
  const scoped = (q: any) => countyFips ? q.eq("county_fips", countyFips) : city ? q.eq("state", state).ilike("city", city) : q.eq("state", state);
  const pick = (rows: any[]) => rows.filter((r: any) => r.state === state && (!city || countyFips || String(r.city ?? "").toLowerCase() === String(city).toLowerCase()));
  let rows = (await withFallback<any[]>("provider_risk", () => scoped(sb.from("provider_risk").select("npi,name,city,state,tier,tier_label,detectors,score,dollars_at_risk,reasons,rank")).order("rank").limit(400), pick)) ?? [];
  let scope = countyFips && countyName ? `${titleCase(countyName).replace(/\s+County$/i, "")} County, ${state}` : city ? `${titleCase(city)}, ${state}` : state;
  // A city with nothing to show widens to the state, so the section always says something true about the area.
  if (rows.length < 3 && (countyFips || city)) {
    rows = (await withFallback<any[]>("provider_risk", () => sb.from("provider_risk").select("npi,name,city,state,tier,tier_label,detectors,score,dollars_at_risk,reasons,rank").eq("state", state).order("rank").limit(400), r => r.filter((x: any) => x.state === state))) ?? [];
    scope = state;
  }
  rows = rows.filter((r: any) => r.npi !== npi);
  const releases = await listReleases({ state, limit: 5 });
  if (!rows.length && !releases.length) return null;
  const causes: Record<string, number> = {}; let dollars = 0; const tiers: Record<number, number> = {};
  for (const r of rows) {
    const ds: string[] = typeof r.detectors === "string" ? (() => { try { return JSON.parse(r.detectors); } catch { return []; } })() : (r.detectors ?? []);
    for (const d of ds) causes[d] = (causes[d] ?? 0) + 1;
    dollars += Number(r.dollars_at_risk ?? 0); tiers[r.tier] = (tiers[r.tier] ?? 0) + 1;
  }
  const ranked = Object.entries(causes).sort((a, b) => b[1] - a[1]);
  const top = ranked[0]; const second = ranked[1];
  return (
    <>
      {rows.length > 0 && <div className="card p-5">
        <h2 className="serif text-[24px] mb-1">In this area</h2>
        <p className="text-[13px] leading-6 mt-2" style={{ color: "var(--ink-2)" }}>
          <b>{rows.length.toLocaleString()}</b> provider{rows.length === 1 ? "" : "s"} in <b>{scope}</b> carr{rows.length === 1 ? "ies" : "y"} an indicator in the public record, with <b>{money(dollars)}</b> at stake between them.
          {top ? <> The most common is <b>{DET[top[0]] ?? top[0]}</b>, on {top[1]} of them{second ? <>, followed by {DET[second[0]] ?? second[0]} on {second[1]}</> : null}.</> : null}
          {tiers[1] ? <> {tiers[1]} {tiers[1] === 1 ? "is" : "are"} tier 1: {TIER_LABEL[1].toLowerCase()}.</> : null}
        </p>
        <div className="overflow-x-auto mt-3"><table className="table"><thead><tr><th>tier</th><th>provider</th><th>at stake</th><th>why</th></tr></thead>
          <tbody>{rows.slice(0, 8).map((r: any) => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.city ? `${titleCase(r.city)}, ` : ""}{r.state}, ranked {r.rank}</div></td><td className="whitespace-nowrap">{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)] max-w-[420px] leading-5"><Reasons text={r.reasons} compact max={2} /></td></tr>)}</tbody></table></div>
        {rows.length > 8 && <Link href={`/app/candidates?state=${state}`} className="link text-[12px] mt-3 inline-block">All {rows.length.toLocaleString()} in {state}</Link>}
      </div>}
      {releases.length > 0 && <div className="card p-5">
        <div className="flex items-center justify-between gap-3"><h2 className="serif text-[24px]">Recent enforcement in {state}</h2><Link href={`/app/news?state=${state}`} className="link text-[12px]">All releases</Link></div>
        <p className="text-[12px] text-[var(--ink-3)] mt-1 mb-2">Department of Justice and HHS-OIG releases for this state, newest first. Each opens in a new tab.</p>
        {releases.map(r => <Link key={r.id} href={`/app/news/${encodeURIComponent(r.id)}`} target="_blank" rel="noopener" className="block py-3 rule">
          <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--ink-3)]"><span className="tag">{sourceShort(r.source)}</span>{r.action_type ? <span>{actionLabel(r.action_type)}</span> : null}<span>{dateShort(r.published)}</span></div>
          <div className="serif text-[17px] leading-snug mt-1" style={{ color: "var(--blue)" }}>{r.title}</div>
          {r.scheme ? <div className="text-[12px] text-[var(--ink-2)] mt-1 line-clamp-2">{r.scheme}</div> : null}
        </Link>)}
      </div>}
    </>
  );
}
