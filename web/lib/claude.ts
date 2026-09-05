import Anthropic from "@anthropic-ai/sdk";
export const MODEL = process.env.VERITY_MODEL ?? "claude-opus-5";
export function claudeReady() { return (process.env.ANTHROPIC_API_KEY ?? "").startsWith("sk-ant-"); }
export function claude() { return new Anthropic(); }
// House style: no em or en dashes anywhere the model writes.
export function cleanText<T>(v: T): T {
  if (typeof v === "string") return (v.replace(/—/g, ", ").replace(/–/g, " to ").replace(/\s+,/g, ",") as unknown) as T;
  if (Array.isArray(v)) return v.map(cleanText) as unknown as T;
  if (v && typeof v === "object") return Object.fromEntries(Object.entries(v as any).map(([k, x]) => [k, cleanText(x)])) as T;
  return v;
}
