import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { withFallback } from "@/lib/fallback";
import { getRelease, sourceLabel, sourceShort, actionLabel, districtLabel, paragraphs, npiList } from "@/lib/news";
import { dateLong, money, titleCase } from "@/lib/labels";
import { Tier } from "@/components/app/Tier";
export const revalidate = 600;
export default async function Article({ params }: { params: Promise<{ id: string }> }) {
  const { id: raw } = await params; const id = decodeURIComponent(raw);
  const r = await getRelease(id);
  if (!r) return (
    <div>
      <Link href="/app/news" className="eyebrow">News</Link>
      <div className="card-2 p-6 text-[13px] mt-4">That release is not in the feed. It may not have been fetched yet, or it was judged unrelated to health care claims. <Link href="/app/news" className="link">See the latest releases.</Link></div>
    </div>);
  const npis = npiList(r.npis);
  // Verity's own rows for the providers the release names, so the reader can step straight into the evidence.
  const named = npis.length ? (await withFallback<any[]>("provider_risk", () => publicClient().from("provider_risk").select("npi,name,city,state,tier,tier_label,dollars_at_risk").in("npi", npis), rows => rows.filter((x: any) => npis.includes(x.npi)))) ?? [] : [];
  const other = npis.filter(n => !named.some((x: any) => x.npi === n));
  const paras = paragraphs(r.body);
  return (
    <article className="max-w-4xl">
      <Link href="/app/news" className="eyebrow">News</Link>
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--ink-3)] mt-3"><span className="tag">{sourceShort(r.source)}</span>{r.action_type ? <span className="tag tag-accent">{actionLabel(r.action_type)}</span> : null}<span>{dateLong(r.published)}</span>{r.state ? <span>{r.state}</span> : null}</div>
      <h1 className="display serif text-[32px] md:text-[42px] leading-[1.08] mt-3">{r.title}</h1>
      <p className="text-[13px] text-[var(--ink-3)] mt-3">{sourceLabel(r.source)}{r.district ? `, ${districtLabel(r.district)}` : ""}. Published {dateLong(r.published)}{r.action_date && r.action_date !== r.published ? `; the action is dated ${dateLong(r.action_date)}` : ""}.</p>
      {r.image_url ? <img src={r.image_url} alt="" className="mt-6 w-full" /> : null}
      {r.scheme ? <div className="card-2 p-5 mt-6" style={{ borderLeft: "3px solid var(--blue)" }}><div className="eyebrow mb-1">What the release says</div><p className="text-[15px] leading-7">{r.scheme}</p>
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-[12px] text-[var(--ink-2)] mt-3">{r.programs ? <span><b>Programs</b> {String(r.programs).replace(/,/g, ", ")}</span> : null}{r.dollars_alleged ? <span><b>Alleged</b> {money(r.dollars_alleged)}</span> : null}{r.dollars_ordered ? <span><b>Ordered</b> {money(r.dollars_ordered)}</span> : null}</div></div> : null}
      {(named.length || other.length) ? <div className="card p-5 mt-6"><h2 className="serif text-[22px] mb-2">Providers named in this release</h2>
        <p className="text-[12px] text-[var(--ink-3)] mb-3">Matched to the national provider registry by name, place and provider type at high confidence only. Each opens the provider's own record.</p>
        {named.map((x: any) => <Link key={x.npi} href={`/app/providers/${x.npi}`} className="flex items-center gap-3 py-2 rule text-[13px]"><Tier n={x.tier} /><span className="link">{x.name || x.npi}</span><span className="text-[var(--ink-3)]">{x.city ? `${titleCase(x.city)}, ` : ""}{x.state}</span><span className="ml-auto text-[12px]">{money(x.dollars_at_risk)}</span></Link>)}
        {other.map(n => <Link key={n} href={`/app/providers/${n}`} className="flex items-center gap-3 py-2 rule text-[13px]"><span className="link">NPI {n}</span><span className="text-[var(--ink-3)]">no indicators in Verity</span></Link>)}
      </div> : null}
      <div className="mt-8"><div className="eyebrow mb-3">The release, as published</div>
        {paras.length ? <div className="text-[15px] leading-7 space-y-4" style={{ color: "var(--ink)" }}>{paras.map((t, i) => <p key={i}>{t}</p>)}</div>
          : <p className="text-[13px] text-[var(--ink-3)]">The text of this release is not stored here. Read it at the source below.</p>}
      </div>
      <div className="mt-8 pt-5 rule flex flex-wrap items-center gap-3">
        <a href={r.url} target="_blank" rel="noopener noreferrer" className="btn btn-arrow">Read the original at {r.source === "DOJ" ? "justice.gov" : r.source === "OIG" ? "oig.hhs.gov" : "the source"}<span className="btn-arrow-glyph" aria-hidden>&rarr;</span></a>
        <span className="text-[11px] text-[var(--ink-3)]">A United States government work, reproduced here so it can be read beside the evidence. Verity adds nothing to it.</span>
      </div>
    </article>
  );
}
