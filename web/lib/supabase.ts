import { createClient } from "@supabase/supabase-js";

// Public read client (row-level security allows select on every table). Safe on the server and in the browser.
// If the keys are missing (a preview deploy without environment variables) the client points at a placeholder host; every
// query then fails and withFallback serves the static JSON in web/public/fallback, so the site still renders.
// The project's own variables are named SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY in the hosting environment, and
// NEXT_PUBLIC_* locally. Both clients run only on the server, so either name works; reading both is what keeps a deploy
// from silently falling through to the static JSON because of a naming mismatch.
const SUPABASE_URL = () => process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL || "";
const SUPABASE_PUBLISHABLE_KEY = () => process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.SUPABASE_PUBLISHABLE_KEY || "";
// True when a live database is configured at all; callers use it to tell "no rows" from "no connection".
export function supabaseConfigured() { return !!SUPABASE_URL() && !!SUPABASE_PUBLISHABLE_KEY(); }
export function publicClient() {
  const url = SUPABASE_URL() || "https://placeholder.supabase.co";
  const key = SUPABASE_PUBLISHABLE_KEY() || "missing";
  return createClient(url, key, { auth: { persistSession: false } });
}
// Server-only writer (packets, reviews). Never import from a client component.
export function serviceClient() {
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!key) throw new Error("SUPABASE_SECRET_KEY is not set");
  const url = SUPABASE_URL();
  if (!url) throw new Error("SUPABASE_URL (or NEXT_PUBLIC_SUPABASE_URL) is not set");
  return createClient(url, key, { auth: { persistSession: false } });
}
export const money = (v: number | null | undefined, digits = 1) => {
  const n = Number(v ?? 0);
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(digits)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(digits)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};
export const num = (v: number | null | undefined) => Number(v ?? 0).toLocaleString("en-US");
