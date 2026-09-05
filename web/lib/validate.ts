// Request validation shared by the console routes. Every route reads JSON through readJson (which never throws) and checks
// identifiers against fixed patterns before touching the database or the model.
export const NPI_RE = /^\d{10}$/;
export const CLUSTER_RE = /^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$/;
export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export type Subject = "cluster" | "provider";
export async function readJson(req: Request): Promise<Record<string, any> | null> {
  try { const j = await req.json(); return j && typeof j === "object" && !Array.isArray(j) ? j : null; } catch { return null; }
}
export function subjectOk(subject_type: unknown, subject_id: unknown): subject_type is Subject {
  if (typeof subject_id !== "string") return false;
  if (subject_type === "provider") return NPI_RE.test(subject_id);
  if (subject_type === "cluster") return CLUSTER_RE.test(subject_id);
  return false;
}
export const str = (v: unknown, max: number, fallback = ""): string => (typeof v === "string" ? v.slice(0, max) : fallback);
export function chatHistory(h: unknown): { role: "user" | "assistant"; content: string }[] {
  if (!Array.isArray(h)) return [];
  return h.filter(m => m && typeof m === "object" && (m.role === "user" || m.role === "assistant") && typeof m.content === "string" && m.content.trim())
    .slice(-8).map(m => ({ role: m.role as "user" | "assistant", content: String(m.content).slice(0, 8000) }));
}
