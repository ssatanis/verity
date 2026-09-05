import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { publicClient } from "@/lib/supabase";
import { Eq, M } from "@/components/app/Math";
import { Bars } from "@/components/app/Bars";
import { idMatchName, labelName, money } from "@/lib/labels";
export const revalidate = 300;
const num = (v: any) => Number(v ?? 0).toLocaleString("en-US");
const clean = (s: string) => s.replace(/—/g, ", ").replace(/–/g, " to ").replace(/`([^`]+)`/g, "$1").replace(/\b(docs|ingest|detectors|scripts|api|data)\/[\w./-]+/g, "the pipeline code").replace(/\b([a-z0-9]+_){1,}[a-z0-9]+\b/g, m => m.replace(/_/g, " "));
export default async function Methods() {
  const sb = publicClient();
  const [{ data }, { data: trends }] = await Promise.all([sb.from("summary").select("key,value"), sb.from("procedure_trends").select("*").gte("n_all", 200).order("lift", { ascending: false }).limit(15)]);
  const S: Record<string, any> = Object.fromEntries((data ?? []).map((r: any) => [r.key, r.value]));
  const t = S.totals ?? {}; const d1 = S.d1_summary ?? {}; const d2 = S.d2_summary ?? {}; const d3 = S.d3_summary ?? {};
  const prec: [string, number][] = Object.entries(d1.precision ?? {}).map(([k, v]) => [`top ${k}`, Number(v)]);
  const pv: Record<string, number> = d1.precision_pvalues ?? {};
  const d2tiers: [string, number, string][] = (d2.tiers ?? []).map((r: any[]) => [`tier ${r[0]}`, Number(r[2]), `${num(r[1])} months`]);
  const d2labels: [string, number][] = (d2.labels ?? []).slice(0, 6).map((r: any[]) => [labelName(r[0]).split(",")[0].slice(0, 34), Number(r[2])]);
  const denom: any[] = d2.denominator ?? [];
  const idm: any[] = d3.id_match ?? []; const fileDates: any[] = d3.file_dates ?? []; const byYear: [string, number][] = (d3.by_year ?? []).filter((r: any[]) => Number(r[0]) >= 2015).map((r: any[]) => [r[0], Number(r[2])]);
  const h = d3.headline?.[0] ?? [];
  const md = clean(String(S.methods_md?.text ?? ""));
  return (
    <div className="max-w-4xl">
      <div className="eyebrow">Methods</div>
      <h1 className="display serif text-[34px] md:text-[44px] mt-2">How Verity makes its numbers.</h1>
      <p className="text-[15px] text-[var(--ink-2)] mt-4 leading-7">Everything on this site comes from public records. This page explains, in plain terms, what each detector looks for, how a provider ends up with a tier and a score, and how much each result can be trusted. The full technical write-up is at the bottom.</p>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>The data</h2>
        <p className="text-[14px] leading-7 mt-3">Fourteen public datasets: Medicaid provider spending and enrollment for every state ({num(t.spend_rows)} spending rows, 2018 to 2024), Medicare enrollments and their owners, the national provider registry ({num(t.nppes)} providers), the OIG exclusion list, SAM.gov exclusions, Medicare revocations, market saturation, quality data, Census geography, state exclusion lists and state fee schedules. Every provider number is validated with its check digit, addresses are standardized, and names are parsed before anything is joined.</p>
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>Detector 1: provider networks</h2>
        <p className="text-[14px] leading-7 mt-3">Verity builds a graph in which hospices, home health agencies and nursing facilities are connected to the people and companies that own them, the buildings and suites they occupy, their phone numbers, their officials, and the addresses of companies already revoked or excluded. Owner records that refer to the same person are merged with a probabilistic matching model; addresses that host many unrelated providers, such as registered agents, are held out so they do not glue strangers together. Connected groups become networks.</p>
        <p className="text-[14px] leading-7 mt-3">Each network is measured on features such as how many of its companies were incorporated within one 90-day window, how many share a suite or phone, how many owners sit on three or more of them, and whether any member touches a public list. Each feature is compared with every other network using a robust z-score, which asks how far a value sits from the typical network in units that outliers cannot distort:</p>
        <Eq>{String.raw`z_i = \frac{x_i - \operatorname{median}(x)}{1.4826 \cdot \operatorname{MAD}(x)}`}</Eq>
        <p className="text-[14px] leading-7">The score adds structure, list and context terms. A network is ranked only when it has three or more separate companies, at least one formed since 2021, two independent kinds of evidence, and fewer than half its members in a known chain. On the site the score is shown on a 0 to 100 scale within the ranked networks.</p>
        <div className="card p-5 mt-5"><div className="eyebrow mb-3">How often a highly ranked network already touches a public list</div>
          <Bars rows={prec.map(([k, v]) => [k, Math.round(v * 100), ""])} unit="%" max={100} />
          <p className="text-[12px] text-[var(--ink-3)] mt-3 leading-5">Precision at the top of the ranking, using the structure score only and excluding chains, against public labels (revocations, exclusions, state terminations). The base rate across all networks is {Math.round(Number(d1.base_rate ?? 0) * 100)}%. The p-value for the top 50 is {Number(pv["50"] ?? 0).toExponential(1)} and for the top 250 is {Number(pv["250"] ?? 0).toExponential(1)}; the top 10 alone is not statistically distinguishable from chance ({Number(pv["10"] ?? 0).toFixed(2)}). The labels are incomplete and partly overlap the score, so these figures are a sanity check, not a measured accuracy.</p></div>
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>Detector 2: more hours than a day holds</h2>
        <p className="text-[14px] leading-7 mt-3">Medicaid pays for many services by the unit of time. Verity converts each provider's monthly billing on those codes into hours of hands-on care three ways. The lower bound needs no price at all: every claim line is worth at least one unit, so</p>
        <Eq>{String.raw`\text{hours}_{\text{lower}} = \frac{\sum_{\text{codes}} \text{lines}_c \cdot \text{minutes}_c}{60}`}</Eq>
        <p className="text-[14px] leading-7">The point estimate divides dollars by a unit price, using the published state rate where one exists and a conservative estimate elsewhere. The conservative figure uses 1.5 times that price, which lowers the hours. A month is flagged only when the conservative hours per calendar day exceed 24:</p>
        <Eq>{String.raw`\frac{\text{hours}_{\text{conservative}}}{\text{days in month}} > 24`}</Eq>
        <p className="text-[14px] leading-7">Only codes that a clinician must deliver in person count toward an individual's hours; aide, technician and agency codes are billed under a supervising provider by design and are reported separately. Because several states let clinics bill under a supervising clinician, hours beyond a day from a single organization are tier B. Tier A needs the hours to come from three or more small billing organizations in the same month with at most 500 patients, more than 24 hours per patient per day, or a breach of a state's own daily cap. A rendering NPI with hundreds of patients a month, or whose billing organizations each carry dozens of rendering clinicians, is a medical director or supervising clinician on the claims: a supervisory umbrella, kept out of tier 2 however many organizations bill it.</p>
        <div className="grid md:grid-cols-2 gap-5 mt-5">
          <div className="card p-5"><div className="eyebrow mb-3">Dollars in flagged months by tier, $ millions</div><Bars rows={d2tiers} /><p className="text-[12px] text-[var(--ink-3)] mt-3">Tier C is informational (over 12 hours a day, or agency volume under one clinician) and stays out of the referral queue.</p></div>
          <div className="card p-5"><div className="eyebrow mb-3">What was found, by number of providers</div><Bars rows={d2labels} /></div>
        </div>
        {denom.length > 0 && <div className="card p-5 mt-5"><div className="eyebrow mb-2">Calendar days or working days</div><table className="table"><thead><tr><th>denominator</th><th>providers over 24 hours a day</th><th>months</th></tr></thead><tbody>{denom.map((r: any[]) => <tr key={r[0]}><td>{r[0]}</td><td>{num(r[1])}</td><td>{num(r[2])}</td></tr>)}</tbody></table><p className="text-[12px] text-[var(--ink-3)] mt-2">Labels use calendar days, the more conservative choice. Dividing by working days roughly doubles the count, so both are shown.</p></div>}
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>Detector 3: paid after a list action</h2>
        <p className="text-[14px] leading-7 mt-3">A provider appears on a public list with an effective date: a Medicare revocation on integrity grounds, an OIG exclusion, a SAM.gov exclusion, or a state Medicaid exclusion. Verity then looks for Medicaid payments in the months strictly after that date and before any reinstatement or the end of the re-enrollment bar. {num(h[0])} providers are on such a list inside the data window; {num(h[1])} of them were paid afterwards, {money(Number(h[2]) * 1e6)} in total. Every match is by the NPI itself, and the name on the list must agree with the national registry; name conflicts are set aside.</p>
        <div className="grid md:grid-cols-2 gap-5 mt-5">
          <div className="card p-5"><div className="eyebrow mb-2">How the providers were matched</div><table className="table"><thead><tr><th>match</th><th>tier</th><th>providers</th><th>$ millions after</th></tr></thead><tbody>{idm.map((r: any[], i: number) => <tr key={i}><td>{idMatchName(r[0])}</td><td>{r[1]}</td><td>{num(r[2])}</td><td>{r[3]}</td></tr>)}</tbody></table></div>
          <div className="card p-5"><div className="eyebrow mb-3">$ millions paid after the action, by year of the action</div><Bars rows={byYear} /></div>
        </div>
        <div className="card p-5 mt-5"><div className="eyebrow mb-2">How current each file is</div><table className="table"><tbody>{fileDates.map((r: any[]) => <tr key={r[0]}><td className="text-[var(--ink-2)]">{r[0]}</td><td className="mono">{r[1]}</td></tr>)}</tbody></table><p className="text-[12px] text-[var(--ink-3)] mt-2">"Excluded but still enrolled" is often just a stale enrollment file, so the headline counts months Medicaid actually paid, never enrollment status.</p></div>
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>Procedures</h2>
        <p className="text-[14px] leading-7 mt-3">A summary bill hides what was done; the procedure codes do not. Every provider page lists the specific codes behind its Medicaid dollars (T-MSIS, 2018 to 2024) and its Medicare Part B dollars (2024), with a description for each code. Two comparisons make a code meaningful. For Medicaid, the provider's dollars per patient-month on that code are ranked against every other provider billing the same code for six months or more:</p>
        <Eq>{String.raw`\text{percentile}_{p,c} = \Pr\big[\, d_{q,c} \le d_{p,c} \,\big] \quad\text{over providers } q \text{ billing code } c,\qquad d_{p,c} = \frac{\text{paid}_{p,c}}{\text{patient-months}_{p,c}}`}</Eq>
        <p className="text-[14px] leading-7">For Medicare, the provider's submitted charge divided by the allowed amount is compared with the median ratio across all providers billing that code, the way a reviewer would say "this provider bills eleven times Medicare for this code while peers bill four". A provider earns procedure points in the unified score when a large code sits in the top 5% of dollars per patient, when most of its dollars fall on code families with a documented history of abuse, or when its Medicare charge ratio is at least three times the usual ratio for the code. The points never change a tier.</p>
        <p className="text-[14px] leading-7 mt-3">Across the whole population, a code's lift is how much more often tier 1 and tier 2 providers bill it than providers in general:</p>
        <Eq>{String.raw`\text{lift}_c = \frac{n_{\text{flagged},c} / N_{\text{flagged}}}{n_{\text{all},c} / N_{\text{all}}}`}</Eq>
        {(trends ?? []).length > 0 && <div className="card p-5 mt-5"><div className="eyebrow mb-2">Codes that recur among tier 1 and tier 2 providers (at least 200 providers bill each)</div><table className="table"><thead><tr><th>code</th><th>what it is</th><th>flagged providers</th><th>all providers</th><th>lift</th><th>paid to flagged</th></tr></thead><tbody>{(trends ?? []).map((r: any) => <tr key={r.hcpcs}><td className="mono">{r.hcpcs}</td><td className="text-[12px] max-w-[320px]">{r.description || "Medicaid service code"}{r.vector === "HIGH" ? <span className="tag tag-danger ml-2">history of abuse</span> : null}</td><td>{num(r.n_flagged)}</td><td>{num(r.n_all)}</td><td>{Number(r.lift).toFixed(1)}x</td><td>{money(r.paid_flagged)}</td></tr>)}</tbody></table><p className="text-[12px] text-[var(--ink-3)] mt-2">Lift describes where the flagged population concentrates; it says nothing about any individual provider and is not used to flag anyone.</p></div>}
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>Factor desk for networks</h2>
        <p className="text-[14px] leading-7 mt-3">Every network with three or more providers is measured on thirty factors in seven families: formation timing, ownership, addresses and contacts, list exposure, market, money, and identity and enrollment. Each factor carries its value, its percentile among all such networks in the risky direction, and a robust z-score. Six rate-of-change factors (formation velocity, share of new companies, Medicaid growth, owner association bursts, county saturation trend and ownership changes) are averaged as clipped z-scores into a momentum reading:</p>
        <Eq>{String.raw`m = \frac{1}{k}\sum_{j=1}^{k} \operatorname{clip}(z_j,\,-3,\,3)`}</Eq>
        <p className="text-[14px] leading-7">with the outlook labelled rising fast at or above 1, rising from 0.3, steady, or cooling below minus 0.3. The desk is indicative: no outcome data exist yet to calibrate it, and it never changes a tier.</p>
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>One score per provider</h2>
        <p className="text-[14px] leading-7 mt-3">Every provider any detector reached gets a tier that says what the public record can prove: 1, on a public list and still paid afterwards; 2, more hours than a day holds across several organizations; 3, part of a ranked network that touches a public list; 4, network structure alone or hours beyond a day under one organization; 5, worth knowing. The score adds a bonus when strong findings from different detectors agree, and a small term for the dollars involved:</p>
        <Eq>{String.raw`\text{score} = \min\Big(100,\; \text{base}_{\text{tier}} + 8\,\max(n_{\text{strong}} - 1, 0) + \min\big(9, \log_{10} \text{dollars}\big)\Big)`}</Eq>
        <p className="text-[14px] leading-7">with tier bases of 90, 75, 60, 45 and 25, plus up to 8 procedure points as described above. Dollars come from the detector that set the tier and are never summed across detectors, so a weak indicator cannot lift a small case above a large one. Across the country: {num(t.risk_tier1)} providers in tier 1, {num(t.risk_tier2)} in tier 2, and {num(t.risk_corroborated)} confirmed independently by two detectors.</p>
      </section>

      <section className="mt-12">
        <h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>What the model does, and does not do</h2>
        <p className="text-[14px] leading-7 mt-3">Claude drafts the referral packet from the evidence rows only; any statement that cites a record outside the list is removed and counted. The regulations named in a packet come from a fixed mapping of evidence types, not from the model. The case chat can only call read-only tools over the same tables and must cite a row for every sentence. Reviewer rejections are classified to the kind of evidence that was wrong, and only that kind's weight moves; the weights stay informational until there are a few hundred reviews. Batch jobs extract state exclusion lists from PDFs and spreadsheets, review the time-code table, match list entries that lack an NPI by name, and adjudicate borderline owner matches, each with a written report.</p>
      </section>

      {md && <details className="mt-12"><summary className="serif text-[24px] cursor-pointer" style={{ color: "var(--blue)" }}>Technical appendix, generated by the pipeline</summary><div className="card p-8 mt-4 prose-methods"><ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown></div></details>}
    </div>
  );
}
