import Anthropic from "@anthropic-ai/sdk";
export const MODEL = process.env.VERITY_MODEL ?? "claude-sonnet-5";
export function claudeReady() { return (process.env.ANTHROPIC_API_KEY ?? "").startsWith("sk-ant-"); }
export function claude() { return new Anthropic(); }
// The house style every model-written surface shares. Referral packets are read by investigators and quoted in files, so
// the writing has to be plain and checkable: one fact to a sentence, a full stop after each, and nothing stacked into a
// clause chain a reader has to unpick.
export const STYLE = `Write in short, plain sentences.
- One fact per sentence. End every sentence with a full stop. Never run two facts together with "and that", "which together", "with", or a trailing "which".
- Keep sentences under 25 words. If a sentence carries a date, a dollar figure and a citation, split it into two or three sentences.
- Give each figure its own sentence when it needs context. Do not stack parentheses: at most one short parenthetical in a sentence, and never a parenthetical inside another.
- Order the facts: what the record is, then the date, then the amount, then what follows from it.
- No em dashes, no en dashes, no underscores, no semicolon chains, no bullet fragments inside a paragraph, no code-like identifiers. Write list names and reasons in words.
- Cite regulations as 42 CFR 424.535(a)(9), with lower-case subsection letters. Write dates as July 31, 2020. Write amounts as $2,389,353.
Example of what to avoid: "Public records show X was placed on the list on July 31, 2020 under 42 CFR 424.535(A)(9) Failure To Report, with a bar to 2030, and that Medicaid paid $2,389,353 across 9 months after that date."
Example of the same facts done right: "Medicare revoked this provider on July 31, 2020 under 42 CFR 424.535(a)(9), failure to report. The bar on re-enrolling runs to July 31, 2030. Delaware Medicaid then paid $2,389,353 across 9 service months, from August 2020 to April 2021."`;

// House style: no em or en dashes anywhere the model writes.
export function cleanText<T>(v: T): T {
  if (typeof v === "string") return (v.replace(/—/g, ", ").replace(/–/g, " to ").replace(/\s+,/g, ",").replace(/[ \t]{2,}/g, " ") as unknown) as T;
  if (Array.isArray(v)) return v.map(cleanText) as unknown as T;
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v as any).map(([k, x]) => [k, cleanText(x)])) as T;
  return v;
}
