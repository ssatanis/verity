// Plain-language names for detector codes shown in the console. No identifiers with underscores reach the screen.
export const SOURCE: Record<string, string> = {
  MEDICARE_REVOKED: "Medicare revocation list", OIG_LEIE: "OIG exclusion list", NPPES_DEACTIVATED: "Deactivated NPI", TMSIS_DECEASED: "State file: provider deceased",
};
export function sourceName(s?: string | null): string {
  if (!s) return "";
  return s.split(",").map(x => SOURCE[x] ?? (x.startsWith("STATE_EXCL_") ? `${x.slice(11)} Medicaid exclusion list` : x.startsWith("SAM_") ? `SAM.gov exclusion (${x.slice(4).replace(/_/g, " ")})` : x.startsWith("TMSIS_TERM_") ? "State Medicaid termination" : x.endsWith("_NAME") ? `${sourceName(x.slice(0, -5))}, matched by name` : x.replace(/_/g, " ").toLowerCase())).join(", ");
}
export const LABEL: Record<string, string> = {
  IMPOSSIBLE_BY_LINE_COUNT: "More hours than a day holds, even counting one unit per claim line",
  IMPOSSIBLE_CONSERVATIVE_RATE: "More hours than a day holds at a conservative unit price",
  IMPOSSIBLE_PER_PATIENT: "More than 24 hours per patient per day",
  EXCEEDS_MN_DAILY_CAP: "Over the state's daily cap for every patient every day",
  IMPLAUSIBLE_OVER_16H: "Over 16 hours per day",
  ELEVATED_OVER_12H: "Over 12 hours per day",
  UMBRELLA_VOLUME: "Agency volume billed under one clinician's NPI",
  GROWTH_ANOMALY: "New biller with rapid growth concentrated on one code",
};
export const IDMATCH: Record<string, string> = {
  exact_npi_name_verified: "Exact NPI, name verified", exact_npi_not_in_nppes: "Exact NPI, no NPPES record", exact_npi_unnamed_source: "Exact NPI, list gives no name",
  exact_npi_name_conflict: "Exact NPI, name conflict (set aside)", name_match_model_high: "No NPI on the list; matched by name at high confidence",
};
export const labelName = (l?: string | null) => (l ? LABEL[l] ?? l.replace(/_/g, " ").toLowerCase() : "");
export const idMatchName = (l?: string | null) => (l ? IDMATCH[l] ?? l.replace(/_/g, " ") : "");
export const TIER_LABEL: Record<number, string> = { 1: "Documented action, then payment", 2: "Impossible volume with concurrency", 3: "Network structure with a list link", 4: "Structure, or single-organization volume", 5: "Informational" };
export const money = (v: number | null | undefined, digits = 1) => { const n = Number(v ?? 0); if (Math.abs(n) >= 1e9) return `$${(n / 1e9).toFixed(digits)}B`; if (Math.abs(n) >= 1e6) return `$${(n / 1e6).toFixed(digits)}M`; if (Math.abs(n) >= 1e3) return `$${(n / 1e3).toFixed(0)}K`; return `$${n.toFixed(0)}`; };

export const ordinal = (n: number) => { const v = Math.round(n); const s = ["th", "st", "nd", "rd"], k = v % 100; return `${v}${s[(k - 20) % 10] ?? s[k] ?? s[0]}`; };
export const moneyExact = (v: number | null | undefined) => { const n = Number(v ?? 0); if (Math.abs(n) >= 1e3) return money(n); return n < 10 ? `$${n.toFixed(2)}` : `$${Math.round(n)}`; };

// Revocation grounds as they read on the page. The CMS file writes them in upper case with underscores and packs several
// grounds into one field, which is why they arrive looking like "424.535(A)(9) FAILURE_TO_REPORT;424.535(A)(3) FELONIES".
export function revocationReason(raw?: string | null): string {
  if (!raw) return "";
  return String(raw).split(";").map(part => part.replace(/_/g, " ").trim().toLowerCase()
    // subsection letters are lower case in the regulation itself
    .replace(/\((\w)\)/g, (_, c) => `(${String(c).toLowerCase()})`)
    // keep the citation itself upright, sentence-case the ground that follows it
    .replace(/^(\d[\d.]*(?:\([a-z0-9]\))*)\s+(.*)$/, (_, cite, rest) => `${cite} ${rest}`)
  ).filter(Boolean).join("; ");
}

// The reasons column arrives as one semicolon-joined string, which reads as a run-on wherever it is printed whole.
// Split it into the separate statements it actually is, each a sentence with a capital and a full stop. The warehouse
// writes "month(s)" and does not singularise a count of one, so both are repaired here for rows already published.
const grammar = (x: string) => x
  .replace(/\b(\d[\d,]*) ([a-z]+)\(s\)/g, (_, n: string, w: string) => `${n} ${Number(n.replace(/,/g, "")) === 1 ? w : w + "s"}`)
  .replace(/\b1 ((?:[a-z]+ )*?[a-z]+)s\b/g, (_, w: string) => `1 ${w}`);
export function reasonList(raw?: string | null): string[] {
  if (!raw) return [];
  return String(raw)
    .split(/\s*;\s*/)
    .map(x => grammar(x.trim().replace(/[.;,]+$/, "")))
    .filter(Boolean)
    .map(x => (/^[a-z]/.test(x) ? x[0].toUpperCase() + x.slice(1) : x) + ".");
}

// CMS files store places and descriptions in upper case, which shouts inside sentence-case UI. Title-case them for
// display while keeping the tokens that are genuinely upper case: company suffixes, initialisms and state codes.
const KEEP_UPPER = new Set(["LLC", "L.L.C.", "INC", "INC.", "PC", "P.C.", "PA", "P.A.", "LLP", "LP", "PLLC", "DBA", "USA", "US", "II", "III", "IV", "DME", "SNF", "HHA", "NPI", "OIG", "MD", "DO", "DDS", "DPM", "RN", "LPN", "EIN"]);
export function titleCase(raw?: string | null): string {
  if (!raw) return "";
  const s = String(raw);
  // Text that is already mixed case was written by a person; leave it alone.
  if (s !== s.toUpperCase()) return s;
  return s.toLowerCase().replace(/[A-Za-z][A-Za-z.\']*/g, w => {
    const up = w.toUpperCase();
    if (KEEP_UPPER.has(up)) return up;
    if (w.length <= 2 && !/^(a|an|at|by|in|of|on|or|to|up|as)$/i.test(w)) return up;
    return w[0].toUpperCase() + w.slice(1);
  });
}
