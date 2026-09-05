// CMS NPPES NPI Registry API, version 2.1 (public, no key, refreshed daily). Up to 200 results per request.
// https://npiregistry.cms.hhs.gov/api/?version=2.1
const BASE = "https://npiregistry.cms.hhs.gov/api/?version=2.1";
export type NppesRecord = {
  npi: string; entity_type: "1" | "2"; name: string; credential?: string; status?: string; enumeration_date?: string; last_updated?: string; deactivation_date?: string; deactivation_reason?: string; reactivation_date?: string;
  organization_name?: string; first_name?: string; last_name?: string; authorized_official?: string; sole_proprietor?: string;
  practice?: { address_1?: string; address_2?: string; city?: string; state?: string; postal_code?: string; telephone?: string; fax?: string };
  mailing?: { address_1?: string; address_2?: string; city?: string; state?: string; postal_code?: string; telephone?: string };
  taxonomies: { code: string; desc: string; primary: boolean; state?: string; license?: string }[];
  other_names: string[]; identifiers: { issuer?: string; identifier?: string; state?: string }[];
  city?: string; state?: string; taxonomy?: string;
};
function pick(r: any): NppesRecord {
  const b = r.basic ?? {}; const addrs: any[] = r.addresses ?? [];
  const loc = addrs.find(a => a.address_purpose === "LOCATION") ?? addrs[0] ?? {}; const mail = addrs.find(a => a.address_purpose === "MAILING") ?? {};
  const isOrg = r.enumeration_type === "NPI-2";
  const name = isOrg ? (b.organization_name ?? "") : [b.first_name, b.middle_name, b.last_name].filter(Boolean).join(" ") + (b.credential ? `, ${b.credential}` : "");
  const tax = (r.taxonomies ?? []).map((t: any) => ({ code: t.code, desc: t.desc, primary: !!t.primary, state: t.state, license: t.license }));
  const primary = tax.find((t: any) => t.primary) ?? tax[0];
  const fmtZip = (z?: string) => (z && z.length === 9 ? `${z.slice(0, 5)}-${z.slice(5)}` : z);
  return {
    npi: String(r.number), entity_type: isOrg ? "2" : "1", name: name.trim(), credential: b.credential, status: b.status === "A" ? "active" : b.status === "D" ? "deactivated" : b.status,
    enumeration_date: b.enumeration_date, last_updated: b.last_updated, deactivation_date: b.deactivation_date, deactivation_reason: b.deactivation_reason_code, reactivation_date: b.reactivation_date,
    organization_name: b.organization_name, first_name: b.first_name, last_name: b.last_name, sole_proprietor: b.sole_proprietor,
    authorized_official: isOrg ? [b.authorized_official_first_name, b.authorized_official_last_name].filter(Boolean).join(" ") + (b.authorized_official_title_or_position ? ` (${b.authorized_official_title_or_position})` : "") : undefined,
    practice: { address_1: loc.address_1, address_2: loc.address_2, city: loc.city, state: loc.state, postal_code: fmtZip(loc.postal_code), telephone: loc.telephone_number, fax: loc.fax_number },
    mailing: { address_1: mail.address_1, address_2: mail.address_2, city: mail.city, state: mail.state, postal_code: fmtZip(mail.postal_code), telephone: mail.telephone_number },
    taxonomies: tax, other_names: (r.other_names ?? []).map((o: any) => o.organization_name ?? [o.first_name, o.last_name].filter(Boolean).join(" ")).filter(Boolean),
    identifiers: (r.identifiers ?? []).map((i: any) => ({ issuer: i.issuer ?? i.desc, identifier: i.identifier, state: i.state })),
    city: loc.city ? String(loc.city).replace(/\b\w+/g, (w: string) => w[0] + w.slice(1).toLowerCase()) : undefined, state: loc.state, taxonomy: primary?.code,
  };
}
async function call(params: Record<string, string>): Promise<NppesRecord[]> {
  const u = new URL(BASE); for (const [k, v] of Object.entries(params)) if (v) u.searchParams.set(k, v);
  const r = await fetch(u.toString(), { next: { revalidate: 3600 }, signal: AbortSignal.timeout(8000), headers: { Accept: "application/json" } });
  if (!r.ok) return [];
  const j = await r.json(); if (!Array.isArray(j.results)) return [];
  return j.results.map(pick);
}
// Raw registry results for a query, untouched, for callers that normalize themselves (the Chrome extension route).
export async function nppesRaw(params: Record<string, string>): Promise<any[]> {
  const u = new URL(BASE); for (const [k, v] of Object.entries(params)) if (v) u.searchParams.set(k, v);
  const r = await fetch(u.toString(), { next: { revalidate: 600 }, signal: AbortSignal.timeout(9000), headers: { Accept: "application/json" } });
  if (!r.ok) return [];
  const j = await r.json(); return Array.isArray(j.results) ? j.results : [];
}
export async function nppesLookup(npi: string): Promise<NppesRecord | null> {
  if (!/^\d{10}$/.test(npi)) return null;
  try { const rs = await call({ number: npi, limit: "1" }); return rs[0] ?? null; } catch { return null; }
}
// Name search: organizations by name prefix, individuals by last name (and first name when two words are typed). NPI prefixes are not supported by the registry, so only a full number is looked up.
export async function nppesSearch(q: string, limit = 12): Promise<NppesRecord[]> {
  const term = q.trim(); if (term.length < 2) return [];
  if (/^\d{10}$/.test(term)) { const r = await nppesLookup(term); return r ? [r] : []; }
  if (/^\d+$/.test(term)) return [];
  const lim = String(Math.min(50, Math.max(1, limit)));
  const words = term.replace(/[^A-Za-z0-9&'.,\- ]/g, "").split(/\s+/).filter(Boolean);
  const tasks: Promise<NppesRecord[]>[] = [call({ organization_name: `${term}*`, limit: lim })];
  if (words.length >= 2) { tasks.push(call({ first_name: `${words[0]}*`, last_name: `${words[words.length - 1]}*`, use_first_name_alias: "False", limit: lim })); tasks.push(call({ last_name: `${words[0]}*`, first_name: `${words[words.length - 1]}*`, use_first_name_alias: "False", limit: lim })); }
  else tasks.push(call({ last_name: `${words[0]}*`, limit: lim }));
  const settled = await Promise.allSettled(tasks); const out: NppesRecord[] = []; const seen = new Set<string>();
  for (const s of settled) if (s.status === "fulfilled") for (const r of s.value) if (!seen.has(r.npi)) { seen.add(r.npi); out.push(r); }
  return out.slice(0, limit);
}

// Name search with optional city and state, for queries such as "mayo clinic rochester mn".
export async function nppesSearchIn(name: string, city?: string, state?: string, limit = 12): Promise<NppesRecord[]> {
  const term = name.trim(); if (term.length < 2) return [];
  const lim = String(Math.min(50, Math.max(1, limit))); const loc: Record<string, string> = {}; if (city) loc.city = city; if (state) loc.state = state;
  const words = term.replace(/[^A-Za-z0-9&'.,\- ]/g, "").split(/\s+/).filter(Boolean);
  const tasks: Promise<NppesRecord[]>[] = [call({ organization_name: `${term}*`, limit: lim, ...loc })];
  if (words.length >= 2) { tasks.push(call({ first_name: `${words[0]}*`, last_name: `${words[words.length - 1]}*`, use_first_name_alias: "False", limit: lim, ...loc })); tasks.push(call({ last_name: `${words[0]}*`, first_name: `${words[words.length - 1]}*`, use_first_name_alias: "False", limit: lim, ...loc })); }
  else tasks.push(call({ last_name: `${words[0]}*`, limit: lim, ...loc }));
  const settled = await Promise.allSettled(tasks); const out: NppesRecord[] = []; const seen = new Set<string>();
  for (const s of settled) if (s.status === "fulfilled") for (const r of s.value) if (!seen.has(r.npi)) { seen.add(r.npi); out.push(r); }
  return out.slice(0, limit);
}
