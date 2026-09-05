"""Whole-universe lookups over the DuckDB warehouse (every NPI in NPPES, 9 million records) for the console search and provider pages.
Opens a short read-only connection per request so it never holds the single-writer lock while a detector runs."""
from __future__ import annotations
import os, re
import duckdb
DB = os.environ.get("VERITY_DUCKDB", "data/verity.duckdb")
def _con():
    return duckdb.connect(DB, read_only=True)
def search(q: str, limit: int = 10) -> list[dict]:
    q = q.strip(); limit = max(1, min(int(limit), 25))
    if not q: return []
    with _con() as con:
        if re.fullmatch(r"\d{2,10}", q):
            rows = con.execute("""SELECT npi, COALESCE(org_name, trim(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) AS name, city, state, entity_type
                                  FROM nppes WHERE npi LIKE ? ORDER BY npi LIMIT ?""", (q + "%", limit)).fetchall()
        else:
            toks = [t for t in re.split(r"\s+", q.upper()) if t]
            first, last = (toks[0], toks[-1]) if len(toks) > 1 else (toks[0], toks[0])
            rows = con.execute("""SELECT npi, COALESCE(org_name, trim(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) AS name, city, state, entity_type
                                  FROM nppes
                                  WHERE upper(org_name) LIKE ? OR (upper(last_name) LIKE ? AND upper(first_name) LIKE ?) OR upper(last_name) LIKE ?
                                  ORDER BY (upper(org_name) LIKE ?) DESC, name LIMIT ?""", (q.upper() + "%", last + "%", first + "%", q.upper() + "%", q.upper() + "%", limit)).fetchall()
    return [dict(npi=r[0], name=r[1], city=r[2], state=r[3], entity_type=r[4]) for r in rows]
def provider(npi: str) -> dict | None:
    if not re.fullmatch(r"\d{10}", npi): return None
    with _con() as con:
        n = con.execute("""SELECT npi, entity_type, COALESCE(org_name, trim(COALESCE(first_name,'') || ' ' || COALESCE(last_name,''))) AS name, city, state, zip5, taxonomy, enum_date, deact_date, react_date
                           FROM nppes WHERE npi = ?""", (npi,)).fetchone()
        if not n: return None
        cols = ["npi", "entity_type", "name", "city", "state", "zip5", "taxonomy", "enum_date", "deact_date", "react_date"]
        out = dict(zip(cols, n))
        try:
            out["medicaid_states"] = [r[0] for r in con.execute("SELECT DISTINCT state FROM enroll WHERE npi = ? ORDER BY 1", (npi,)).fetchall()]
        except Exception: out["medicaid_states"] = []
        try:
            out["spend_by_year"] = [dict(year=r[0], paid=float(r[1] or 0), months=int(r[2] or 0)) for r in con.execute(
                "SELECT substr(month, 1, 4) AS yr, SUM(paid), COUNT(*) FROM spend_any_month WHERE npi = ? GROUP BY 1 ORDER BY 1", (npi,)).fetchall()]
        except Exception: out["spend_by_year"] = []
        try:
            out["medicare_by_year"] = [dict(program=r[0], year=int(r[1]), services=float(r[2] or 0), beneficiaries=float(r[3] or 0), paid=float(r[4] or 0)) for r in con.execute(
                "SELECT program, year, services, beneficiaries, paid FROM medicare_billing WHERE npi = ? ORDER BY program, year", (npi,)).fetchall()]
        except Exception: out["medicare_by_year"] = []
        try:
            out["medicaid_top_codes"] = [dict(code=r[0], paid=float(r[1] or 0), months=int(r[2] or 0), role=r[3]) for r in con.execute(
                "SELECT hcpcs, SUM(paid), MAX(months), string_agg(DISTINCT role, ' and ') FROM spend_npi_code WHERE npi = ? GROUP BY 1 ORDER BY 2 DESC LIMIT 12", (npi,)).fetchall()]
        except Exception: out["medicaid_top_codes"] = []
        try:
            out["medicaid_roles"] = {r[0]: float(r[1] or 0) for r in con.execute("SELECT 'billing', SUM(paid) FROM spend_bill_month WHERE npi = ? UNION ALL SELECT 'servicing', SUM(paid) FROM spend_srv_month WHERE npi = ?", (npi, npi)).fetchall()}
        except Exception: out["medicaid_roles"] = {}
        try:
            out["lists"] = {"revoked": con.execute("SELECT COUNT(*) FROM revoked WHERE npi = ?", (npi,)).fetchone()[0], "leie": con.execute("SELECT COUNT(*) FROM leie WHERE npi = ?", (npi,)).fetchone()[0],
                            "sam": con.execute("SELECT COUNT(*) FROM sam WHERE npi = ?", (npi,)).fetchone()[0], "state": con.execute("SELECT COUNT(*) FROM state_exclusions WHERE npi = ?", (npi,)).fetchone()[0]}
        except Exception: out["lists"] = {}
    return {k: (str(v) if hasattr(v, "isoformat") else v) for k, v in out.items()}
