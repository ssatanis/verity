"""Referral candidate packet builder.

Two paths produce the same schema: a deterministic builder that turns evidence lines into numbered findings, and a Claude draft
(claude-opus-5, structured output) that must cite evidence line ids for every finding; findings that cite nothing, or cite ids
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
Rules:
1. Every finding must be supported verbatim by the evidence lines you are given and must cite their ids. Never add a fact that is not in the evidence.
2. Describe records, dates and amounts. Never assert fraud, intent or guilt. The subject is a referral candidate, not a finding.
3. Use the regulatory grounds provided by their citation; do not invent citations.
4. Plain English, short sentences, no jargon a payer executive would not know. Do not use em dashes or en dashes anywhere.
5. Include caveats: legitimate explanations the reviewer must rule out (supervisory billing conventions, appeals and reinstatements, shared landlords, data lag)."""

def _title(ev):
    if ev["kind"] == "cluster": return f"Referral candidate packet: provider community {ev['cluster']['id']}"
    p = ev["provider"] or {}; return f"Referral candidate packet: NPI {ev.get('provider', {}).get('npi') or ''} {p.get('name') or ''}".strip()

def deterministic_packet(ev):
    lines = evidence_lines(ev); types = evidence_types(ev); grounds = grounds_for_types(types)
    subject = ev["cluster"]["id"] if ev["kind"] == "cluster" else ev["provider"]["npi"]
    findings = [dict(text=l[1], evidence_ids=[i]) for i, l in enumerate(lines[1:], start=1)][:30]
    caveats = ["Screening indicator only: the detector has a measured false positive rate and every fact must be verified against the source rows before action.",
               "Several states permit clinics to bill under a supervising clinician's NPI, and telehealth or locum tenens arrangements can concentrate volume under one NPI.",
               "Medicare revocations and state exclusions can be appealed, reversed or reinstated; payments after an action can reflect claims later recouped.",
               "Shared addresses can reflect a common landlord or billing agent rather than common ownership."]
    return dict(title=_title(ev), subject_type=ev["kind"], subject_id=subject, generated_at=dt.datetime.now(dt.timezone.utc).isoformat(), model="deterministic",
                summary=lines[0][1] if lines else "", findings=findings, grounds=grounds, evidence_types=types,
                recommendation="Request the provider's records for the flagged service months, verify the cited public records against the source datasets, run the 42 CFR 455.436 database checks, and, if the records do not resolve the pattern, refer to the state Medicaid program integrity unit and the Medicaid Fraud Control Unit under 42 CFR 455.23(d).",
                evidence=[dict(id=i, source=l[0], statement=l[1]) for i, l in enumerate(lines)],
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
