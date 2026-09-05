import Link from "next/link";
import { Reveal, Rise } from "./Reveal";
import { HeroNetwork } from "./HeroNetwork";
const money = (v: number) => v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v).toLocaleString()}`;
const num = (v: number) => Number(v ?? 0).toLocaleString();
const W = "max-w-[1860px] mx-auto px-8 md:px-[72px]";

export function Hero() {
  return (
    <section className={W}>
      <div className="relative overflow-hidden" style={{ minHeight: 720 }}>
        <HeroNetwork />
        <div className="relative px-8 md:px-[74px] pt-[88px] pb-[300px]" style={{ pointerEvents: "none" }}>
          <Rise><h1 className="display serif text-white" style={{ lineHeight: 1.04, fontSize: "clamp(48px, 7vw, 104px)", pointerEvents: "none" }}>Every Medicaid Dollar,<br />Verified Before<br />It Is Paid</h1></Rise>
        </div>
        <div className="hero-band absolute left-0 right-0 bottom-0 px-8 md:px-[74px] py-16" style={{ pointerEvents: "none" }}>
          <Rise delay={0.25}><p className="text-white text-[19px] leading-9 max-w-2xl">Fourteen public datasets. Every Medicare and Medicaid provider. One ranked queue, and a packet in which every sentence cites the record behind it.</p></Rise>
        </div>
      </div>
    </section>
  );
}
export function WhatWeDo() {
  return (
    <section id="what" style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24 grid md:grid-cols-[1fr_3fr] gap-12`}>
        <div className="text-[17px]" style={{ color: "var(--blue)" }}>What we do</div>
        <div className="lrule pl-10">
          <Reveal><p className="serif text-[28px] md:text-[36px] leading-[1.22]" style={{ color: "var(--blue)" }}>Our ambition is that every dollar a health plan pays a provider is a dollar it can defend. We bring public enrollment, ownership, exclusion and spending records together into one picture, so that investigators see the pattern before the payment clears.</p>
          <Link href="/app" className="btn mt-12">Explore the Console</Link></Reveal>
        </div>
      </div>
    </section>
  );
}
export function Stats({ stats }: { stats: Record<string, any> }) {
  const items = [
    [num(stats.risk_tier1 ?? 0), "Providers on a public exclusion or revocation list that Medicaid kept paying afterwards", "Each one is matched by exact NPI with the name verified, and the payments are dated after the action and before any reinstatement."],
    [money(stats.d3_dollars_after ?? 0), "Paid to those providers after the action that should have triggered a screening check", "Federal rules require states to check these lists every month. This is not a loss estimate; appeals and reinstatements are respected."],
    [num(stats.d1_clusters_eligible ?? 0), "Provider networks ranked for a closer look", "Hospices, home health agencies and nursing facilities connected through owners, suites, phone numbers, officials and the addresses of revoked companies."],
  ];
  return (
    <section className={`${W} py-24`}>
      <div className="grid md:grid-cols-3 gap-10">
        {items.map(([v, l, f], i) => <Reveal key={l} delay={i * 0.12} className="lrule pl-10 py-2"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(56px, 6.2vw, 108px)", lineHeight: 1, wordBreak: "break-word" }}>{v}</div><div className="text-[17px] mt-14 leading-7 max-w-xs" style={{ color: "var(--ink-2)" }}>{l}</div><div className="text-[13px] mt-8 leading-6 max-w-xs" style={{ color: "var(--ink-3)" }}>{f}</div></Reveal>)}
      </div>
    </section>
  );
}
export function Detectors() {
  const d = [
    ["01", "Ghost Networks", "Groups of newly formed hospices, home health agencies and nursing facilities that share owners, suites, phone numbers or officials, often at the address of a company that was already revoked. Verity resolves who owns what and ranks each network by how unusual its structure is.", "/app/clusters"],
    ["02", "Impossible Days", "Medicaid billing turned into hours of hands-on care. When one clinician is billed for more hours than a day holds, across several unrelated organizations in the same month, the volume cannot be one person's work.", "/app/flags?detector=D2"],
    ["03", "Paid After a Screening Trigger", "Providers revoked by Medicare, excluded by the OIG, debarred in SAM.gov or excluded by a state, whom Medicaid kept paying after the action. Matched by exact NPI with the name verified.", "/app/flags?detector=D3"],
  ];
  return (
    <section id="detectors" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <h2 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Three Detectors,<br />One Hierarchy</h2>
        <p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>Each detector asks a different question of a different public record. A provider flagged by two of them independently is the strongest signal the system produces, and the ranking is built so that corroboration, not volume, rises to the top.</p>
      </div>
      <div className="grid md:grid-cols-3 gap-10 mt-24">
        {d.map(([n, h, t, href], i) => <Reveal key={n} delay={i * 0.12}><Link href={href} className="lrule pl-10 py-2 block group"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(56px, 5.5vw, 96px)", lineHeight: 1 }}>{n}</div><h3 className="serif text-[34px] mt-10 group-hover:underline" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[15px] leading-7 mt-4 max-w-sm" style={{ color: "var(--ink-2)" }}>{t}</p></Link></Reveal>)}
      </div>
    </section>
  );
}
export function Hierarchy() {
  const tiers = [["1", "On a public list, and still paid afterwards"], ["2", "More hours than a day holds, across several organizations"], ["3", "Part of a suspicious network that touches a public list"], ["4", "Network structure alone, or hours beyond a day under one organization"], ["5", "Worth knowing, not yet a referral"]];
  return (
    <section style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24 grid md:grid-cols-[1fr_1.4fr] gap-12`}>
        <div><h2 className="display serif text-[54px] md:text-[64px]" style={{ color: "var(--blue)" }}>Every Candidate<br />Carries Its Tier</h2><p className="text-[16px] leading-7 mt-8 max-w-md" style={{ color: "var(--ink-2)" }}>The score is a tier base, a bonus for every strong finding that reached the provider independently, and a bounded dollar term. Dollars at risk come from the detector that set the tier, count each provider once, and are never summed. Every row is a candidate for records review, not a finding.</p></div>
        <div className="lrule pl-10">{tiers.map(([n, h], i) => <Reveal key={n} delay={i * 0.08} className="flex items-center gap-8 py-6 rule first:border-t-0"><span className="serif" style={{ color: "var(--blue)", fontSize: 44, lineHeight: 1, width: 48 }}>{n}</span><span className="serif text-[26px]" style={{ color: "var(--ink)" }}>{h}</span></Reveal>)}</div>
      </div>
    </section>
  );
}
export function WhoWeServe() {
  const items = [["Special Investigations", "A ranked queue with the evidence already assembled, so records requests go out on day one instead of week three."], ["Payment Integrity", "Hold the highest-tier candidates for review before a claim is paid, with the regulation behind each hold."], ["Network and Credentialing", "See the owners, formation dates and shared suites behind a new enrollment before signing a contract, and run the monthly list checks the rules require."], ["Compliance and Legal", "Packets describe records and dates, never intent, and every statement traces to a public dataset, so the file holds up when challenged."]];
  return (
    <section id="who" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <h2 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Built for the People<br />Who Sign the Hold</h2>
        <p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>Medicaid managed care plans, Medicare Advantage plans and commercial payers carry the loss when a ghost network bills them. Verity gives the teams that investigate, hold, contract and defend the same ranked list and the same evidence.</p>
      </div>
      <div className="grid md:grid-cols-4 gap-10 mt-20">
        {items.map(([h, t], i) => <Reveal key={h} delay={i * 0.1} className="lrule pl-8 py-2"><h3 className="serif text-[28px]" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[14.5px] leading-7 mt-4" style={{ color: "var(--ink-2)" }}>{t}</p></Reveal>)}
      </div>
    </section>
  );
}
export function HowItWorks() {
  const steps = [["Gather", "Fourteen public datasets: Medicaid spending and enrollment, Medicare enrollments and owners, the national provider registry, exclusion and revocation lists, market saturation, quality data, Census geography, state lists and fee schedules."], ["Resolve", "Validate every provider number, repair encodings, standardize addresses, and work out which owner records are the same person, with borderline cases adjudicated by a model."], ["Detect", "Three detectors with conservative assumptions and explicit tiers, evaluated against public labels with the uncertainty stated."], ["Explain", "An investigator agent drafts the packet from the evidence rows only, cites a record for every finding, and names the regulation each one relates to."], ["Learn", "Reviewers accept or reject. The reason given is filed under the kind of evidence that was wrong, and the ranking adjusts."]];
  return (
    <section id="how" style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24`}>
        <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
          <h2 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Public Records In,<br />A Defensible<br />Packet Out</h2>
          <p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>No patient data and no claim lines leave your systems. Verity scores providers and networks from public records, and a person signs every action. Connect your own claims warehouse to hold payments before they go out.</p>
        </div>
        <div className="grid md:grid-cols-5 gap-8 mt-20">
          {steps.map(([h, t], i) => <Reveal key={h} delay={i * 0.1} className="lrule pl-8 py-2"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(40px, 3.2vw, 56px)", lineHeight: 1 }}>{String(i + 1).padStart(2, "0")}</div><h3 className="serif text-[26px] mt-6" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[13.5px] leading-6 mt-3" style={{ color: "var(--ink-2)" }}>{t}</p></Reveal>)}
        </div>
      </div>
    </section>
  );
}
export function Security() {
  const items = [["No patient data", "Public provider-level datasets only. No patients, no claim lines, nothing beyond the public record."], ["A person decides", "Every packet is a draft for a reviewer, every action is signed by a person, and a deployment puts the console behind your identity provider."], ["Runs anywhere", "Hosted today, or inside your own environment. The warehouse rebuilds from public files in minutes and refreshes weekly."], ["Holds up", "Every number traces to a public record, and the Methods page says what each evaluation can and cannot support."]];
  return (
    <section id="security" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_3fr] gap-12">
        <div className="text-[17px]" style={{ color: "var(--blue)" }}>Security and deployment</div>
        <div className="lrule pl-10">
          <Reveal><p className="serif text-[34px] md:text-[42px] leading-[1.2]" style={{ color: "var(--blue)" }}>Built to be audited. Verity is designed for the compliance review that comes before any deployment inside a health plan.</p></Reveal>
          <div className="grid md:grid-cols-4 gap-8 mt-14">{items.map(([h, t]) => <div key={h}><h3 className="serif text-[24px]" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[14px] leading-6 mt-3" style={{ color: "var(--ink-2)" }}>{t}</p></div>)}</div>
        </div>
      </div>
    </section>
  );
}
export function CTA() {
  return (
    <section id="contact" style={{ background: "var(--blue)" }}>
      <div className={`${W} py-28 grid md:grid-cols-[1.2fr_1fr] gap-12 items-center`}>
        <Reveal><h2 className="display serif text-white text-[56px] md:text-[80px]">See Your Network<br />Through Verity</h2></Reveal>
        <div><p className="text-[18px] leading-8 text-white max-w-md">A pilot takes one week. We run your state's providers through Verity and hand your investigations team a ranked queue with packets.</p><a href="mailto:ss4497@cornell.edu?subject=Verity%20pilot" className="btn btn-white mt-10">Request a Pilot</a></div>
      </div>
    </section>
  );
}
