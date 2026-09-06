// The enforcement feed as the console shows it: DOJ press releases and HHS-OIG enforcement actions, refreshed daily by
// scripts/enforcement_daily.sh, published to public.enforcement, with web/public/fallback/enforcement.json behind it.
import { publicClient } from "./supabase";
import { withFallback } from "./fallback";
import { titleCase } from "./labels";

export type Release = {
  id: string; source: string; title: string; published: string; url: string; district?: string | null; state?: string | null;
  action_type?: string | null; tier?: string | null; programs?: string | null; scheme?: string | null;
  dollars_alleged?: number | null; dollars_ordered?: number | null; action_date?: string | null; body?: string | null; npis?: string[] | null; image_url?: string | null;
};
export const LIST_COLS = "id,source,title,published,url,district,state,action_type,tier,programs,scheme,dollars_alleged,dollars_ordered,action_date,npis,image_url";

export const sourceLabel = (s?: string | null) => (s === "DOJ" ? "Department of Justice" : s === "OIG" ? "HHS Office of Inspector General" : s ?? "");
export const sourceShort = (s?: string | null) => (s === "DOJ" ? "DOJ" : s === "OIG" ? "HHS-OIG" : s ?? "");
// Action types come out of the extraction step as single lower-case words; read them as a reviewer would say them.
const ACTION: Record<string, string> = { indicted: "Indicted", charged: "Charged", arrested: "Arrested", pleaded: "Pleaded guilty", guilty: "Found guilty", convicted: "Convicted", sentenced: "Sentenced", settled: "Settled", settlement: "Settled", excluded: "Excluded", judgment: "Judgment entered", civil: "Civil action", complaint: "Complaint filed", "pleaded guilty": "Pleaded guilty", "found guilty": "Found guilty", "civil settlement": "Civil settlement" };
export const actionLabel = (a?: string | null) => { if (!a) return ""; const k = String(a).toLowerCase().replace(/_/g, " ").trim(); return ACTION[k] ?? k[0].toUpperCase() + k.slice(1); };
export const districtLabel = (d?: string | null) => String(d ?? "").replace(/USAO - /g, "U.S. Attorney's Office, ").replace(/^OPA$/, "Office of Public Affairs");
// The release body is one block of text. Break it into paragraphs at blank lines when the feed kept them, otherwise every
// three sentences, so a reader is never faced with a wall.
export function paragraphs(body?: string | null): string[] {
  const text = String(body ?? "").replace(/\r/g, "").trim();
  if (!text) return [];
  const byBlank = text.split(/\n\s*\n/).map(x => x.replace(/\s+/g, " ").trim()).filter(Boolean);
  if (byBlank.length > 1) return byBlank;
  const sentences = text.replace(/\s+/g, " ").split(/(?<=[.!?])\s+(?=[A-Z"“(])/);
  const out: string[] = []; for (let i = 0; i < sentences.length; i += 3) out.push(sentences.slice(i, i + 3).join(" "));
  return out;
}
export const npiList = (v: any): string[] => { const x = typeof v === "string" ? (() => { try { return JSON.parse(v); } catch { return []; } })() : v; return Array.isArray(x) ? x.map(String) : []; };
export const placeLabel = (r: Release) => [r.district ? districtLabel(r.district) : null, r.state].filter(Boolean).join(", ");
export const cityOf = (city?: string | null) => titleCase(city);

// The newest releases, optionally for one state or matching a search, from the live table or the static file.
export async function listReleases(opts: { state?: string; q?: string; limit?: number; offset?: number } = {}): Promise<Release[]> {
  const { state, q, limit = 60, offset = 0 } = opts; const sb = publicClient();
  const rows = await withFallback<Release[]>("enforcement", () => {
    let qq = sb.from("enforcement").select(LIST_COLS).order("published", { ascending: false }).range(offset, offset + limit - 1);
    if (state) qq = qq.eq("state", state);
    if (q) qq = qq.or(`title.ilike.%${q.replace(/[%,()]/g, " ")}%,scheme.ilike.%${q.replace(/[%,()]/g, " ")}%`);
    return qq;
  }, rows => rows.filter((r: any) => (!state || r.state === state) && (!q || `${r.title} ${r.scheme ?? ""}`.toLowerCase().includes(q.toLowerCase()))).slice(offset, offset + limit));
  return rows ?? [];
}
export async function getRelease(id: string): Promise<Release | null> {
  const sb = publicClient();
  const rows = await withFallback<Release[]>("enforcement", () => sb.from("enforcement").select("*").eq("id", id).limit(1), rows => rows.filter((r: any) => r.id === id));
  return rows?.[0] ?? null;
}
// State counts for the filter chips.
export async function releaseStates(): Promise<[string, number][]> {
  const sb = publicClient();
  const rows = await withFallback<{ state: string | null }[]>("enforcement", () => sb.from("enforcement").select("state").not("state", "is", null).limit(5000), rows => rows.map((r: any) => ({ state: r.state })));
  const counts: Record<string, number> = {}; for (const r of rows ?? []) if (r.state) counts[r.state] = (counts[r.state] ?? 0) + 1;
  return Object.entries(counts).sort((a, b) => b[1] - a[1]);
}
