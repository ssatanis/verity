import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { Tier } from "@/components/app/Tier";
import { Reasons } from "@/components/app/Reasons";
import { SearchBox } from "@/components/app/SearchBox";
import { money, titleCase } from "@/lib/labels";
import { nppesSearchIn, nppesLookup } from "@/lib/nppes";
import { parseQuery } from "@/lib/searchparse";
export const dynamic = "force-dynamic";
export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams; const term = q.trim(); const sb = publicClient();
  const P = parseQuery(term); const isNpi = !!P.npi; const nm = P.name;
  const filt = (q: any) => { if (P.state) q = q.eq("state", P.state); if (P.city) q = q.ilike("city", `${P.city}%`); return q; };
  const [{ data: risk0 }, { data: prov }, { data: cl }, { data: fz }] = term ? await Promise.all([
    isNpi ? sb.from("provider_risk").select("*").eq("npi", P.npi!) : filt(sb.from("provider_risk").select("*").ilike("name", `${nm}%`)).order("rank").limit(50),
    isNpi ? sb.from("providers").select("npi,name,city,state,entity_type,taxonomy").eq("npi", P.npi!) : filt(sb.from("providers").select("npi,name,city,state,entity_type,taxonomy").ilike("name", `${nm}%`)).limit(50),
    sb.from("clusters").select("id,rank,city,state,n_providers,summary").ilike("summary", `%${nm || term}%`).eq("eligible", true).order("rank").limit(10),
    isNpi || nm.length < 3 ? Promise.resolve({ data: [] as any[] }) : sb.rpc("search_providers", { q: nm, st: P.state ?? null, ct: P.city ?? null, lim: 20 }),
  ]) : [{ data: [] }, { data: [] }, { data: [] }, { data: [] }] as any;
  const risk = [...(risk0 ?? [])]; const seenR = new Set(risk.map((r: any) => r.npi));
  const fuzzy = ((fz ?? []) as any[]).filter(r => !seenR.has(r.npi));
  const seen = new Set((risk ?? []).map((r: any) => r.npi)); const extra = (prov ?? []).filter((p: any) => !seen.has(p.npi)); for (const p of extra) seen.add(p.npi);
  let registry: any[] = [];
  if (term) { try { const rs = P.npi ? [await nppesLookup(P.npi)].filter(Boolean) as any[] : await nppesSearchIn(nm, P.city, P.state, 25); registry = rs.filter((h: any) => !seen.has(h.npi) && !fuzzy.some(f => f.npi === h.npi)); } catch {} }
  return (
    <div>
      <div className="eyebrow">Search</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">{term ? <>Results for <span style={{ color: "var(--blue)" }}>{P.npi ?? nm}</span>{P.city || P.state ? <span className="text-[var(--ink-3)]"> in {[P.city, P.state].filter(Boolean).join(", ")}</span> : null}</> : "Look up any provider in the country"}</h1>
      <div className="mt-5 max-w-2xl"><SearchBox large autoFocus={!term} /></div>
      <p className="text-[12.5px] text-[var(--ink-3)] mt-3">Type a 10-digit NPI, a name, or a name with a city and state, for example "mayo clinic rochester mn". Misspellings and partial names are matched by similarity; suggestions appear as you type.</p>
      {(risk ?? []).length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">Providers with indicators</div><table className="table"><thead><tr><th>tier</th><th>provider</th><th>state</th><th>at stake</th><th>why</th></tr></thead>
        <tbody>{(risk ?? []).map((r: any) => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.npi}</div></td><td>{r.state}</td><td>{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)] max-w-[420px] leading-5"><Reasons text={r.reasons} compact /></td></tr>)}</tbody></table></div>}
      {fuzzy.length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">Close matches by similarity</div><table className="table"><tbody>{fuzzy.map((p: any) => <tr key={p.npi}><td>{p.tier ? <Tier n={p.tier} /> : null}</td><td><Link href={`/app/providers/${p.npi}`} className="link">{p.name}</Link></td><td>{p.npi}</td><td>{titleCase(p.city)}, {p.state}</td><td className="text-[var(--ink-3)]">{Math.round(Number(p.sim) * 100)}% similar</td></tr>)}</tbody></table></div>}
      {extra.length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">Providers in the data without indicators</div><table className="table"><tbody>{extra.map((p: any) => <tr key={p.npi}><td><Link href={`/app/providers/${p.npi}`} className="link">{p.name}</Link></td><td>{p.npi}</td><td>{titleCase(p.city)}, {p.state}</td><td className="text-[var(--ink-3)]">{p.taxonomy}</td></tr>)}</tbody></table></div>}
      {registry.length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">From the CMS national provider registry</div><table className="table"><tbody>{registry.map((p: any) => <tr key={p.npi}><td><Link href={`/app/providers/${p.npi}`} className="link">{p.name}</Link></td><td>{p.npi}</td><td>{p.city ? `${titleCase(p.city)}, ` : ""}{p.state}</td><td className="text-[var(--ink-3)]">{p.entity_type === "2" ? "organization" : "individual"}{p.taxonomies?.[0]?.desc ? `, ${p.taxonomies[0].desc}` : ""}</td></tr>)}</tbody></table></div>}
      {(cl ?? []).length > 0 && <div className="card mt-6 p-5"><div className="eyebrow">Networks mentioning the term</div>{(cl ?? []).map((c: any) => <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 rule text-[13px]"><span className="serif text-[18px]">{c.summary}</span> <span className="text-[var(--ink-3)]">{c.id}, ranked {c.rank}</span></Link>)}</div>}
      {term && !(risk ?? []).length && !extra.length && !registry.length && !fuzzy.length && !(cl ?? []).length && <div className="card-2 p-6 mt-6 text-[13px]">Nothing matched. Try the 10-digit NPI or the legal business name as it appears in the national registry.</div>}
    </div>
  );
}
