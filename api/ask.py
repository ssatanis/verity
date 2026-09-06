"""'Ask this case' for the FastAPI service: Claude answers reviewer questions using evidence tools only (Supabase serving tables).
Mirror of web/app/api/ask/route.ts so both surfaces behave the same."""
from __future__ import annotations
import json, os
import psycopg
from psycopg.rows import dict_row
from anthropic import beta_tool
import llm

SYSTEM = ("You are the case assistant inside Verity, a provider-integrity console for health plan investigators. You may only answer from the tool results in this conversation. "
          "Every factual sentence must end with a bracketed citation naming the tool and the row, for example [payment_timeline: NPI 1234567893, 2022-11]. If the tools do not contain the answer, say so. "
          "Describe records, dates and amounts; never assert fraud or intent; the subject is a referral candidate. Keep paragraphs to three or four sentences.\n\n" + llm.STYLE)

def _conn():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)

def _npis(subject_type, subject_id, c):
    if subject_type == "cluster":
        return [r["npi"] for r in c.execute("SELECT npi FROM public.cluster_members WHERE cluster_id=%s", (subject_id,)).fetchall()]
    return [subject_id]

def make_tools(subject_type: str, subject_id: str):
    @beta_tool
    def get_subject() -> str:
        """The subject's summary row: community features, or the provider's risk row and NPPES record."""
        with _conn() as c:
            if subject_type == "cluster":
                r = c.execute("SELECT id, rank, score, state, city, county, n_providers, n_hospice, n_hha, n_snf, dollars_at_risk, dollars_medicare, summary, features FROM public.clusters WHERE id=%s", (subject_id,)).fetchone()
            else:
                r = {"risk": c.execute("SELECT * FROM public.provider_risk WHERE npi=%s", (subject_id,)).fetchone(), "provider": c.execute("SELECT * FROM public.providers WHERE npi=%s", (subject_id,)).fetchone()}
        return json.dumps(r, default=str)
    @beta_tool
    def get_members(limit: int = 60) -> str:
        """Members of the community (or the communities a provider belongs to): name, NPI, type, city, incorporation date, list labels, Medicaid 2024 dollars."""
        with _conn() as c:
            if subject_type == "cluster":
                rows = c.execute("SELECT npi, org_name, ptype, city, state, inc_date, labels, medicaid_2024, medicare_2023 FROM public.cluster_members WHERE cluster_id=%s ORDER BY medicaid_2024 DESC NULLS LAST LIMIT %s", (subject_id, limit)).fetchall()
            else:
                rows = c.execute("SELECT m.cluster_id, c.rank, c.score, c.summary FROM public.cluster_members m JOIN public.clusters c ON c.id=m.cluster_id WHERE m.npi=%s", (subject_id,)).fetchall()
        return json.dumps(rows, default=str)
    @beta_tool
    def get_owners(limit: int = 120) -> str:
        """Owner and managing-employee rows from the CMS All-Owners files for the subject's enrollments."""
        with _conn() as c:
            q = ("SELECT o.enrollment_id, o.org_name, o.owner_type, o.role_text, o.first_name, o.last_name, o.owner_org_name, o.city, o.state, o.pct_ownership, o.association_date, o.flags FROM public.owners o "
                 + ("JOIN public.cluster_members m ON m.enrollment_id=o.enrollment_id WHERE m.cluster_id=%s" if subject_type == "cluster" else "JOIN public.enrollments e ON e.enrollment_id=o.enrollment_id WHERE e.npi=%s") + " LIMIT %s")
            rows = c.execute(q, (subject_id, limit)).fetchall()
        return json.dumps(rows, default=str)
    @beta_tool
    def get_list_actions() -> str:
        """Medicare revocations and OIG exclusions for the subject's NPIs, with dates, grounds and re-enrollment bars."""
        with _conn() as c:
            npis = _npis(subject_type, subject_id, c)
            rev = c.execute("SELECT npi, org_name, first_name, last_name, state, revocation_rsn, revoked_dt, reenroll_bar_dt FROM public.revoked WHERE npi = ANY(%s)", (npis,)).fetchall()
            leie = c.execute("SELECT npi, busname, firstname, lastname, state, excltype, excl_dt, rein_dt FROM public.leie WHERE npi = ANY(%s)", (npis,)).fetchall()
        return json.dumps({"revoked": rev, "leie": leie}, default=str)
    @beta_tool
    def get_payment_timeline() -> str:
        """Detector flags with dates and dollars: for D3 the action date, first and last Medicaid service month after it and dollars; for D2 each flagged month with implied hours, patients, billing organizations and codes."""
        with _conn() as c:
            npis = _npis(subject_type, subject_id, c)
            rows = c.execute("SELECT npi, detector, tier, month, metric, value, threshold, dollars, evidence FROM public.flags WHERE npi = ANY(%s) ORDER BY month LIMIT 200", (npis,)).fetchall()
        return json.dumps(rows, default=str)
    @beta_tool
    def get_saturation() -> str:
        """CMS Market Saturation rows for the subject's county: providers per 10k FFS beneficiaries by service type and year."""
        with _conn() as c:
            fips = (c.execute("SELECT county_fips FROM public.clusters WHERE id=%s", (subject_id,)).fetchone() if subject_type == "cluster" else c.execute("SELECT county_fips FROM public.provider_risk WHERE npi=%s", (subject_id,)).fetchone()) or {}
            fips = fips.get("county_fips")
            if not fips: return "[]"
            st = (c.execute("SELECT state FROM public.county_risk WHERE county_fips=%s", (fips,)).fetchone() or {}).get("state")
            rows = c.execute("SELECT reference_period, type_of_service, county, state, providers, ffs_beneficiaries, providers_per_10k_ffs, moratorium FROM public.saturation_county WHERE county_fips=%s AND state=%s LIMIT 40", (str(fips)[-3:], st)).fetchall()
        return json.dumps(rows, default=str)
    return [get_subject, get_members, get_owners, get_list_actions, get_payment_timeline, get_saturation]

def ask(subject_type: str, subject_id: str, question: str, history: list[dict] | None = None) -> dict:
    if not llm.ready(): raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    messages = [m for m in (history or [])[-8:] if m.get("role") in ("user", "assistant")] + [{"role": "user", "content": question}]
    runner = llm.client().beta.messages.tool_runner(model=llm.MODEL, max_tokens=4000, system=SYSTEM + f" Subject: {subject_type} {subject_id}.", tools=make_tools(subject_type, subject_id), messages=messages, max_iterations=8)
    final = runner.until_done()
    text = "\n".join(b.text for b in final.content if getattr(b, "type", "") == "text")
    return {"answer": llm.clean_text(text), "stop_reason": final.stop_reason}
