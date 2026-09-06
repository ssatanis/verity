"""Referral candidate packet builder.

Two paths produce the same schema: a deterministic builder that turns evidence lines into numbered findings, and a Claude draft
(claude-sonnet-5, structured output) that must cite evidence line ids for every finding; findings that cite nothing, or cite ids
that do not exist, are dropped and the deterministic text is used instead. Regulatory grounds come from api/grounds.py, selected
from evidence types, never from keywords. Language rule: the packet describes records and dates and calls the subject a referral
candidate; it never asserts fraud. House style: no em dashes."""
import datetime as dt, json, os, re
from typing import List
from pydantic import BaseModel, Field
from evidence import cluster_evidence, provider_evidence, evidence_lines
from grounds import grounds_for_types, evidence_types
import llm

class Finding(BaseModel):
    text: str = Field(description="One factual sentence describing a record, date or amount from the evidence. No conclusions about intent.")
    evidence_ids: List[int] = Field(description="Ids of the evidence lines that support this sentence verbatim.")
class PacketDraft(BaseModel):
    summary: str = Field(description="Two sentences for an SIU or program integrity reviewer: what the records show and why it warrants a records request.")
    plain_english: str = Field(description="One paragraph a non-specialist can follow. Describe what public records show; do not assert wrongdoing.")
    findings: List[Finding]
    recommendation: str = Field(description="Concrete next steps: records to request, checks to run, whom to refer to, citing the regulatory grounds provided.")
    caveats: List[str] = Field(description="Reasons the pattern could be legitimate, taken from the evidence and the detector caveats.")

SYSTEM = """You draft referral candidate packets for health plan special investigations units and state Medicaid program integrity units.

What the packet must be true to:
- Every finding is supported verbatim by the evidence lines you are given and cites their ids. Never add a fact that is not in the evidence.
- Describe records, dates and amounts. Never assert fraud, intent or guilt. The subject is a referral candidate, not a finding.
- Use the regulatory grounds provided by their citation. Do not invent citations.
- Include caveats: the legitimate explanations a reviewer must rule out, such as supervisory billing conventions, appeals and reinstatements, shared landlords and data lag.

How each field reads:
- summary: three to five sentences. The first says what the record is and when. The rest add one fact each. It is a paragraph of separate sentences, never one long sentence.
- plain_english: three to five sentences describing this specific subject, drawn from the evidence. Never a generic paragraph, and never a restatement of the summary.
- findings: one sentence each, or two short ones. No sentence carries more than one figure.
- recommendation: two to four sentences saying what to do next and under which rule.
- caveats: one sentence each.

""" + llm.STYLE

def _title(ev):
    if ev["kind"] == "cluster": return f"Referral packet: provider network {ev['cluster']['id']}"
    p = ev.get("provider") or {}; return f"Referral packet: {p.get('name') or ('NPI ' + str(p.get('npi') or ''))}".strip()

# caveats keyed by evidence type (mirrors web/lib/packet.ts): the ordinary explanations a reviewer must rule out first
CAVEATS = {
    "MEDICARE_REVOKED_PAID_AFTER": "A revocation can be reversed on appeal or through a corrective action plan; confirm the current enrollment status with the state and in PECOS before acting.",
    "OIG_LEIE_PAID_AFTER": "Check the LEIE for a reinstatement date; services dated before the exclusion but billed after it are lawful.",
    "SAM_PAID_AFTER": "SAM debarments from agencies other than HHS restrict federal contracting; confirm that the state's own screening policy applies to them.",
    "STATE_EXCL_PAID_AFTER": "State lists carry reinstatements and administrative terminations; confirm the action type with the listing agency.",
    "NPPES_DEACTIVATED_PAID_AFTER": "An NPI deactivated after a death or retirement can still receive lawful late claims for services rendered before the deactivation date.",
    "IMPOSSIBLE_HOURS": "The rendering NPI on Medicaid claims is often the supervising clinician under state convention; confirm which organizations employ or contract with this clinician before treating the hours as one person's work.",
    "PER_PATIENT_IMPOSSIBLE": "Per-patient hours can exceed the calendar under legitimate group or crisis services when the code is billed per staff member; confirm the code's billing unit with the state.",
    "MN_DAILY_CAP": "State caps carry prior-authorization exceptions; confirm whether an exception was on file.",
    "UMBRELLA_VOLUME": "One organization billing under a supervising NPI is common and lawful in several states; this is a records request, not a finding.",
    "GROWTH_ANOMALY": "Rapid growth and concentration on one code describe many legitimate new specialty agencies; this indicator is informational.",
    "NETWORK_SHARED_OWNERS": "Common ownership across several enrollments is lawful and ordinary; the indicator is the combination with formation timing, shared suites and list links.",
    "NETWORK_INCORPORATION_BURST": "Incorporation bursts also occur when a legitimate operator expands or restructures.",
    "NETWORK_SHARED_ADDRESS": "Shared suites and phones are ordinary in medical office buildings and with registered-agent, accountant or answering-service addresses; the address alone proves nothing.",
    "NETWORK_ADDRESS_OF_REVOKED_ENTITY": "A previous tenant's revocation does not attach to the current tenant; the link shows only that the address recurs.",
    "NETWORK_OWNER_ON_LEIE": "An owner match to the LEIE or SAM is a name match at the stated confidence; confirm identity with date of birth or address before relying on it.",
    "NETWORK_MEMBER_ON_LIST": "A list hit on one member does not extend to the other members without a records review.",
}

def deterministic_packet(ev):
    lines = evidence_lines(ev); types = evidence_types(ev); grounds = grounds_for_types(types)
    subject = ev["cluster"]["id"] if ev["kind"] == "cluster" else ev["provider"]["npi"]
    findings = [dict(text=l[1], evidence_ids=[i]) for i, l in enumerate(lines[1:], start=1)][:30]
    caveats = ["Screening indicator only: every fact must be verified against the cited source rows before any action, and the packet describes records and dates, never intent."]
    caveats += [CAVEATS[t] for t in types if t in CAVEATS]
    if not types: caveats.append("No detector evidence type was derived for this subject; the packet lists the public records only.")
    return dict(title=_title(ev), subject_type=ev["kind"], subject_id=subject, generated_at=dt.datetime.now(dt.timezone.utc).isoformat(), model="deterministic",
                summary=lines[0][1] if lines else "", findings=findings, grounds=grounds, evidence_types=types,
                recommendation="Request the provider's records for the flagged service months, verify the cited public records against the source datasets, run the 42 CFR 455.436 database checks, and, if the records do not resolve the pattern, refer to the state Medicaid program integrity unit and the Medicaid Fraud Control Unit under 42 CFR 455.23(d).",
                evidence=[dict(id=i, source=l[0], statement=l[1]) for i, l in enumerate(lines)], procedures=ev.get("procedures") or [],
                plain_english=("Public records show several related provider entities that were formed close together, share owners, suites or phone numbers, and sit in a market with an unusual number of providers. " if ev["kind"] == "cluster" else "Public records show an action that should have triggered a state screening check, followed by Medicaid claims for later service months, or a billing volume that one clinician could not deliver personally. ") + "Each numbered finding cites the public dataset and row it came from. This is a screening indicator to be checked, not a conclusion.",
                caveats=caveats)

def claude_packet(ev):
    base = deterministic_packet(ev); lines = base["evidence"]
    user = json.dumps({"subject": base["title"], "evidence": lines, "regulatory_grounds": base["grounds"], "evidence_types": base["evidence_types"]}, default=str)
    draft = llm.parse(PacketDraft, SYSTEM, user, effort="high")
    n = len(lines)
    ok = [f.model_dump() for f in draft.findings if f.evidence_ids and all(isinstance(i, int) and 0 <= i < n for i in f.evidence_ids)]
    base.update(model=llm.MODEL, summary=llm.clean_text(draft.summary) or base["summary"], plain_english=llm.clean_text(draft.plain_english) or base["plain_english"],
                findings=ok or base["findings"], recommendation=llm.clean_text(draft.recommendation) or base["recommendation"], caveats=llm.clean_text(draft.caveats) or base["caveats"],
                findings_dropped=len(draft.findings) - len(ok))
    return base

def build_packet(subject_type, subject_id, use_agent=None):
    ev = cluster_evidence(subject_id) if subject_type == "cluster" else provider_evidence(subject_id)
    if not ev: return None
    use_agent = llm.ready() if use_agent is None else (use_agent and llm.ready())
    if use_agent:
        try: return claude_packet(ev)
        except Exception as e:
            p = deterministic_packet(ev); p["model"] = f"deterministic (model unavailable: {str(e)[:80]})"; return p
    return deterministic_packet(ev)
