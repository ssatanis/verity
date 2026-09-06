import Link from "next/link";
import { publicClient } from "@/lib/supabase";
import { money, sourceName, labelName, idMatchName } from "@/lib/labels";
import { Filters } from "@/components/app/Filters";
export const revalidate = 120;
const ev = (x: any) => (typeof x === "string" ? JSON.parse(x) : x) ?? {};
export default async function Flags({ searchParams }: { searchParams: Promise<{ detector?: string; state?: string; tier?: string }> }) {
  const { detector = "D3", state, tier = "A" } = await searchParams; const sb = publicClient();
  let q = sb.from("flags").select("*").eq("detector", detector).order("score", { ascending: false }).limit(300);
  if (state) q = q.eq("state", state); if (tier !== "all") q = q.eq("tier", tier);
  const [{ data }, { data: summ }] = await Promise.all([q, sb.from("summary").select("value").eq("key", "d3_summary").maybeSingle()]);
  const byNpi = new Map<string, any>(); for (const f of data ?? []) if (!byNpi.has(f.npi)) byNpi.set(f.npi, f);
  const rows = [...byNpi.values()];
  const S = (summ?.value as any) ?? {}; const idTiers: any[] = S.id_match_headline ?? []; const fileDates: any[] = S.file_dates ?? [];
  const idLabel = (k: string) => idMatchName(k);
  return (
    <div>
      <div className="eyebrow">Providers, detail view</div>
      <h1 className="display serif text-[54px] mt-2">{detector === "D3" ? "Paid after a list action" : "More hours than a day holds"}</h1>
      <p className="text-[13.5px] text-[var(--ink-2)] mt-4 mb-5 max-w-3xl leading-6">{detector === "D3" ? "Providers on a Medicare revocation, OIG exclusion, SAM.gov or state exclusion list, or named in a Department of Justice, HHS-OIG or state attorney general enforcement release, whom Medicaid kept paying after the action. Tier A means the reason for the action concerns integrity, the NPI passes its check digit, and the name on the list agrees with the national registry. The dollars are payments after an action that should have triggered a screening check, not a determination that they were improper." : "Clinicians whose Medicaid billing implies more hours of hands-on care than a day holds, organizations billed for more than 24 hours per patient per day, and providers over a state's own daily cap. Tier A needs the hours to come from three or more billing organizations in the same month, a per-patient breach, or a cap breach. Hours beyond a day under a single organization are tier B, because several states let clinics bill under a supervising clinician's NPI."}</p>
      <Filters query={{ detector, state, tier: tier === "A" ? undefined : tier }} path="/app/flags" resetTo="/app/flags?detector=D3" groups={[
        { name: "detector", chips: [["D3", "Paid after a list action"], ["D2", "Hours per day"]].map(([d, n]) => ({ key: "detector", value: d, label: n, required: true })) },
        { name: "tier", chips: [{ key: "tier", label: "Strongest tier only" }, { key: "tier", value: "all", label: "All tiers", accent: true, title: "Also show the tiers held back from the headline" }] },
        ...(state ? [{ name: "state", chips: [{ key: "state", value: state, label: `${state}, clear`, accent: true }] }] : []),
      ]} />
      <div className="mb-5" />
      {detector === "D3" && idTiers.length > 0 && <div className="grid md:grid-cols-[1fr_1fr] gap-6 mb-6">
        <div className="card p-5"><div className="eyebrow mb-2">How each provider was matched (tier A, paid after the action)</div><table className="table"><thead><tr><th>match</th><th>NPIs</th><th>$M after</th></tr></thead><tbody>{idTiers.map((r: any[]) => <tr key={r[0]}><td>{idLabel(r[0])}</td><td>{Number(r[1]).toLocaleString()}</td><td>{r[2]}</td></tr>)}</tbody></table><p className="text-[11px] text-[var(--ink-3)] mt-2">Every match here is by the NPI itself. List rows without an NPI are matched by name separately and never enter these figures.</p></div>
        <div className="card p-5"><div className="eyebrow mb-2">File dates</div><table className="table"><tbody>{fileDates.map((r: any[]) => <tr key={r[0]}><td className="text-[var(--ink-2)]">{r[0]}</td><td className="mono">{r[1]}</td></tr>)}</tbody></table><p className="text-[11px] text-[var(--ink-3)] mt-2">The headline counts months Medicaid actually paid after the action, not enrollment status, because enrollment files go stale.</p></div>
      </div>}
      <div data-filtered className="is-settled"><div className="card overflow-x-auto"><table className="table">
        {detector === "D3" ? <thead><tr><th>provider</th><th>state</th><th>list</th><th>identity check</th><th>action date</th><th>months paid after</th><th>paid after</th><th>tier</th></tr></thead>
          : <thead><tr><th>provider</th><th>state</th><th>peak month</th><th>what was found</th><th>hours per day</th><th>lower bound</th><th>billing organizations</th><th>paid that month</th></tr></thead>}
        <tbody className="rows-in">{rows.map(f => { const e = ev(f.evidence); return detector === "D3"
          ? <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link">{f.name || e.nppes_name || f.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{f.npi}, {f.entity_type === "2" ? "organization" : "individual"}</div></td><td>{f.state}</td><td className="text-[12px]">{sourceName(e.source)}<div className="text-[11px] text-[var(--ink-3)] max-w-[280px]">{String(e.reason ?? "").replace(/_/g, " ")}</div></td><td className="text-[11px]">{idMatchName(e.id_match)}</td><td>{e.event_dt}</td><td>{e.months_paid_after} <span className="text-[var(--ink-3)] text-[11px]">{e.first_month_after} to {e.last_month_after}</span></td><td>{money(e.paid_after)}</td><td>{f.tier}</td></tr>
          : <tr key={String(f.id)}><td><Link href={`/app/providers/${f.npi}`} className="link">{f.name || e.name || f.npi}</Link><div className="text-[11px] text-[var(--ink-3)]">{f.npi}, {e.entity_type === "2" ? "organization" : "individual"}, {e.taxonomy}</div></td><td>{f.state}</td><td>{String(f.month).slice(0, 7)}</td><td className="text-[11px] max-w-[220px]">{labelName(e.label)}</td><td>{Number(f.value).toFixed(1)}</td><td>{Number(e.hours_lb_per_day).toFixed(1)}</td><td>{e.n_billing_orgs}</td><td>{money(e.paid)}</td></tr>; })}</tbody>
      </table></div>
      {rows.length === 0 && <div className="card-2 p-6 mt-4 text-[13px]">Nothing matches these filters. Try the other detector, or turn on "all tiers".</div>}
      </div>
    </div>
  );
}
