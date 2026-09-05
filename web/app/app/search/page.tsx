import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { Tier } from "@/components/app/Tier";
import { SearchBox } from "@/components/app/SearchBox";
import { money } from "@/lib/labels";
export const dynamic = "force-dynamic";
const API = process.env.VERITY_API_URL ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams; const term = q.trim(); const sb = publicClient();
  const isNpi = /^\d{10}$/.test(term);
  const [{ data: risk }, { data: prov }, { data: cl }] = term ? await Promise.all([
    isNpi ? sb.from("provider_risk").select("*").eq("npi", term) : sb.from("provider_risk").select("*").ilike("name", `${term}%`).order("rank").limit(50),
    isNpi ? sb.from("providers").select("npi,name,city,state,entity_type,taxonomy").eq("npi", term) : sb.from("providers").select("npi,name,city,state,entity_type,taxonomy").ilike("name", `${term}%`).limit(50),
    sb.from("clusters").select("id,rank,city,state,n_providers,summary").ilike("summary", `%${term}%`).eq("eligible", true).order("rank").limit(10),
  ]) : [{ data: [] }, { data: [] }, { data: [] }] as any;
  const seen = new Set((risk ?? []).map((r: any) => r.npi)); const extra = (prov ?? []).filter((p: any) => !seen.has(p.npi)); for (const p of extra) seen.add(p.npi);
  let registry: any[] = [];
  if (term && API && seen.size < 20) { try { const r = await fetch(`${API}/search?q=${encodeURIComponent(term)}&limit=25`, { signal: AbortSignal.timeout(5000) }); if (r.ok) registry = ((await r.json()).hits ?? []).filter((h: any) => !seen.has(h.npi)); } catch {} }
  return (
    <div>
      <div className="eyebrow">Search</div>
      <h1 className="display serif text-[40px] md:text-[54px] mt-2">{term ? <>Results for <span style={{ color: "var(--blue)" }}>{term}</span></> : "Look up any provider in the country"}</h1>
      <div className="mt-5 max-w-2xl"><SearchBox large autoFocus={!term} /></div>
      <p className="text-[12.5px] text-[var(--ink-3)] mt-3">Type a 10-digit NPI or the start of a name. Suggestions appear as you type; press Enter to see everything.</p>
      {(risk ?? []).length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">Providers with indicators</div><table className="table"><thead><tr><th>tier</th><th>provider</th><th>state</th><th>at stake</th><th>why</th></tr></thead>
        <tbody>{(risk ?? []).map((r: any) => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.npi}</div></td><td>{r.state}</td><td>{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)]">{r.reasons}</td></tr>)}</tbody></table></div>}
      {extra.length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">Providers in the data without indicators</div><table className="table"><tbody>{extra.map((p: any) => <tr key={p.npi}><td><Link href={`/app/providers/${p.npi}`} className="link">{p.name}</Link></td><td>{p.npi}</td><td>{p.city}, {p.state}</td><td className="text-[var(--ink-3)]">{p.taxonomy}</td></tr>)}</tbody></table></div>}
      {registry.length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">From the national provider registry</div><table className="table"><tbody>{registry.map((p: any) => <tr key={p.npi}><td><Link href={`/app/providers/${p.npi}`} className="link">{p.name}</Link></td><td>{p.npi}</td><td>{p.city ? `${p.city}, ` : ""}{p.state}</td><td className="text-[var(--ink-3)]">{p.entity_type === "2" ? "organisation" : "individual"}</td></tr>)}</tbody></table></div>}
      {(cl ?? []).length > 0 && <div className="card mt-6 p-5"><div className="eyebrow">Networks mentioning the term</div>{(cl ?? []).map((c: any) => <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 rule text-[13px]"><span className="serif text-[18px]">{c.summary}</span> <span className="text-[var(--ink-3)]">{c.id}, ranked {c.rank}</span></Link>)}</div>}
      {term && !(risk ?? []).length && !extra.length && !registry.length && !(cl ?? []).length && <div className="card-2 p-6 mt-6 text-[13px]">Nothing matched. Try the 10-digit NPI or the legal business name as it appears in the national registry.</div>}
    </div>
  );
}
