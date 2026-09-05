import { promises as fs } from "fs";
import path from "path";
// Static fallback (web/public/fallback/*.json, written by scripts/export_static.py) so the console still renders when Supabase is paused or over budget.
export async function withFallback<T>(name: string, query: () => Promise<{ data: T | null; error: any }>, pick?: (rows: any[]) => T): Promise<T | null> {
  try { const { data, error } = await query(); if (!error && data != null) return data; } catch {}
  try { const raw = await fs.readFile(path.join(process.cwd(), "public", "fallback", `${name}.json`), "utf8"); const rows = JSON.parse(raw); return pick ? pick(rows) : (rows as T); } catch { return null; }
}
