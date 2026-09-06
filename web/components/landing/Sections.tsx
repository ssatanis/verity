import Link from "next/link";
import { Reveal, Rise, Stagger, StaggerItem, Headline, CountUp, Parallax, ScrollFade, ScrollCue, ScrollRule, BackToTop, ScrollProgress } from "./Scroll";
import { HeroNetwork } from "./HeroNetwork";
import { TierFigure, PaidAfterFigure, DetectorGlyph, PipelineFigure } from "./Figures";
const W = "max-w-[1860px] mx-auto px-8 md:px-[72px]";
// Section labels stick beside the column they describe while it scrolls.
const STICKY = "md:sticky md:top-[124px] md:self-start";

export { ScrollProgress, BackToTop };

export function Hero() {
  return (
    <section className={W}>
      <div className="relative overflow-hidden" style={{ minHeight: 720 }}>
        <HeroNetwork />
        <ScrollFade>
          <div className="relative px-8 md:px-[74px] pt-[88px] pb-[300px]" style={{ pointerEvents: "none" }}>
            <Headline lines={["Integrity Before", "the Payment", "Goes Out"]} className="display serif text-white" style={{ lineHeight: 1.04, fontSize: "clamp(48px, 7vw, 104px)", pointerEvents: "none" }} delay={0.15} />
          </div>
        </ScrollFade>
        <div className="hero-band absolute left-0 right-0 bottom-0 px-8 md:px-[74px] py-16" style={{ pointerEvents: "none" }}>
          <Rise delay={0.5}><p className="text-white text-[19px] leading-9 max-w-2xl">Before a payment goes out, Verity reads the whole public record, so that every dollar a health plan pays is a dollar it can defend.</p></Rise>
          <div className="mt-8"><ScrollCue /></div>
        </div>
      </div>
    </section>
  );
}
export function WhatWeDo() {
  return (
    <section id="what" style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24 grid md:grid-cols-[1fr_3fr] gap-12`}>
        <div className={`text-[17px] ${STICKY}`} style={{ color: "var(--blue)" }}>What we do</div>
        <div className="lrule pl-10">
          <Reveal><p className="serif text-[28px] md:text-[36px] leading-[1.22]" style={{ color: "var(--blue)" }}>Our ambition is that no health plan pays a provider the public record has already warned it about. We bring public enrollment, ownership, exclusion and spending records together into one picture, so that investigators see the pattern before the payment clears.</p></Reveal>
          <Reveal delay={0.15}><Link href="/app" className="btn btn-arrow mt-12">Explore the Console<span className="btn-arrow-glyph" aria-hidden>&rarr;</span></Link></Reveal>
        </div>
      </div>
    </section>
  );
}
export function Stats({ stats, byYear }: { stats: Record<string, any>; byYear: [string, number, number][] }) {
  const items: [number, "count" | "money", string, string][] = [
    [Number(stats.d3_npis_paid_after ?? stats.risk_tier1 ?? 0), "count", "Providers on a public exclusion or revocation list that Medicaid kept paying afterwards", "Each one is matched by exact NPI with the name verified, and the payments are dated after the action and before any reinstatement."],
    [Number(stats.d3_dollars_after ?? 0), "money", "Paid to those providers after the action that should have triggered a screening check", "Federal rules require states to check the federal exclusion lists every month. This is not a loss estimate; payments after a reinstatement are not counted."],
    [Number(stats.d1_clusters_eligible ?? 0), "count", "Provider networks ranked for a closer look", "Hospices, home health agencies and nursing facilities connected through owners, suites, phone numbers, officials and the addresses of revoked companies."],
  ];
  return (
    <section className={`${W} py-24`}>
      <Stagger className="grid md:grid-cols-3 gap-10" step={0.12}>
        {items.map(([v, fmt, l, f]) => (
          <StaggerItem key={l} className="lrule pl-10 py-2">
            <div className="serif tabular-nums" style={{ color: "var(--blue)", fontSize: "clamp(56px, 6.2vw, 108px)", lineHeight: 1, wordBreak: "break-word" }}><CountUp value={v} format={fmt} /></div>
            <div className="text-[17px] mt-14 leading-7 max-w-xs" style={{ color: "var(--ink-2)" }}>{l}</div>
            <div className="text-[13px] mt-8 leading-6 max-w-xs" style={{ color: "var(--ink-3)" }}>{f}</div>
          </StaggerItem>
        ))}
      </Stagger>
      {byYear.length > 0 && <PaidAfterFigure rows={byYear} />}
    </section>
  );
}
export function Detectors() {
  const d = [
    ["01", "Ghost Networks", "Newly formed hospices, home health agencies and nursing facilities that share owners, suites, phones or officials, often at the address of an already revoked company. Verity resolves who owns what and ranks each network by how unusual its structure is.", "/app/clusters"],
    ["02", "Impossible Days", "Medicaid billing turned into hours of hands-on care. When three or more organizations bill one clinician for more hours than a day holds in the same month, the volume cannot be one person's work. Supervisory billing stays out of the top tier.", "/app/flags?detector=D2"],
    ["03", "Paid After a Screening Trigger", "Providers revoked by Medicare, excluded by the OIG or excluded by a state, whom Medicaid kept paying after the action. Matched by exact NPI with the name verified; SAM.gov debarments and NPI deactivations stay informational.", "/app/flags?detector=D3"],
  ];
  return (
    <section id="detectors" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <Headline as="h2" onScroll lines={["Three Detectors,", "One Hierarchy"]} className={`display serif text-[54px] md:text-[72px] ${STICKY}`} style={{ color: "var(--blue)" }} />
        <Reveal><p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>Each detector asks a different question of a different public record. A provider flagged by two of them independently is the strongest signal the system produces, and the ranking is built so that corroboration, not volume, rises to the top.</p></Reveal>
      </div>
      <Stagger className="grid md:grid-cols-3 gap-10 mt-24" step={0.12}>
        {d.map(([n, h, t, href], i) => (
          <StaggerItem key={n}>
            <Link href={href} className="lrule pl-10 py-2 block group card-lift">
              <div className="flex items-end justify-between max-w-sm"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(56px, 5.5vw, 96px)", lineHeight: 1 }}>{n}</div><DetectorGlyph kind={i === 0 ? "network" : i === 1 ? "clock" : "list"} /></div>
              <h3 className="serif text-[34px] mt-10 underline-grow" style={{ color: "var(--ink)" }}>{h}</h3>
              <p className="text-[15px] leading-7 mt-4 max-w-sm" style={{ color: "var(--ink-2)" }}>{t}</p>
            </Link>
          </StaggerItem>
        ))}
      </Stagger>
    </section>
  );
}
export function Hierarchy({ tierCounts }: { tierCounts: number[] }) {
  const tiers = [["1", "On a public list and still paid afterwards, or adjudicated in a public enforcement record"], ["2", "More hours than a day holds, billed by three or more organizations"], ["3", "Part of a suspicious network that touches a public list, or charged but not yet adjudicated"], ["4", "Network structure alone, or hours beyond a day under one organization"], ["5", "Worth knowing, not yet a referral: supervisory volume and informational lists"]];
  return (
    <section style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24 grid md:grid-cols-[1fr_1.4fr] gap-12`}>
        <div className={STICKY}>
          <Headline as="h2" onScroll lines={["Every Candidate", "Carries Its Tier"]} className="display serif text-[54px] md:text-[64px]" style={{ color: "var(--blue)" }} />
          <Reveal delay={0.1}><p className="text-[16px] leading-7 mt-8 max-w-md" style={{ color: "var(--ink-2)" }}>The score is a tier base, a bonus for every strong finding that reached the provider independently, and a bounded dollar term. Dollars at risk come from the detector that set the tier, count each provider once, and are never summed. Every row is a candidate for records review, not a finding.</p></Reveal>
          {tierCounts.length === 5 && <TierFigure counts={tierCounts} />}
        </div>
        <div className="relative pl-10">
          <ScrollRule className="absolute left-0 top-0 bottom-0" style={{ width: 1, background: "var(--line)" }} />
          <Stagger step={0.08}>
            {tiers.map(([n, h], i) => (
              <StaggerItem key={n} className={`flex items-center gap-8 py-6 rule ${i === 0 ? "border-t-0" : ""}`}>
                <span className="serif tier-mark" style={{ color: "var(--blue)", fontSize: 44, lineHeight: 1, width: 48 }}>{n}</span>
                <span className="serif text-[24px] leading-tight" style={{ color: "var(--ink)" }}>{h}</span>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </div>
    </section>
  );
}
export function WhoWeServe() {
  const items = [["Special Investigations", "A ranked queue with the evidence already assembled, so records requests go out on day one instead of week three."], ["Payment Integrity", "Hold the highest-tier candidates for review before a claim is paid, with the regulation behind each hold."], ["Network and Credentialing", "See the owners, formation dates and shared suites behind a new enrollment before signing a contract, and run the monthly list checks the rules require."], ["Compliance and Legal", "Packets describe records and dates, never intent, and every statement traces to a public dataset, so the file holds up when challenged."]];
  return (
    <section id="who" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <Headline as="h2" onScroll lines={["Built for the People", "Who Sign the Hold"]} className={`display serif text-[54px] md:text-[72px] ${STICKY}`} style={{ color: "var(--blue)" }} />
        <Reveal><p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>Medicaid managed care plans, Medicare Advantage plans and commercial payers carry the loss when a ghost network bills them. Verity gives the teams that investigate, hold, contract and defend the same ranked list and the same evidence.</p></Reveal>
      </div>
      <Stagger className="grid md:grid-cols-4 gap-10 mt-20" step={0.1}>
        {items.map(([h, t]) => <StaggerItem key={h} className="lrule pl-8 py-2 card-lift"><h3 className="serif text-[28px]" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[14.5px] leading-7 mt-4" style={{ color: "var(--ink-2)" }}>{t}</p></StaggerItem>)}
      </Stagger>
    </section>
  );
}
export function HowItWorks() {
  const steps = [["Gather", "Public federal and state records: Medicaid spending and enrollment, Medicare enrollments and owners, the national provider registry, exclusion and revocation lists, market saturation, quality data, Census geography, state lists and fee schedules."], ["Resolve", "Validate every provider number, repair encodings, standardize addresses, and work out which owner records are the same person with a probabilistic model fitted on the records, its merge rule checked against a sample a model adjudicated."], ["Detect", "Three detectors with conservative assumptions and explicit tiers, evaluated against public labels with the uncertainty stated."], ["Explain", "The packet is drafted from the evidence rows only, cites a record for every finding, and names the regulation each one relates to."], ["Learn", "Reviewers accept or reject each packet. The decisions re-weight the evidence families behind the network score, so the ranking adjusts to what investigators confirm."]];
  return (
    <section id="how" style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24`}>
        <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
          <Headline as="h2" onScroll lines={["Public Records In,", "A Defensible", "Packet Out"]} className={`display serif text-[54px] md:text-[72px] ${STICKY}`} style={{ color: "var(--blue)" }} />
          <Reveal><p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>No patient data and no claim lines leave your systems. Verity scores providers and networks from public records, and a person signs every action. Connect your own claims warehouse to hold payments before they go out.</p></Reveal>
        </div>
        <Stagger className="grid md:grid-cols-5 gap-8 mt-20" step={0.1}>
          {steps.map(([h, t], i) => <StaggerItem key={h} className="lrule pl-8 py-2 card-lift"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(40px, 3.2vw, 56px)", lineHeight: 1 }}>{String(i + 1).padStart(2, "0")}</div><h3 className="serif text-[26px] mt-6" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[13.5px] leading-6 mt-3" style={{ color: "var(--ink-2)" }}>{t}</p></StaggerItem>)}
        </Stagger>
        <PipelineFigure />
      </div>
    </section>
  );
}
export function Security() {
  const items = [["No patient data", "Public provider-level datasets only. No patients, no claim lines, nothing beyond the public record."], ["A person decides", "Every packet is a draft for a reviewer, every action is signed by a person, and a deployment puts the console behind your identity provider."], ["Runs anywhere", "Hosted today, or inside your own environment. The warehouse rebuilds from public files in minutes and refreshes weekly."], ["Holds up", "Every number traces to a public record, and the Methods page says what each evaluation can and cannot support."]];
  return (
    <section id="security" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_3fr] gap-12">
        <div className={`text-[17px] ${STICKY}`} style={{ color: "var(--blue)" }}>Security and deployment</div>
        <div className="lrule pl-10">
          <Reveal><p className="serif text-[34px] md:text-[42px] leading-[1.2]" style={{ color: "var(--blue)" }}>Built to be audited. Verity is designed for the compliance review that comes before any deployment inside a health plan.</p></Reveal>
          <Stagger className="grid md:grid-cols-4 gap-8 mt-14" step={0.08}>{items.map(([h, t]) => <StaggerItem key={h}><h3 className="serif text-[24px]" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[14px] leading-6 mt-3" style={{ color: "var(--ink-2)" }}>{t}</p></StaggerItem>)}</Stagger>
        </div>
      </div>
    </section>
  );
}
export function CTA() {
  return (
    <section id="contact" className="overflow-hidden" style={{ background: "var(--blue)" }}>
      <div className={`${W} py-28 grid md:grid-cols-[1.2fr_1fr] gap-12 items-center`}>
        <Parallax speed={26}><Headline as="h2" onScroll lines={["See Your Network", "Through Verity"]} className="display serif text-white text-[56px] md:text-[80px]" /></Parallax>
        <Reveal delay={0.12}><p className="text-[18px] leading-8 text-white max-w-md">A pilot takes one week. We run your state's providers through Verity and hand your investigations team a ranked queue with packets.</p><a href="mailto:ss4497@cornell.edu?subject=Verity%20pilot" className="btn btn-white btn-arrow mt-10">Request a Pilot<span className="btn-arrow-glyph" aria-hidden>&rarr;</span></a></Reveal>
      </div>
    </section>
  );
}
