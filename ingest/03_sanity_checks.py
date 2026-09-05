#!/usr/bin/env python3
"""Sanity checks for verity.duckdb; appends a Methods section to docs/methods.md."""
import os, time, duckdb
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"), read_only=True)
def q(sql):
    try: return con.execute(sql).fetchall()
    except Exception as e: return [("ERROR", str(e)[:200])]
def tbl(title, sql, cols):
    rows = q(sql); out = [f"\n**{title}**\n", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows: out.append("| " + " | ".join(f"{v:,}" if isinstance(v, int) else (f"{v:,.2f}" if isinstance(v, float) else str(v)) for v in r) + " |")
    return "\n".join(out)
tables = [r[0] for r in q("SELECT table_name FROM information_schema.tables WHERE table_schema='main' ORDER BY 1")]
md = [f"\n## Warehouse sanity checks ({time.strftime('%Y-%m-%d %H:%M')} ET)\n", f"Tables in `data/verity.duckdb`: {', '.join(tables)}"]
md.append(tbl("spend (time-based HCPCS only, clean NPIs, paid between 0 and 50M)", "SELECT COUNT(*) AS rows, COUNT(DISTINCT servicing_npi) AS npis, ROUND(SUM(paid)/1e9,2) AS billions FROM spend", ["rows","servicing NPIs","$ billions"]))
md.append(tbl("Rows dropped from the Medicaid spending file", "SELECT reason, n FROM drops", ["reason","rows"]))
md.append(tbl("Medicaid enrollment", "SELECT (SELECT COUNT(*) FROM enroll) AS segments, (SELECT COUNT(*) FROM provider_state) AS providers_with_state", ["enrollment segments","NPIs with a home state"]))
md.append(tbl("CMS enrollment files", "SELECT (SELECT COUNT(*) FROM hospice), (SELECT COUNT(*) FROM hha), (SELECT COUNT(*) FROM snf), (SELECT COUNT(*) FROM hospital), (SELECT COUNT(*) FROM owners), (SELECT COUNT(*) FROM chow), (SELECT COUNT(*) FROM ppef)", ["hospice","HHA","SNF","hospital","owner rows","CHOW rows","PPEF rows"]))
md.append(tbl("Owner types (expect I and O)", 'SELECT "TYPE - OWNER", COUNT(*) FROM owners GROUP BY 1 ORDER BY 1', ["type","rows"]))
md.append(tbl("Labels", "SELECT (SELECT COUNT(*) FROM revoked), (SELECT COUNT(*) FROM revoked WHERE revoked_dt IS NOT NULL), (SELECT COUNT(*) FROM leie), (SELECT COUNT(*) FROM leie WHERE npi IS NOT NULL)", ["revoked rows","revoked with date","LEIE rows","LEIE with NPI"]))
md.append(tbl("Incorporation date parse rate", "SELECT 'hospice', COUNT(*), COUNT(inc_date) FROM hospice UNION ALL SELECT 'hha', COUNT(*), COUNT(inc_date) FROM hha UNION ALL SELECT 'snf', COUNT(*), COUNT(inc_date) FROM snf", ["file","rows","parsed inc_date"]))
md.append(tbl("Market saturation (typed county table)", "SELECT COUNT(*), COUNT(DISTINCT type_of_service), MIN(reference_period), MAX(reference_period), COUNT(*) FILTER (WHERE moratorium) FROM saturation_county", ["rows","service types","first period","last period","moratorium rows"]))
if "nppes" in tables:
    md.append(tbl("NPPES", "SELECT COUNT(*), COUNT(*) FILTER (WHERE entity_type='1'), COUNT(*) FILTER (WHERE entity_type='2'), COUNT(deact_date) FROM nppes", ["NPIs","individuals","organizations","deactivated"]))
md.append(tbl("Spend by year", "SELECT substr(month,1,4) AS yr, COUNT(*), ROUND(SUM(paid)/1e9,2) FROM spend GROUP BY 1 ORDER BY 1", ["year","rows","$ billions"]))
md.append(tbl("Top 15 time-based codes by dollars", "SELECT s.hcpcs, t.description, ROUND(SUM(paid)/1e9,2) AS b FROM spend s JOIN timecodes t USING (hcpcs) GROUP BY 1,2 ORDER BY 3 DESC LIMIT 15", ["hcpcs","description","$ billions"]))
open("docs/methods.md", "a").write("\n".join(md) + "\n"); print("\n".join(md))
