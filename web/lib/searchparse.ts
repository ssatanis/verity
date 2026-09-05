// Parse a free-text provider query into a name, an optional state and an optional city: "mayo clinic rochester mn", "smith, john TX", "we care transport in overland park kansas".
const STATES: Record<string, string> = { alabama: "AL", alaska: "AK", arizona: "AZ", arkansas: "AR", california: "CA", colorado: "CO", connecticut: "CT", delaware: "DE", florida: "FL", georgia: "GA", hawaii: "HI", idaho: "ID", illinois: "IL", indiana: "IN", iowa: "IA", kansas: "KS", kentucky: "KY", louisiana: "LA", maine: "ME", maryland: "MD", massachusetts: "MA", michigan: "MI", minnesota: "MN", mississippi: "MS", missouri: "MO", montana: "MT", nebraska: "NE", nevada: "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY", "north carolina": "NC", "north dakota": "ND", ohio: "OH", oklahoma: "OK", oregon: "OR", pennsylvania: "PA", "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", tennessee: "TN", texas: "TX", utah: "UT", vermont: "VT", virginia: "VA", washington: "WA", "west virginia": "WV", wisconsin: "WI", wyoming: "WY", "district of columbia": "DC", "puerto rico": "PR" };
const ABBR = new Set(Object.values(STATES));
export type Parsed = { name: string; state?: string; city?: string; npi?: string };
export function parseQuery(raw: string): Parsed {
  let q = raw.trim().replace(/\s+/g, " ");
  const npi = q.match(/\b(\d{10})\b/)?.[1]; if (npi) return { name: "", npi };
  let state: string | undefined; let city: string | undefined;
  const lower = q.toLowerCase();
  for (const [full, ab] of Object.entries(STATES).sort((a, b) => b[0].length - a[0].length)) { const re = new RegExp(`(?:,\\s*|\\s+|^)${full}\\s*$`, "i"); if (re.test(lower)) { state = ab; q = q.replace(re, "").trim(); break; } }
  if (!state) { const m = q.match(/(?:,\s*|\s+)([A-Za-z]{2})\s*$/); if (m && ABBR.has(m[1].toUpperCase()) && q.replace(m[0], "").trim().length >= 2) { state = m[1].toUpperCase(); q = q.replace(m[0], "").trim(); } }
  // "name in city" or "name, city"
  const inM = q.match(/^(.*?)\s+in\s+([A-Za-z .'-]{2,})$/i); if (inM) { q = inM[1].trim(); city = inM[2].trim(); }
  else { const parts = q.split(",").map(x => x.trim()).filter(Boolean); if (parts.length >= 2 && parts[parts.length - 1].split(" ").length <= 3 && parts.length <= 3) { city = parts.pop(); q = parts.join(", "); } }
  return { name: q.replace(/[^\w &'.,-]/g, " ").replace(/\s+/g, " ").trim(), state, city: city ? city.replace(/\b\w/g, c => c.toUpperCase()) : undefined };
}
