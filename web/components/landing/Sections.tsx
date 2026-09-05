import Link from "next/link";
const money = (v: number) => v >= 1e9 ? `$${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `$${(v / 1e6).toFixed(1)}M` : `$${Math.round(v).toLocaleString()}`;
const num = (v: number) => Number(v ?? 0).toLocaleString();
const W = "max-w-[1860px] mx-auto px-8 md:px-[72px]";

function Network() {
  // abstract provider network drawn in flag blue tints: nodes, suites, owners
  const pts = [[8, 22], [18, 12], [26, 30], [36, 18], [44, 40], [52, 14], [60, 32], [70, 22], [78, 44], [86, 16], [92, 34], [14, 48], [30, 56], [48, 62], [64, 54], [82, 62], [24, 76], [40, 84], [58, 78], [74, 86], [90, 74], [10, 68], [96, 90], [4, 90]];
  const edges = [[0, 1], [1, 3], [2, 3], [3, 5], [4, 6], [5, 7], [6, 7], [7, 9], [8, 10], [9, 10], [11, 12], [12, 13], [13, 14], [14, 15], [16, 17], [17, 18], [18, 19], [19, 20], [2, 12], [4, 13], [6, 14], [8, 15], [11, 21], [16, 21], [20, 22], [21, 23], [1, 11], [10, 15], [13, 18], [15, 20], [0, 11], [3, 13]];
  return (
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full" aria-hidden="true">
      <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#0b3a78" /><stop offset="1" stopColor="#002856" /></linearGradient></defs>
      <rect width="100" height="100" fill="url(#g)" />
      {edges.map(([a, b], i) => <line key={i} x1={pts[a][0]} y1={pts[a][1]} x2={pts[b][0]} y2={pts[b][1]} stroke="#ffffff" strokeOpacity="0.22" strokeWidth="0.18" />)}
      {pts.map(([x, y], i) => <rect key={i} x={x - 0.7} y={y - 0.7} width="1.4" height="1.4" fill="#ffffff" fillOpacity={i % 5 === 0 ? 0.95 : 0.55} />)}
    </svg>
  );
}
export function Hero() {
  return (
    <section className={W}>
      <div className="relative overflow-hidden" style={{ minHeight: 720 }}>
        <Network />
        <div className="relative px-8 md:px-[74px] pt-[88px] pb-[300px]">
          <h1 className="display serif text-white" style={{ lineHeight: 1.04, fontSize: "clamp(52px, 7.6vw, 112px)" }}>Integrity Before<br />the Payment<br />Goes Out</h1>
        </div>
        <div className="hero-band absolute left-0 right-0 bottom-0 px-8 md:px-[74px] py-16">
          <p className="text-white text-[19px] leading-9 max-w-3xl">Verity screens every enrolled provider against fourteen public federal and state datasets, ranks referral candidates on an explicit evidence hierarchy, and gives investigators a packet in which every sentence cites the public record behind it.</p>
        </div>
      </div>
    </section>
  );
}
export function WhatWeDo() {
  return (
    <section id="what" style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24 grid md:grid-cols-[1fr_3fr] gap-12`}>
        <div className="eyebrow text-[15px]">What we do</div>
        <div className="lrule pl-10">
          <p className="serif text-[34px] md:text-[46px] leading-[1.18]" style={{ color: "var(--blue)" }}>Our ambition is that every dollar a health plan pays a provider is a dollar it can defend. We assemble public enrollment, ownership, exclusion and spending records into one evidence graph, so that investigators see the pattern before the payment clears.</p>
          <Link href="/app" className="btn mt-12">Explore the Console</Link>
        </div>
      </div>
    </section>
  );
}
export function Stats({ stats }: { stats: Record<string, any> }) {
  const items = [
    [num(stats.risk_tier1 ?? 0), "Referral candidates with a documented list action followed by Medicaid service months", "Tier 1 of the evidence hierarchy. Medicare revocations, OIG exclusions and state exclusion lists, check-digit and name verified, joined to T-MSIS service months after the action."],
    [money(stats.d3_dollars_after ?? 0), "Paid after an action that should have triggered a state screening check", "42 CFR 455.436 requires monthly LEIE, SAM and NPPES checks. This is not an estimate of improper payment; appeals and reinstatements are carried as window ends."],
    [num(stats.d1_clusters_eligible ?? 0), "Provider communities ranked for network review", "Hospice, home health and skilled nursing enrollments linked through owners, suites, phones, officials and the addresses of revoked entities. Chains and platforms are held out."],
  ];
  return (
    <section className={`${W} py-24`}>
      <div className="grid md:grid-cols-3 gap-10">
        {items.map(([v, l, f]) => <div key={l} className="lrule pl-10 py-2"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(56px, 6.2vw, 108px)", lineHeight: 1, wordBreak: "break-word" }}>{v}</div><div className="text-[17px] mt-14 leading-7 max-w-xs" style={{ color: "var(--ink-2)" }}>{l}</div><div className="text-[13px] mt-8 leading-6 max-w-xs" style={{ color: "var(--ink-3)" }}>{f}</div></div>)}
      </div>
    </section>
  );
}
export function Detectors() {
  const d = [
    ["01", "Ghost Networks", "Identity resolution across owners and officials, Leiden communities, robust baselines, and links to the addresses of revoked entities. Every community carries its features and the p-value of its evaluation.", "/app/clusters"],
    ["02", "Impossible Days", "Time-based Medicaid codes converted to clinician hours with a rate-free lower bound and published state rates. Supervisory billing is separated from impossibility, and concurrency across organisations is the test.", "/app/flags?detector=D2"],
    ["03", "Paid After a Screening Trigger", "Revocations, exclusions, debarments and state list actions matched by exact NPI, check digit and name, then joined to Medicaid service months after the action and before any reinstatement.", "/app/flags?detector=D3"],
  ];
  return (
    <section id="detectors" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <h2 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Three Detectors,<br />One Hierarchy</h2>
        <p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>Each detector answers a different question from a different public record. A provider reached by two of them independently is the strongest signal the system produces, and the ranking is built so that corroboration, not volume, rises to the top.</p>
      </div>
      <div className="grid md:grid-cols-3 gap-10 mt-24">
        {d.map(([n, h, t, href]) => <Link key={n} href={href} className="lrule pl-10 py-2 block group"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(56px, 5.5vw, 96px)", lineHeight: 1 }}>{n}</div><h3 className="serif text-[34px] mt-10 group-hover:underline" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[15px] leading-7 mt-4 max-w-sm" style={{ color: "var(--ink-2)" }}>{t}</p></Link>)}
      </div>
    </section>
  );
}
export function Hierarchy() {
  const tiers = [["1", "Documented action, then payment"], ["2", "Impossible volume with concurrency"], ["3", "Network structure with a list link"], ["4", "Structure, or single-organisation volume"], ["5", "Informational"]];
  return (
    <section style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24 grid md:grid-cols-[1fr_1.4fr] gap-12`}>
        <div><h2 className="display serif text-[54px] md:text-[64px]" style={{ color: "var(--blue)" }}>Every Candidate<br />Carries Its Tier</h2><p className="text-[16px] leading-7 mt-8 max-w-md" style={{ color: "var(--ink-2)" }}>The score is a tier base, a bonus for every strong finding that reached the provider independently, and a bounded dollar term. Dollars at risk come from the detector that set the tier, count each provider once, and are never summed. Every row is a candidate for records review, not a finding.</p></div>
        <div className="lrule pl-10">{tiers.map(([n, h]) => <div key={n} className="flex items-center gap-8 py-6 rule first:border-t-0"><span className="serif" style={{ color: "var(--blue)", fontSize: 44, lineHeight: 1, width: 48 }}>{n}</span><span className="serif text-[26px]" style={{ color: "var(--ink)" }}>{h}</span></div>)}</div>
      </div>
    </section>
  );
}
export function WhoWeServe() {
  const items = [["Special Investigations", "A ranked queue with the evidence trail assembled. Records requests go out on day one."], ["Payment Integrity", "Pre-payment review on tier 1 and tier 2 candidates before adjudication, with the regulatory ground for each hold."], ["Network and Credentialing", "Ownership graphs, incorporation bursts and shared suites at the point of contracting, and monthly list checks under 42 CFR 455.436."], ["Compliance and Legal", "Packets describe records and dates, never intent. Every claim traces to a public dataset, so the file survives a challenge."]];
  return (
    <section id="who" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
        <h2 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Built for the People<br />Who Sign the Hold</h2>
        <p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>Medicaid managed care plans, Medicare Advantage plans and commercial payers carry the loss when a ghost network bills them. Verity gives the teams that investigate, hold, contract and defend the same ranked list and the same evidence.</p>
      </div>
      <div className="grid md:grid-cols-4 gap-10 mt-20">
        {items.map(([h, t]) => <div key={h} className="lrule pl-8 py-2"><h3 className="serif text-[28px]" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[14.5px] leading-7 mt-4" style={{ color: "var(--ink-2)" }}>{t}</p></div>)}
      </div>
    </section>
  );
}
export function HowItWorks() {
  const steps = [["Ingest", "T-MSIS spending and enrollment, PECOS enrollments and owners, NPPES, LEIE, SAM, revocations, Market Saturation, Care Compare, Census, state lists and fee schedules."], ["Resolve", "Check-digit validation, encoding repair, address normalisation, identity resolution with an EM-fitted match model, model-adjudicated borderline pairs."], ["Detect", "Three detectors, robust baselines, conservative unit prices, explicit tiers, held-out evaluation with the significance stated."], ["Explain", "The investigator agent drafts a packet from evidence rows only. Every finding cites its rows. Grounds come from 42 CFR 455 and 1001."], ["Learn", "Reviewers accept or reject. The reason in the note is classified to the evidence family that was wrong, and the weights update."]];
  return (
    <section id="how" style={{ background: "var(--paper-2)" }}>
      <div className={`${W} py-24`}>
        <div className="grid md:grid-cols-[1fr_1.4fr] gap-12 items-start">
          <h2 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Public Records In,<br />A Defensible<br />Packet Out</h2>
          <p className="text-[18px] leading-8 max-w-2xl" style={{ color: "var(--ink-2)" }}>No beneficiary data and no claim lines leave your systems. Verity scores providers and networks from public records, and a human signs every action. Connect your own claims warehouse for pre-payment holds.</p>
        </div>
        <div className="grid md:grid-cols-5 gap-8 mt-20">
          {steps.map(([h, t], i) => <div key={h} className="lrule pl-8 py-2"><div className="serif" style={{ color: "var(--blue)", fontSize: "clamp(40px, 3.2vw, 56px)", lineHeight: 1 }}>{String(i + 1).padStart(2, "0")}</div><h3 className="serif text-[26px] mt-6" style={{ color: "var(--ink)" }}>{h}</h3><p className="text-[13.5px] leading-6 mt-3" style={{ color: "var(--ink-2)" }}>{t}</p></div>)}
        </div>
      </div>
    </section>
  );
}
export function Security() {
  const items = [["No PHI", "Public provider-level datasets only. No beneficiaries, no claim lines, no PHI or PII beyond the public record."], ["Human in the loop", "Every packet is a draft for a reviewer. Every action is signed by a person. The console is access controlled."], ["Deployable", "Vercel and Supabase today, or inside your VPC. DuckDB warehouse rebuilds in minutes; serving tables refresh weekly."], ["Defensible", "Every number traces to a public row. Methods state what each evaluation can and cannot support."]];
  return (
    <section id="security" className={`${W} py-24`}>
      <div className="grid md:grid-cols-[1fr_3fr] gap-12">
        <div className="eyebrow text-[15px]">Security and deployment</div>
        <div className="lrule pl-10">
          <p className="serif text-[34px] md:text-[42px] leading-[1.2]" style={{ color: "var(--blue)" }}>Built to be audited. Verity is designed for the compliance review that precedes any deployment inside a health plan.</p>
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
        <h2 className="display serif text-white text-[56px] md:text-[80px]">See Your Network<br />Through Verity</h2>
        <div><p className="text-[18px] leading-8 text-white max-w-md">A pilot takes one week. We run your state's providers through the pipeline and hand your special investigations unit a ranked queue with packets.</p><a href="mailto:ss4497@cornell.edu?subject=Verity%20pilot" className="btn btn-white mt-10">Request a Pilot</a></div>
      </div>
    </section>
  );
}
