import { NextResponse } from "next/server";
import { publicClient } from "@/lib/supabase";
import { nppesRaw } from "@/lib/nppes";
import { NPI_RE } from "@/lib/validate";
// The Chrome extension's door into the platform. Read only, public data only, and answered with CORS headers so the
// extension can call it from any origin. Three modes:
//   ?ping=1                                  liveness plus the size of the scored table
//   ?mode=resolve&first=&last=&state=&city=  (or &org=) raw CMS registry records for a name, with the risk rows for them
//   ?npi=1234567890                          everything the provider page shows: registry record, risk row, flags, list rows, networks
export const dynamic = "force-dynamic";
const CORS = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS", "Access-Control-Allow-Headers": "Content-Type", "Cache-Control": "public, max-age=60" };
const json = (body: unknown, status = 200) => NextResponse.json(body, { status, headers: CORS });
export async function OPTIONS() { return new NextResponse(null, { status: 204, headers: CORS }); }
const clean = (v: string | null, max = 60) => String(v ?? "").replace(/[^A-Za-z0-9&'.,\- ]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);

export async function GET(req: Request) {
  const sp = new URL(req.url).searchParams; const sb = publicClient();
  if (sp.get("ping")) {
    const { count } = await sb.from("provider_risk").select("npi", { count: "exact", head: true });
    return json({ ok: true, service: "Verity console", rows: count ?? 0, version: 1 });
  }
  const npi = sp.get("npi");
  if (npi) {
    if (!NPI_RE.test(npi)) return json({ error: "not an NPI" }, 400);
    const [{ data: risk }, { data: flags }, { data: revoked }, { data: leie }, { data: members }, { data: provider }, reg] = await Promise.all([
      sb.from("provider_risk").select("*").eq("npi", npi).maybeSingle(),
      sb.from("flags").select("id,detector,metric,month,dollars,evidence").eq("npi", npi).order("month"),
      sb.from("revoked").select("*").eq("npi", npi), sb.from("leie").select("*").eq("npi", npi),
      sb.from("cluster_members").select("cluster_id, clusters(id,rank,score,summary)").eq("npi", npi),
      sb.from("providers").select("*").eq("npi", npi).maybeSingle(),
      nppesRaw({ number: npi, limit: "1" }).catch(() => [] as any[]),
    ]);
    return json({ npi, nppes: reg[0] ?? null, risk: risk ?? null, flags: flags ?? [], revoked: revoked ?? [], leie: leie ?? [], members: members ?? [], provider: provider ?? null });
  }
  if (sp.get("mode") === "resolve") {
    const first = clean(sp.get("first"), 40), last = clean(sp.get("last"), 60), org = clean(sp.get("org"), 80), city = clean(sp.get("city"), 40);
    const st = clean(sp.get("state"), 2).toUpperCase(); const state = /^[A-Z]{2}$/.test(st) ? st : "";
    const lim = "200"; const plans: Record<string, string>[] = [];
    if (org.length >= 2) {
      plans.push({ organization_name: `${org}*`, state, limit: lim }); if (state) plans.push({ organization_name: `${org}*`, limit: lim });
      const short = org.split(" ").slice(0, 2).join(" "); if (short !== org && short.length >= 4) plans.push({ organization_name: `${short}*`, state, limit: lim });
    } else if (last.length >= 2) {
      const f = first.replace(/[^A-Za-z'\-]/g, ""); const fq = f.length >= 2 ? `${f}*` : "";
      if (city && state) plans.push({ last_name: last, first_name: fq, city, state, limit: lim });
      plans.push({ last_name: last, first_name: fq, state, limit: lim });
      if (state) plans.push({ last_name: last, first_name: fq, limit: lim });
      if (!fq && city) plans.push({ last_name: last, city, limit: lim });
      if (/[- ]/.test(last)) for (const part of last.split(/[- ]+/)) if (part.length >= 3) plans.push({ last_name: part, first_name: fq, state, limit: lim });
      if (fq && state) plans.push({ last_name: last, state, limit: lim });
    } else return json({ error: "give a last name or an organization name" }, 400);
    const settled = await Promise.allSettled(plans.slice(0, 6).map(p => nppesRaw(p)));
    const seen = new Map<string, any>();
    for (const s of settled) if (s.status === "fulfilled") for (const r of s.value) if (r?.number && !seen.has(String(r.number))) seen.set(String(r.number), r);
    const ids = [...seen.keys()].slice(0, 150);
    const risk: Record<string, any> = {}; const lists = { revoked: [] as string[], leie: [] as string[] };
    if (ids.length) {
      const [{ data: rs }, { data: rv }, { data: le }] = await Promise.all([
        sb.from("provider_risk").select("npi,name,tier,tier_label,score,rank,dollars_at_risk,detectors").in("npi", ids),
        sb.from("revoked").select("npi").in("npi", ids), sb.from("leie").select("npi").in("npi", ids),
      ]);
      for (const r of rs ?? []) risk[r.npi] = r; lists.revoked = [...new Set((rv ?? []).map(r => r.npi))]; lists.leie = [...new Set((le ?? []).map(r => r.npi))];
    }
    return json({ results: [...seen.values()], risk, lists, plans: plans.length });
  }
  return json({ error: "pass ping=1, npi=, or mode=resolve" }, 400);
}
