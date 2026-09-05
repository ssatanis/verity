import Link from "next/link";
import { publicClient, money } from "@/lib/supabase";
import { Tier } from "@/components/app/Tier";
export const dynamic = "force-dynamic";
export default async function Search({ searchParams }: { searchParams: Promise<{ q?: string }> }) {
  const { q = "" } = await searchParams; const term = q.trim(); const sb = publicClient();
  const isNpi = /^\d{10}$/.test(term);
  const [{ data: risk }, { data: prov }, { data: cl }] = term ? await Promise.all([
    isNpi ? sb.from("provider_risk").select("*").eq("npi", term) : sb.from("provider_risk").select("*").ilike("name", `${term}%`).order("rank").limit(50),
    isNpi ? sb.from("providers").select("npi,name,city,state,entity_type,taxonomy").eq("npi", term) : sb.from("providers").select("npi,name,city,state,entity_type,taxonomy").ilike("name", `${term}%`).limit(50),
    sb.from("clusters").select("id,rank,city,state,n_providers,summary").ilike("summary", `%${term}%`).eq("eligible", true).order("rank").limit(10),
  ]) : [{ data: [] }, { data: [] }, { data: [] }] as any;
  const seen = new Set((risk ?? []).map((r: any) => r.npi)); const extra = (prov ?? []).filter((p: any) => !seen.has(p.npi));
  return (
    <div>
      <div className="eyebrow">Search</div>
      <h1 className="display serif text-[54px] mt-2">{term ? <>Results for <span style={{ color: "var(--accent)" }}>{term}</span></> : "Search by NPI or provider name"}</h1>
      <p className="text-[13px] text-[var(--ink-3)] mt-3">Exact NPI, or a name prefix. Names are matched as they appear in NPPES, so search the legal business name.</p>
      {(risk ?? []).length > 0 && <div className="card mt-6 overflow-x-auto"><table className="table"><thead><tr><th>tier</th><th>provider</th><th>state</th><th>detectors</th><th>$ at risk</th><th>reasons</th></tr></thead>
        <tbody>{(risk ?? []).map((r: any) => <tr key={r.npi}><td><Tier n={r.tier} /></td><td><Link href={`/app/providers/${r.npi}`} className="link">{r.name || r.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{r.npi}</div></td><td>{r.state}</td><td>{(r.detectors as string[])?.join(" ")}</td><td>{money(r.dollars_at_risk)}</td><td className="text-[12px] text-[var(--ink-2)]">{r.reasons}</td></tr>)}</tbody></table></div>}
      {extra.length > 0 && <div className="card mt-6 overflow-x-auto"><div className="eyebrow p-4 pb-0">Providers in the data without a referral tier</div><table className="table"><tbody>{extra.map((p: any) => <tr key={p.npi}><td><Link href={`/app/providers/${p.npi}`} className="link">{p.name}</Link></td><td>{p.npi}</td><td>{p.city}, {p.state}</td><td className="text-[var(--ink-3)]">{p.taxonomy}</td></tr>)}</tbody></table></div>}
      {(cl ?? []).length > 0 && <div className="card mt-6 p-5"><div className="eyebrow">Communities mentioning the term</div>{(cl ?? []).map((c: any) => <Link key={c.id} href={`/app/clusters/${c.id}`} className="block py-3 rule text-[13px]"><span className="serif text-[18px]">{c.id}</span> <span className="text-[var(--ink-3)]">rank {c.rank} · {c.city}</span><div className="text-[12px] text-[var(--ink-2)]">{c.summary}</div></Link>)}</div>}
      {term && !(risk ?? []).length && !extra.length && !(cl ?? []).length && <div className="card-2 p-6 mt-6 text-[13px]">Nothing matched. Providers only appear here once a detector or a community reached them, or when NPPES lists them under that legal name.</div>}
    </div>
  );
}
