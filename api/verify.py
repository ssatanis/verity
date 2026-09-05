"""Verity NPI verification: one function that answers "should this provider have been paid on this date?"

Sources (all in the DuckDB warehouse built by ingest/): CMS Medicare revocations (`revoked`), OIG LEIE (`leie`), SAM.gov exclusions
(`sam`, from ingest/06_sam_exclusions.py), state Medicaid exclusion lists (`state_exclusions`), NPPES deactivations (`nppes`),
Medicaid deceased terminations (`enroll` status 80). Plus an optional live SAM.gov API lookup by name for entities SAM has no NPI for.
"""
import os, re, datetime as dt, urllib.parse, urllib.request, json
import duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.environ.get("VERITY_DUCKDB", os.path.join(ROOT, "data/verity.duckdb"))
NPI_RE = re.compile(r"^[12]\d{9}$")

_con = None
def con():
    global _con
    if _con is None:
        _con = duckdb.connect(DB, read_only=True)
    return _con

def _tables():
    return {r[0] for r in con().execute("SELECT table_name FROM information_schema.tables").fetchall()}

EVENT_SQL = {
 "revoked": """SELECT npi, 'MEDICARE_REVOKED' AS source, 'A' AS tier, revoked_dt AS event_dt, reenroll_bar_dt AS window_end,
                revocation_rsn AS reason, state, COALESCE(org_name, trim(COALESCE(first_name,'')||' '||COALESCE(last_name,''))) AS name, provider_type_desc AS detail
               FROM revoked WHERE npi IN ({npis}) AND revoked_dt IS NOT NULL""",
 "leie": """SELECT npi, 'OIG_LEIE', 'A', excl_dt, rein_dt, 'LEIE '||excltype||' ('||COALESCE(general,'')||')', state,
             COALESCE(NULLIF(busname,''), trim(COALESCE(firstname,'')||' '||COALESCE(lastname,''))), specialty
            FROM leie WHERE npi IN ({npis}) AND excl_dt IS NOT NULL AND waiver_dt IS NULL""",
 "sam": """SELECT npi, 'SAM_'||COALESCE(excluding_agency,'UNKNOWN'), CASE WHEN excluding_agency='HHS' THEN 'A' ELSE 'B' END, active_dt, termination_dt,
            exclusion_type||COALESCE(' / '||ct_code,''), state, COALESCE(name, trim(COALESCE(first_name,'')||' '||COALESCE(last_name,''))), classification
           FROM sam WHERE npi IN ({npis}) AND active_dt IS NOT NULL AND record_status='Active'""",
 "state_exclusions": """SELECT npi, 'STATE_EXCL_'||state, 'A', excl_dt, reinstated_dt, source, state, name, provider_type
                        FROM state_exclusions WHERE npi IN ({npis}) AND excl_dt IS NOT NULL""",
 "nppes": """SELECT npi, 'NPPES_DEACTIVATED', 'B', deact_date, react_date, 'NPI deactivated in NPPES', state,
              COALESCE(org_name, trim(COALESCE(first_name,'')||' '||COALESCE(last_name,''))), taxonomy
             FROM nppes WHERE npi IN ({npis}) AND deact_date IS NOT NULL AND (react_date IS NULL OR react_date <= deact_date)""",
 "enroll": """SELECT npi, 'TMSIS_DECEASED', 'A', MIN(start_dt), NULL::DATE, 'Medicaid enrollment terminated: provider deceased (status 80)', state, NULL, prvdr_type_desc
              FROM enroll WHERE npi IN ({npis}) AND status_cd='80' GROUP BY npi, state, prvdr_type_desc""",
}

def events_for(npis):
    """All should-not-be-paid events for a set of NPIs, from every source table that exists."""
    npis = sorted({n for n in npis if n and NPI_RE.match(str(n))})
    if not npis: return []
    have = _tables(); lit = ",".join(f"'{n}'" for n in npis); out = []
    for t, sql in EVENT_SQL.items():
        if t not in have: continue
        try:
            for r in con().execute(sql.format(npis=lit)).fetchall():
                out.append(dict(npi=r[0], source=r[1], tier=r[2], event_dt=r[3], window_end=r[4], reason=r[5], state=r[6], name=r[7], detail=r[8]))
        except Exception as e:
            out.append(dict(npi=None, source=f"ERROR_{t}", tier=None, event_dt=None, window_end=None, reason=str(e)[:200], state=None, name=None, detail=None))
    return out

def provider_names(npis):
    npis = sorted({n for n in npis if n and NPI_RE.match(str(n))})
    if not npis or "nppes" not in _tables(): return {}
    lit = ",".join(f"'{n}'" for n in npis)
    rows = con().execute(f"""SELECT npi, COALESCE(org_name, trim(COALESCE(first_name,'')||' '||COALESCE(last_name,''))), entity_type, state, city
                             FROM nppes WHERE npi IN ({lit})""").fetchall()
    return {r[0]: dict(name=r[1], entity_type=r[2], state=r[3], city=r[4]) for r in rows}

def paid_after(event, service_dt):
    """True when a service date falls inside the exclusion window."""
    if not service_dt or not event.get("event_dt"): return False
    if service_dt <= event["event_dt"]: return False
    we = event.get("window_end")
    return we is None or service_dt <= we

def verify_claims(claims):
    """claims: list of dicts with keys id, type, start (date), end (date), npis (list), paid (float or None), codes (list).
    Returns per-claim flags plus a summary."""
    all_npis = {n for c in claims for n in c.get("npis", [])}
    ev = events_for(all_npis); names = provider_names(all_npis)
    by_npi, seen = {}, set()
    for e in ev:   # the revoked list repeats one revocation per enrollment; keep one row per (npi, source, date, reason)
        k = (e["npi"], e["source"], e["event_dt"], e["reason"])
        if k in seen: continue
        seen.add(k); by_npi.setdefault(e["npi"], []).append(e)
    flagged = []
    for c in claims:
        hits = []
        for n in c.get("npis", []):
            for e in by_npi.get(n, []):
                if paid_after(e, c.get("start")):
                    hits.append({**e, "event_dt": str(e["event_dt"]), "window_end": str(e["window_end"]) if e["window_end"] else None})
        if hits:
            flagged.append({**c, "start": str(c.get("start")), "end": str(c.get("end")), "hits": hits})
    return dict(
        n_claims=len(claims), n_npis=len(all_npis), n_npis_with_events=len(by_npi), n_flagged_claims=len(flagged),
        flagged_paid=round(sum((c.get("paid") or 0) for c in flagged), 2),
        flagged=flagged,
        providers={n: {**names.get(n, {}), "events": [{**e, "event_dt": str(e["event_dt"]), "window_end": str(e["window_end"]) if e["window_end"] else None} for e in by_npi.get(n, [])]} for n in sorted(all_npis)},
    )

def sam_live_lookup(name=None, uei=None, size=10):
    """Live SAM.gov Exclusions API v4 (needs SAM_API_KEY). Use for organizations SAM lists without an NPI."""
    key = os.environ.get("SAM_API_KEY")
    if not key: return {"error": "SAM_API_KEY not set"}
    q = dict(api_key=key, size=size)
    if name: q["exclusionName"] = name
    if uei: q["ueiSAM"] = uei
    import httpx
    r = httpx.get("https://api.sam.gov/entity-information/v4/exclusions", params=q, timeout=60, headers={"User-Agent": "verity/0.1"})
    if r.status_code != 200: return {"error": f"SAM API {r.status_code}", "detail": r.text[:300]}
    d = r.json()
    out = []
    for e in d.get("excludedEntity", []):
        det, ident, acts = e.get("exclusionDetails", {}), e.get("exclusionIdentification", {}), (e.get("exclusionActions", {}).get("listOfActions") or [{}])
        addr = e.get("exclusionPrimaryAddress", {}) or {}
        out.append(dict(name=ident.get("entityName"), npi=ident.get("npi"), uei=ident.get("ueiSAM"), classification=det.get("classificationType"),
                        exclusion_type=det.get("exclusionType"), program=det.get("exclusionProgram"), agency=det.get("excludingAgencyCode"),
                        active_dt=acts[0].get("activateDate"), termination_dt=acts[0].get("terminationDate"), status=acts[0].get("recordStatus"),
                        city=addr.get("city"), state=addr.get("stateOrProvinceCode")))
    return dict(total=d.get("totalRecords", 0), results=out)

