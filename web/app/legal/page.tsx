import { Nav } from "@/components/landing/Nav";
import { Footer } from "@/components/landing/Footer";
export const metadata = { title: "Verity: terms, privacy and security" };
const W = "max-w-[1860px] mx-auto px-8 md:px-[72px]";
export default function Legal() {
  const sections = [
    ["terms", "Terms and Conditions", [
      "Verity is a screening product built on public federal and state datasets. Every row in the console is an indicator for a human reviewer to verify against the cited source records. Nothing in the console, a packet or the case chat is a finding of fraud, abuse or intent, and nothing may be represented as one.",
      "Access to the console is limited to reviewers who have agreed to treat every row as an indicator, to verify the cited records before any action, and not to publish or redistribute rows that name a provider.",
      "Regulatory citations are provided to orient a reviewer to the applicable screening and enrollment rules (42 CFR Parts 455, 1001 and 424). They are not legal advice. Payment suspension and enrollment actions are decisions of the responsible state agency or health plan under their own procedures.",
    ]],
    ["privacy", "Privacy Policy", [
      "Verity processes provider-level public records only: enrollment, ownership, exclusion, revocation and aggregate spending files published by CMS, HHS OIG, SAM.gov, NPPES, the Census Bureau and state Medicaid agencies. It holds no beneficiary data, no claim lines and no protected health information.",
      "The console stores reviewer decisions and notes to improve the ranking. Notes are classified by an automated model into an evidence family; the note text is retained for audit and is visible to other reviewers of the same packet.",
      "Contact ss4497@cornell.edu for questions about the data, to request the removal of a row that names you or your organisation, or to correct a record.",
    ]],
    ["security", "Security", [
      "The console sits behind a reviewer sign in. Packets are stored in a private bucket. The case chat can only call read-only evidence tools over the serving tables, and every model output is validated against the evidence list before it is shown.",
      "The warehouse rebuilds from public files in minutes and can run entirely inside a customer's own environment. No customer data is sent to a model provider; only public evidence rows are.",
      "Report a security concern to ss4497@cornell.edu.",
    ]],
  ] as const;
  return (
    <div className="min-h-screen bg-white">
      <Nav />
      <main className={`${W} py-20`}>
        <h1 className="display serif text-[54px] md:text-[72px]" style={{ color: "var(--blue)" }}>Terms, Privacy and Security</h1>
        {sections.map(([id, h, ps]) => <section key={id} id={id} className="mt-16 grid md:grid-cols-[1fr_3fr] gap-10"><h2 className="serif text-[32px]" style={{ color: "var(--blue)" }}>{h}</h2><div className="lrule pl-10 space-y-5 text-[15px] leading-7" style={{ color: "var(--ink-2)" }}>{ps.map((p, i) => <p key={i}>{p}</p>)}</div></section>)}
      </main>
      <Footer />
    </div>
  );
}
