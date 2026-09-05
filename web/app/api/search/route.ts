import { NextResponse } from "next/server";
import { serviceClient } from "@/lib/supabase";
import { nppesSearch, nppesSearchIn } from "@/lib/nppes";
import { parseQuery } from "@/lib/searchparse";
// Answered with CORS headers so the Chrome extension can search from any origin (read only, public data).
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" };
const ok = (b: unknown) => NextResponse.json(b, { headers: CORS });
export async function OPTIONS() { return new NextResponse(null, { status: 204, headers: CORS }); }
// Search every provider. Understands "name city state": exact prefix first, then trigram similarity over the serving tables, then the CMS registry with city and state filters.
export async function GET(req: Request) {
  const raw = (new URL(req.url).searchParams.get("q") ?? "").trim(); if (raw.length < 2) return ok({ hits: [] });
  const P = parseQuery(raw); const sb = serviceClient(); const hits: any[] = []; const seen = new Set<string>();
  const push = (r: any, source: string, sim?: number) => { if (r?.npi && !seen.has(r.npi)) { seen.add(r.npi); hits.push({ npi: r.npi, name: r.name, city: r.city, state: r.state, entity_type: r.entity_type, tier: r.tier ?? null, source, sim }); } };
  if (P.npi) {
    const [{ data: risk }, { data: prov }] = await Promise.all([sb.from("provider_risk").select("npi,name,city,state,entity_type,tier").eq("npi", P.npi), sb.from("providers").select("npi,name,city,state,entity_type").eq("npi", P.npi)]);
    for (const r of risk ?? []) push(r, "risk"); for (const r of prov ?? []) push(r, "providers");
    if (!hits.length) { try { for (const r of await nppesSearch(P.npi, 1)) push(r, "nppes"); } catch {} }
    return ok({ hits, parsed: P });
  }
  const isNpiPrefix = /^\d{2,9}$/.test(raw);
  if (isNpiPrefix) {
    const [{ data: risk }, { data: prov }] = await Promise.all([sb.from("provider_risk").select("npi,name,city,state,entity_type,tier").like("npi", `${raw}%`).order("rank").limit(8), sb.from("providers").select("npi,name,city,state,entity_type").like("npi", `${raw}%`).limit(8)]);
    for (const r of risk ?? []) push(r, "risk"); for (const r of prov ?? []) push(r, "providers");
    return ok({ hits: hits.slice(0, 12), parsed: P });
  }
  const name = P.name; if (name.length < 2) return ok({ hits: [], parsed: P });
  // 1. exact prefix on the serving tables (with state and city when given)
  let q1 = sb.from("provider_risk").select("npi,name,city,state,entity_type,tier").ilike("name", `${name}%`).order("rank").limit(8); if (P.state) q1 = q1.eq("state", P.state); if (P.city) q1 = q1.ilike("city", `${P.city}%`);
  let q2 = sb.from("providers").select("npi,name,city,state,entity_type").ilike("name", `${name}%`).limit(8); if (P.state) q2 = q2.eq("state", P.state); if (P.city) q2 = q2.ilike("city", `${P.city}%`);
  const [{ data: risk }, { data: prov }] = await Promise.all([q1, q2]);
  for (const r of risk ?? []) push(r, "risk", 1); for (const r of prov ?? []) push(r, "providers", 1);
  // 2. trigram similarity: misspellings, word order, partial names
  try { const { data: fz } = await sb.rpc("search_providers", { q: name, st: P.state ?? null, ct: P.city ?? null, lim: 10 }); for (const r of fz ?? []) push(r, "fuzzy", Number(r.sim)); } catch {}
  // 3. the national registry, filtered by city and state when given
  if (hits.length < 12) { try { for (const r of await nppesSearchIn(name, P.city, P.state, 10)) push(r, "nppes"); } catch {} }
  hits.sort((a, b) => (b.sim ?? 0.5) - (a.sim ?? 0.5) || (a.tier ?? 9) - (b.tier ?? 9));
  return ok({ hits: hits.slice(0, 14), parsed: P });
}
