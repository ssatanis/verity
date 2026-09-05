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
