import { NextResponse } from "next/server";
import { serviceClient } from "@/lib/supabase";
// Search every provider: the serving tables first (providers with indicators), then the full NPPES index through the local API when it is reachable.
const API = process.env.VERITY_API_URL ?? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
export async function GET(req: Request) {
  const q = (new URL(req.url).searchParams.get("q") ?? "").trim(); if (q.length < 2) return NextResponse.json({ hits: [] });
  const sb = serviceClient(); const isNpi = /^\d{2,10}$/.test(q); const hits: any[] = []; const seen = new Set<string>();
  const push = (r: any, source: string) => { if (r?.npi && !seen.has(r.npi)) { seen.add(r.npi); hits.push({ npi: r.npi, name: r.name, city: r.city, state: r.state, entity_type: r.entity_type, tier: r.tier ?? null, source }); } };
  const [{ data: risk }, { data: prov }] = await Promise.all([
    isNpi ? sb.from("provider_risk").select("npi,name,city,state,entity_type,tier").like("npi", `${q}%`).order("rank").limit(8) : sb.from("provider_risk").select("npi,name,city,state,entity_type,tier").ilike("name", `${q}%`).order("rank").limit(8),
    isNpi ? sb.from("providers").select("npi,name,city,state,entity_type").like("npi", `${q}%`).limit(8) : sb.from("providers").select("npi,name,city,state,entity_type").ilike("name", `${q}%`).limit(8),
  ]);
  for (const r of risk ?? []) push(r, "risk"); for (const r of prov ?? []) push(r, "providers");
  if (API && hits.length < 10) {
    try { const r = await fetch(`${API}/search?q=${encodeURIComponent(q)}&limit=10`, { signal: AbortSignal.timeout(4000) }); if (r.ok) { const j = await r.json(); for (const h of j.hits ?? []) push(h, "nppes"); } } catch {}
  }
  return NextResponse.json({ hits: hits.slice(0, 12), full_index: !!API });
}
