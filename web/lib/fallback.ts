import { promises as fs } from "fs";
import path from "path";
// Static fallback (web/public/fallback/*.json, written by scripts/export_static.py) so the console still renders when Supabase is paused or over budget.
export async function withFallback<T>(name: string, query: () => PromiseLike<{ data: T | null; error: any }>, pick?: (rows: any[]) => T): Promise<T | null> {
  // An empty array counts as a miss, not a success: a misconfigured key or a blocked row makes a query return [] rather
  // than an error, and returning that empty result is what puts zeroes on the page instead of the static fallback.
  try { const { data, error } = await query(); if (!error && data != null && !(Array.isArray(data) && data.length === 0)) return data; } catch {}
  try { const raw = await fs.readFile(path.join(process.cwd(), "public", "fallback", `${name}.json`), "utf8"); const rows = JSON.parse(raw); return pick ? pick(rows) : (rows as T); } catch { return null; }
}
