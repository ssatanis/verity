import Link from "next/link";
import { Database, Layers, Bot } from "lucide-react";
import { Logo } from "./Logo";

const SOURCES = [
  ["T-MSIS Medicaid", "TM", "#2e90fa"], ["NPPES", "NP", "#12b76a"], ["PECOS enrollment", "PE", "#7a5af8"], ["OIG LEIE", "LE", "#f04438"],
  ["SAM.gov", "SA", "#f79009"], ["Market Saturation", "MS", "#0ea5e9"], ["Care Compare", "CC", "#10b981"], ["Census TIGER", "CT", "#6366f1"],
  ["Blue Button 2.0", "BB", "#2e90fa"], ["Open Payments", "OP", "#ec4899"], ["State fee schedules", "FS", "#111114"], ["State exclusion lists", "SX", "#f04438"],
];
function Chip({ name, abbr, color, ghost = false }: { name: string; abbr: string; color: string; ghost?: boolean }) {
  return (
    <div className={`card flex items-center justify-between px-4 py-3 min-w-[230px] ${ghost ? "opacity-40" : ""}`}>
      <span className="flex items-center gap-3 text-[14px]"><span className="w-6 h-6 rounded-md grid place-items-center text-white text-[9px] font-semibold" style={{ background: color }}>{abbr}</span>{name}</span>
      <span className="text-[var(--ink-3)]">+</span>
    </div>
  );
}
export function ContinuouslyRunning() {
  return (
    <section className="px-10 pt-16 pb-14" id="solution">
      <div className="grid md:grid-cols-2 gap-8 items-start mb-10">
        <h2 className="serif text-[40px] leading-[1.05]">Continuously running</h2>
        <p className="text-[14px] leading-6 text-[var(--ink-2)] md:pt-2 max-w-md">Verity continuously scores every enrolled provider against fourteen public federal and state datasets, so a Monday payment run sees what a Friday audit would have missed.</p>
      </div>
      <div className="fade-x overflow-hidden -mx-10 px-10">
        <div className="flex gap-3 mb-3 -ml-24">{SOURCES.slice(0, 6).map((s, i) => <Chip key={s[0]} name={s[0]} abbr={s[1]} color={s[2]} ghost={i === 0} />)}</div>
        <div className="flex gap-3 -ml-8">{SOURCES.slice(6).map((s, i) => <Chip key={s[0]} name={s[0]} abbr={s[1]} color={s[2]} ghost={i === 5} />)}</div>
      </div>
    </section>
  );
}

function MiniAlert({ id, tag, text, tone = "" }: { id: string; tag: string; text: string; tone?: string }) {
  return (
    <div className={`mini-alert ${tone}`}>
      <div className="flex items-center gap-2 pl-3"><span className="serif text-[12px]">{id}</span><span className="tag">{tag}</span></div>
      <div className="pl-3 text-[10px] text-[var(--ink-3)]">{text}</div>
    </div>
  );
}
export function InProduction({ stats }: { stats: Record<string, any> }) {
  const d3n = stats.d3_npis_paid_after ?? 353, d3d = stats.d3_dollars_after ?? 50e6, d2n = stats.d2_npis_impossible ?? 0, d1n = stats.d1_clusters_eligible ?? 0;
  return (
    <section className="px-10 pt-14 pb-6 text-center">
      <h2 className="serif text-[40px] leading-[1.05] max-w-xl mx-auto">Verity in production across critical systems</h2>
      <p className="text-[14px] text-[var(--ink-2)] mt-3 max-w-md mx-auto leading-6">Integrate public signals, apply explainable logic, and hand a human investigator a packet they can act on.</p>
      <div className="grid md:grid-cols-2 gap-5 mt-10 text-left">
        <div className="card p-6 overflow-hidden relative min-h-[300px]">
          <h3 className="serif text-[22px]">Ghost networks</h3>
          <p className="text-[13px] text-[var(--ink-2)] mt-1">Shared owners, shared suites, incorporation bursts, one owner on the exclusion list</p>
          <Link href="/app/clusters" className="link-underline text-[12px] mt-4 inline-block">Explore {d1n ? `${d1n.toLocaleString()} communities` : "communities"}</Link>
          <div className="grid grid-cols-2 gap-2 mt-6 -mb-4 -mr-4">
            <MiniAlert id="D1-00001" tag="High" text="7 hospices, 2 suites, 40 days" />
            <MiniAlert id="D1-00002" tag="Medium" text="Owner on LEIE, 5 HHAs" tone="red" />
            <MiniAlert id="D1-00003" tag="High" text="Saturation z +3.1, Houston" tone="blue" />
            <MiniAlert id="D1-00004" tag="Low" text="Phone shared by 4" tone="violet" />
          </div>
        </div>
        <div className="card grad-blue p-6 overflow-hidden relative min-h-[300px] border-0">
          <h3 className="serif text-[22px]">Impossible days</h3>
          <p className="text-[13px] text-[var(--ink-2)] mt-1">Time-based Medicaid codes converted to clinician hours per day, with Minnesota's own daily caps</p>
          <Link href="/app/flags?detector=D2" className="link-underline text-[12px] mt-4 inline-block">Explore {d2n ? `${d2n.toLocaleString()} rendering NPIs` : "rendering NPIs"}</Link>
          <div className="grid grid-cols-2 gap-2 mt-6 -mb-4 -mr-4">
            <MiniAlert id="97153" tag="EIDBI" text="Over the 8 h per child cap" />
            <MiniAlert id="T1019" tag="PCA" text="31 h per calendar day" tone="red" />
            <MiniAlert id="H2015" tag="HSS" text="4 billing agencies, one NPI" tone="blue" />
            <MiniAlert id="90837" tag="Psych" text="Top 0.1 percent robust z" tone="violet" />
          </div>
        </div>
        <div className="card grad-violet p-6 overflow-hidden relative min-h-[300px] border-0">
          <h3 className="serif text-[22px]">Revoked but paid</h3>
          <p className="text-[13px] text-[var(--ink-2)] mt-1">Dead in Medicare, alive in Medicaid: {d3n.toLocaleString()} NPIs, {`$${(d3d / 1e6).toFixed(1)}M`} after the action</p>
          <Link href="/app/flags?detector=D3" className="link-underline text-[12px] mt-4 inline-block">Explore the list</Link>
          <div className="mini-alert mt-6 -mb-4 -mr-4" style={{ paddingLeft: 14 }}>
            <div className="pl-3 serif text-[12px]">Case D3 · Medicare revocation 424.535(a)(3), Medicaid paid 44 months after</div>
            <div className="pl-3 text-[10px] text-[var(--ink-3)] mt-1"><span className="font-medium text-[var(--ink)]">AI summary</span> · Laboratory revoked August 2018 for a felony ground; T-MSIS shows paid service months through April 2022.</div>
            <div className="pl-3 mt-2 flex gap-2"><span className="text-[9px] text-white bg-[var(--blue)] rounded px-2 py-[2px]">File referral</span><span className="text-[9px] rounded border border-[var(--line)] px-2 py-[2px] bg-white">Dismiss</span></div>
          </div>
        </div>
        <div className="card p-6 overflow-hidden relative min-h-[300px]">
          <h3 className="serif text-[22px]">State screening</h3>
          <p className="text-[13px] text-[var(--ink-2)] mt-1">One call at enrollment and revalidation: revocation, LEIE, SAM, state lists, NPI deactivation, cross-state termination</p>
          <Link href="/app/methods" className="link-underline text-[12px] mt-4 inline-block">Read the methods</Link>
          <div className="grid grid-cols-2 gap-2 mt-6 -mb-4 -mr-4">
            <MiniAlert id="OBBBA" tag="Dec 31 2026" text="Cross-state duplicate check" />
            <MiniAlert id="455.416" tag="CFR" text="Terminate for cause elsewhere" tone="red" />
            <MiniAlert id="NPPES" tag="Weekly" text="Deactivated NPI still billing" tone="blue" />
            <MiniAlert id="SAM" tag="Daily" text="Non-HHS debarments with NPI" tone="violet" />
          </div>
        </div>
      </div>
    </section>
  );
}
export function Automation() {
  const items = [
    { icon: Database, t: "Link your claims warehouse", d: "Point Verity at your T-MSIS extracts or pre-payment queue to score every provider before the check goes out." },
    { icon: Layers, t: "Enrich with public context", d: "Ownership, addresses, exclusions, saturation and fee schedules, joined on NPI, CCN and PECOS IDs." },
    { icon: Bot, t: "Verity works for you", d: "The investigator agent drafts the referral packet; a human accepts or rejects, and the score learns." },
  ];
  return (
    <section className="px-10 pt-16 pb-10">
      <div className="grid md:grid-cols-[1fr_auto] gap-8 items-start mb-8">
        <h2 className="serif text-[34px] leading-[1.08] max-w-sm">Automation for mission critical operation</h2>
        <p className="text-[12px] text-[var(--ink-2)] max-w-[260px] leading-5">Streamline complex workflows, reduce risk, and execute with precision when every second matters.</p>
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        {items.map(({ icon: I, t, d }) => (
          <div key={t} className="card p-5 min-h-[180px]">
            <I size={16} className="text-[var(--ink-2)]" />
            <h3 className="serif text-[17px] mt-6">{t}</h3>
            <p className="text-[11.5px] text-[var(--ink-3)] mt-2 leading-5">{d}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
export function Explore() {
  const tiles = [["TM", "16%", "8%"], ["NP", "10%", "22%"], ["LE", "84%", "10%"], ["SA", "88%", "30%"], ["MS", "74%", "70%"], ["CC", "12%", "72%"]];
  return (
    <section className="px-10 py-16 relative text-center">
      {tiles.map(([t, l, top]) => <span key={t} className="float-tile hidden md:grid" style={{ left: l, top }}>{t}</span>)}
      <h2 className="serif text-[36px]">Explore Verity</h2>
      <p className="text-[12px] text-[var(--ink-2)] mt-2 max-w-sm mx-auto leading-5">Automate program integrity from insight to action, with every number traceable to a public row.</p>
      <Link href="/app" className="btn-dark mt-6">Open console</Link>
    </section>
  );
}
export function Footer() {
  const cols = [["Product", [["Console", "/app"], ["Clusters", "/app/clusters"], ["Flags", "/app/flags"]]], ["Support", [["Methods", "/app/methods"], ["Show the math", "/app/states/MN"], ["Data sources", "/app/methods#data"]]], ["Legal", [["Terms of use", "#"], ["Data use", "#"], ["Security", "#"]]]] as const;
  return (
    <footer className="mx-6 mb-6 rounded-[18px] bg-[var(--surface-2)] border border-[var(--line)] px-8 py-8">
      <div className="flex flex-col md:flex-row justify-between gap-6">
        <Logo withText />
        <p className="text-[11px] text-[var(--ink-3)] max-w-xs leading-5">Pre-payment fraud tripwire for Medicare and Medicaid, built entirely on public federal data. No beneficiary data, no PHI, a human signs every action.</p>
      </div>
      <div className="grid grid-cols-3 gap-8 mt-10 max-w-md">
        {cols.map(([h, links]) => (
          <div key={h}><div className="text-[11px] font-medium mb-3">{h}</div>{links.map(([n, href]) => <Link key={n} href={href} className="block text-[11px] text-[var(--ink-3)] mb-2 hover:text-[var(--ink)]">{n}</Link>)}</div>
        ))}
      </div>
      <div className="flex justify-between items-center mt-10 text-[10px] text-[var(--ink-3)]"><span>All rights reserved 2026 · Verity · DNHacks</span><span>Built on DuckDB, Supabase and Next.js</span></div>
    </footer>
  );
}
