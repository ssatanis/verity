import { createClient } from "@supabase/supabase-js";

// Public read client (row-level security allows select on every table). Safe on the server and in the browser.
export function publicClient() {
  return createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY!, { auth: { persistSession: false } });
}
// Server-only writer (packets, reviews). Never import from a client component.
export function serviceClient() {
  const key = process.env.SUPABASE_SECRET_KEY;
  if (!key) throw new Error("SUPABASE_SECRET_KEY is not set");
  return createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, key, { auth: { persistSession: false } });
}
export const money = (v: number | null | undefined, digits = 1) => {
  const n = Number(v ?? 0);
  if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(digits)}B`;
  if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(digits)}M`;
  if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
};
export const num = (v: number | null | undefined) => Number(v ?? 0).toLocaleString("en-US");
