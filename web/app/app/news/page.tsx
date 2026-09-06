import Link from "next/link";
import { Filters, Pager } from "@/components/app/Filters";
import { listReleases, releaseStates, sourceShort, actionLabel, districtLabel, npiList } from "@/lib/news";
import { dateLong, dateShort, money } from "@/lib/labels";
export const revalidate = 600;
export default async function News({ searchParams }: { searchParams: Promise<{ state?: string; q?: string; page?: string }> }) {
  const { state, q, page = "1" } = await searchParams; const p = Math.max(1, Number(page) || 1); const per = 40;
  const [rows, states] = await Promise.all([listReleases({ state, q, limit: per, offset: (p - 1) * per }), releaseStates()]);
  const latest = rows[0]?.published;
  return (
    <div>
      <div className="eyebrow">News</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">Enforcement, updated every day.</h1>
      <p className="text-[14px] text-[var(--ink-2)] mt-4 max-w-3xl leading-6">Every health care enforcement release from the Department of Justice and the HHS Office of Inspector General, including state attorneys general and Medicaid fraud control units, fetched daily and read into the same schema the detectors use. Each one links to the providers it names when the match is certain{latest ? `, and the newest is dated ${dateLong(latest)}` : ""}. These are public records of charges, pleas, sentences and settlements, not findings by Verity.</p>
      <Filters query={{ state, q }} path="/app/news" resetTo="/app/news" groups={[
        { name: "state", chips: [{ key: "state", label: "All states" }, ...states.slice(0, 14).map(([s, n]) => ({ key: "state", value: s, label: s, count: n }))] },
      ]} />
      <form action="/app/news" className="flex gap-2 mt-4 max-w-xl">{state && <input type="hidden" name="state" value={state} />}<input name="q" defaultValue={q ?? ""} placeholder="Search releases, for example hospice, laboratory, kickback" className="flex-1" aria-label="Search releases" /><button className="btn" style={{ padding: "8px 14px" }}>Search</button>{q && <Link href={state ? `/app/news?state=${state}` : "/app/news"} className="btn btn-ghost" style={{ padding: "8px 14px" }}>Clear</Link>}</form>
      <div data-filtered className="is-settled mt-6">
        <div className="card rows-in">
          {rows.map(r => { const npis = npiList(r.npis); return (
            <Link key={r.id} href={`/app/news/${encodeURIComponent(r.id)}`} className="block p-5 rule first:border-t-0 hover:bg-[var(--paper-2)] transition-colors">
              <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--ink-3)]"><span className="tag">{sourceShort(r.source)}</span>{r.action_type ? <span className="tag tag-accent">{actionLabel(r.action_type)}</span> : null}<span>{dateShort(r.published)}</span>{r.state ? <span>{r.state}</span> : null}{r.district ? <span className="hidden sm:inline">{districtLabel(r.district)}</span> : null}</div>
              <h2 className="serif text-[22px] leading-tight mt-2" style={{ color: "var(--blue)" }}>{r.title}</h2>
              {r.scheme ? <p className="text-[13px] text-[var(--ink-2)] leading-6 mt-2 max-w-3xl">{r.scheme}</p> : null}
              <div className="flex flex-wrap gap-x-5 gap-y-1 text-[11.5px] text-[var(--ink-3)] mt-2">
                {r.dollars_alleged ? <span>{money(r.dollars_alleged)} alleged</span> : null}{r.dollars_ordered ? <span>{money(r.dollars_ordered)} ordered</span> : null}{r.programs ? <span>{String(r.programs).replace(/,/g, ", ")}</span> : null}{npis.length ? <span style={{ color: "var(--blue)" }}>{npis.length} provider{npis.length === 1 ? "" : "s"} in Verity</span> : null}
              </div>
            </Link>); })}
          {rows.length === 0 && <div className="card-2 p-6 text-[13px]">No release matches. Clear the state or try another word.</div>}
        </div>
      </div>
      <Pager page={p} hasNext={rows.length === per} query={{ state, q }} path="/app/news" />
    </div>
  );
}
