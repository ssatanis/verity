import Link from "next/link";
const money = (v: number) => v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v).toLocaleString()}`;
const num = (v: number) => Number(v ?? 0).toLocaleString();

export function Hero({ stats }: { stats: Record<string, any> }) {
  const t1 = stats.risk_tier1 ?? 0, t2 = stats.risk_tier2 ?? 0, corr = stats.risk_corroborated ?? 0;
  return (
    <section className="max-w-[1160px] mx-auto px-6 md:px-10 pt-16 pb-20 grid md:grid-cols-[1.15fr_1fr] gap-14 items-end">
      <div>
        <div className="eyebrow">Pre-payment provider integrity</div>
        <h1 className="display serif text-[64px] md:text-[92px] mt-4">Stop the check before it goes out.</h1>
        <p className="text-[17px] text-[var(--ink-2)] mt-7 max-w-xl leading-7">Verity scores every enrolled provider against fourteen public federal and state datasets, ranks referral candidates by an explicit evidence hierarchy, and hands your SIU a packet where every sentence cites the public row it came from.</p>
        <div className="flex gap-3 mt-8">
          <a href="mailto:ss4497@cornell.edu?subject=Verity%20pilot" className="btn">Request a pilot</a>
          <Link href="/app" className="btn btn-ghost">Open the console</Link>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-px" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
        {[["Referral candidates, tier 1", num(t1), "documented action, then payment"], ["Referral candidates, tier 2", num(t2), "impossible volume with concurrency"], ["Corroborated by two or more detectors", num(corr), "the strongest signal we produce"], ["Rows scanned", num(stats.spend_rows ?? 238015729), "T-MSIS 2018 to 2024, every state"]].map(([l, v, s]) => (
          <div key={l} className="p-6" style={{ background: "var(--paper)" }}><div className="eyebrow">{l}</div><div className="serif text-[44px] leading-none mt-3">{v}</div><div className="text-[12px] text-[var(--ink-3)] mt-2">{s}</div></div>
        ))}
      </div>
    </section>
  );
}
export function Buyers() {
  const items = [
    ["Special investigations", "A ranked queue with the evidence trail already assembled. Records requests go out on day one, not week three."],
    ["Payment integrity", "Pre-payment holds on tier 1 and tier 2 candidates before adjudication, with the regulatory ground for each hold."],
    ["Network and credentialing", "Ownership graphs, incorporation bursts and shared suites at the point of contracting, plus monthly LEIE, SAM and NPPES checks under 42 CFR 455.436."],
    ["Compliance and legal", "Packets describe records and dates, never intent. Every claim traces to a public dataset, so the file survives a challenge."],
  ];
  return (
    <section id="buyers" className="rule">
      <div className="max-w-[1160px] mx-auto px-6 md:px-10 py-20 grid md:grid-cols-[1fr_1.6fr] gap-14">
        <div><div className="eyebrow">Built for health plans</div><h2 className="display serif text-[48px] mt-4">Four teams, one queue.</h2><p className="text-[15px] text-[var(--ink-2)] mt-5 leading-7">Medicaid managed care plans, Medicare Advantage plans and commercial payers eat the loss when a ghost network bills them. Verity gives the people who investigate, hold, contract and defend the same ranked list and the same evidence.</p></div>
        <div className="grid md:grid-cols-2 gap-px" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
          {items.map(([h, d]) => <div key={h} className="p-7" style={{ background: "var(--paper)" }}><h3 className="serif text-[26px]">{h}</h3><p className="text-[13.5px] text-[var(--ink-2)] mt-3 leading-6">{d}</p></div>)}
        </div>
      </div>
    </section>
  );
}
export function Detectors({ stats }: { stats: Record<string, any> }) {
  const d = [
    ["01", "Ghost networks", "Hospice, home health and skilled nursing enrollments linked through owners, suites, phones, officials and the addresses of revoked entities. Fellegi-Sunter identity resolution, Leiden communities, robust z-scores, chains held out.", `${num(stats.d1_clusters_eligible ?? 0)} ranked communities`, "/app/clusters"],
    ["02", "Impossible days", "Time-based Medicaid codes converted to clinician hours with a rate-free lower bound, published state rates, and Minnesota's own daily caps. Umbrella billing is separated from impossibility.", `${num(stats.d2_npis_impossible ?? 0)} rendering NPIs with an impossible month`, "/app/flags?detector=D2"],
    ["03", "Paid after a screening trigger", "Medicare revocations, OIG exclusions, SAM debarments and state exclusion lists joined to Medicaid service months after the action, with check-digit and name agreement on every match.", `${num(stats.d3_npis_paid_after ?? 0)} NPIs, ${money(stats.d3_dollars_after ?? 0)} after the action`, "/app/flags?detector=D3"],
  ];
  return (
    <section id="detectors" className="rule">
      <div className="max-w-[1160px] mx-auto px-6 md:px-10 py-20">
        <div className="eyebrow">Three detectors, one hierarchy</div>
        <h2 className="display serif text-[48px] mt-4 max-w-2xl">Indicators ranked by what the public record can prove.</h2>
        <div className="grid md:grid-cols-3 gap-px mt-12" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
          {d.map(([n, h, txt, stat, href]) => (
            <Link key={n} href={href} className="p-8 block hover:bg-[var(--paper-2)]" style={{ background: "var(--paper)" }}>
              <div className="serif text-[54px] leading-none" style={{ color: "var(--accent)" }}>{n}</div>
              <h3 className="serif text-[30px] mt-5">{h}</h3>
              <p className="text-[13.5px] text-[var(--ink-2)] mt-3 leading-6">{txt}</p>
              <div className="mt-6 text-[13px] link">{stat}</div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
export function Hierarchy() {
  const tiers = [["1", "Documented action, then payment", "On a tier-A federal or state list, and Medicaid service months after it."], ["2", "Impossible volume with concurrency", "Personal-service hours no clinician can deliver, billed by three or more organisations in the same month, or over a state's own cap."], ["3", "Network structure with a list link", "A ranked provider community with a member or owner on an exclusion, revocation or termination list."], ["4", "Structure, or single-organisation volume", "Bursts, shared suites and owners without a list link, or volume that may be supervisory billing."], ["5", "Informational", "Deactivated identifiers still billing, growth and concentration outliers, plaza addresses."]];
  return (
    <section id="how" className="rule" style={{ background: "var(--paper-2)" }}>
      <div className="max-w-[1160px] mx-auto px-6 md:px-10 py-20 grid md:grid-cols-[1fr_1.4fr] gap-14">
        <div><div className="eyebrow">Evidence hierarchy</div><h2 className="display serif text-[48px] mt-4">Every candidate carries its tier and its reasons.</h2><p className="text-[15px] text-[var(--ink-2)] mt-5 leading-7">Score = tier base, plus a bonus for every detector that reached the provider independently, plus a bounded dollar term. Dollars at risk count each provider once, never summed across detectors. Corroboration is the strongest signal in the system, and it is weighted that way.</p></div>
        <div>{tiers.map(([n, h, d]) => <div key={n} className="flex gap-6 py-5 rule"><span className={`tier tier-${n}`}>{n}</span><div><div className="serif text-[22px]">{h}</div><div className="text-[13px] text-[var(--ink-2)] mt-1">{d}</div></div></div>)}</div>
      </div>
    </section>
  );
}
export function Pipeline() {
  const steps = [["Ingest", "T-MSIS spending, enrollment segments, PECOS enrollments and owners, NPPES, LEIE, SAM, revocations, Market Saturation, Care Compare, Census, state lists and fee schedules."], ["Resolve", "Check-digit validation, UTF-8 repair, address normalisation, identity resolution with an EM-fitted match model, model-adjudicated borderline pairs."], ["Detect", "Three detectors, robust baselines, conservative unit prices, explicit tiers, held-out evaluation with the significance stated."], ["Explain", "The investigator agent drafts a packet from evidence rows only; every finding cites its rows; grounds come from 42 CFR 455 and 1001."], ["Learn", "Reviewers accept or reject; the reason in the note is classified to the evidence family that was wrong, and the weights update."]];
  return (
    <section className="rule">
      <div className="max-w-[1160px] mx-auto px-6 md:px-10 py-20">
        <div className="eyebrow">How it works</div>
        <h2 className="display serif text-[48px] mt-4">Public data in, a defensible packet out.</h2>
        <div className="grid md:grid-cols-5 gap-px mt-12" style={{ background: "var(--line)", border: "1px solid var(--line)" }}>
          {steps.map(([h, d], i) => <div key={h} className="p-6" style={{ background: "var(--paper)" }}><div className="serif text-[30px]" style={{ color: "var(--accent)" }}>{String(i + 1).padStart(2, "0")}</div><h3 className="serif text-[24px] mt-3">{h}</h3><p className="text-[12.5px] text-[var(--ink-2)] mt-2 leading-5">{d}</p></div>)}
        </div>
      </div>
    </section>
  );
}
export function Sources() {
  const s = ["T-MSIS Medicaid provider spending", "T-MSIS enrollment segments", "PECOS hospice, HHA, SNF enrollments", "PECOS All Owners and CHOW", "NPPES monthly file", "OIG LEIE", "SAM.gov exclusions", "Medicare revocations", "Market Saturation and Utilization", "Care Compare", "PAC PUF", "Census ZCTA and county", "State exclusion lists", "State fee schedules"];
  return (
    <section className="rule" style={{ background: "var(--ink)", color: "#fff" }}>
      <div className="max-w-[1160px] mx-auto px-6 md:px-10 py-16">
        <div className="eyebrow" style={{ color: "#a9a9ad" }}>Fourteen public datasets, no PHI</div>
        <div className="flex flex-wrap gap-x-8 gap-y-3 mt-6 serif text-[24px]">{s.map(x => <span key={x}>{x}</span>)}</div>
        <p className="text-[13px] mt-8 max-w-2xl" style={{ color: "#c9c9cd" }}>Verity never touches a beneficiary or a claim line. It scores providers and networks from public records, and a human signs every action. Bring your own claims warehouse for pre-payment holds.</p>
      </div>
    </section>
  );
}
export function CTA() {
  return (
    <section id="contact" className="rule">
      <div className="max-w-[1160px] mx-auto px-6 md:px-10 py-24 text-center">
        <h2 className="display serif text-[56px] md:text-[72px]">See your network through Verity.</h2>
        <p className="text-[15px] text-[var(--ink-2)] mt-5 max-w-lg mx-auto leading-7">A pilot takes one week: we run your state's providers through the pipeline and hand your SIU a ranked queue with packets.</p>
        <div className="flex justify-center gap-3 mt-8"><a href="mailto:ss4497@cornell.edu?subject=Verity%20pilot" className="btn">Request a pilot</a><Link href="/app/methods" className="btn btn-ghost">Read the methods</Link></div>
      </div>
    </section>
  );
}
