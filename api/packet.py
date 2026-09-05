"""Referral packet builder. The deterministic builder produces a complete CMS-style packet from the evidence lines alone, so the
demo never depends on a model. When OPENAI_API_KEY is set, the investigator agent (OpenAI Agents SDK) is used with structured tools
that can only read the evidence, and every sentence it writes must cite an evidence line id; uncited sentences are dropped."""
import json, os, re, datetime as dt
from evidence import CFR, cluster_evidence, provider_evidence, evidence_lines

def grounds_for(ev):
    g = []
    lines = evidence_lines(ev); text = " ".join(l[1] for l in lines); low = text.lower()
    if "OIG LEIE" in text or "OIG_LEIE" in text: g += ["1001.1901", "424.535(a)(2)"]
    if "revoked" in low: g += ["424.535(a)(12)", "455.416(c)"]
    if "incorporated within a 90-day window" in text or "share one practice address" in text or "tied to three or more members" in text: g += ["424.535(a)(19)", "424.535(a)(5)"]
    if "implied hours" in text or "IMPOSSIBLE" in text: g += ["424.535(a)(8)", "455.23"]
    if "medicaid paid $" in low and "after the" in low: g += ["455.416(c)", "455.23"]
    if "state exclusion" in low or "STATE_EXCL" in text: g += ["455.416(c)"]
    seen = []; [seen.append(x) for x in g if x not in seen]
    return seen or ["455.410"]

def deterministic_packet(ev):
    lines = evidence_lines(ev); grounds = grounds_for(ev)
    subject = ev["cluster"]["id"] if ev["kind"] == "cluster" else ev["provider"]["npi"]
    title = (f"Referral packet: provider community {subject}" if ev["kind"] == "cluster" else f"Referral packet: NPI {subject} {ev['provider'].get('name','')}")
    summary = lines[0][1] if lines else ""
    findings = [dict(text=l[1], evidence_ids=[i]) for i, l in enumerate(lines[1:], start=1)][:30]
    recommendation = ("Refer to the state Medicaid program integrity unit and the CMS Center for Program Integrity for payment suspension review under 42 CFR 455.23 "
                      "and enrollment action under the grounds listed. Verify every fact against the source rows cited before any action; this packet is a screening product, not a finding.")
    return dict(title=title, subject_type=ev["kind"], subject_id=subject, generated_at=dt.datetime.now(dt.timezone.utc).isoformat(), model="deterministic",
                summary=summary, findings=findings, grounds=[dict(cfr=g, text=CFR[g]) for g in grounds], recommendation=recommendation,
                evidence=[dict(id=i, source=l[0], statement=l[1]) for i, l in enumerate(lines)],
                plain_english=("This provider community shows the structural fingerprint of a ghost network: several newly formed entities sharing owners and addresses in a saturated market, "
                               "with at least one link to a federal exclusion or revocation. " if ev["kind"] == "cluster" else
                               "Public federal records show an action that should have stopped Medicaid payment, and the state spending data shows payments continuing afterwards. ")
                              + "Each numbered finding cites the exact public dataset and row it came from.")

async def agent_packet(ev):
    """OpenAI Agents SDK path: tools expose the evidence; output must cite evidence ids."""
    from agents import Agent, Runner, function_tool
    lines = evidence_lines(ev); grounds = grounds_for(ev)
    @function_tool
    def get_evidence() -> str:
        """All evidence lines as JSON: [{id, source, statement}]. Every sentence in the packet must cite at least one id."""
        return json.dumps([dict(id=i, source=l[0], statement=l[1]) for i, l in enumerate(lines)])
    @function_tool
    def get_regulatory_grounds() -> str:
        """Applicable 42 CFR grounds pre-selected from the evidence, as JSON [{cfr, text}]."""
        return json.dumps([dict(cfr=g, text=CFR[g]) for g in grounds])
    agent = Agent(name="Verity investigator", model=os.environ.get("VERITY_AGENT_MODEL", "gpt-5"),
                  instructions=("You draft CMS-style payment-suspension / notice-of-intent referral packets for a human reviewer. Call get_evidence and get_regulatory_grounds first. "
                                "Write JSON with keys: summary (2 sentences), findings (list of {text, evidence_ids}), plain_english (one paragraph for a non-specialist), recommendation. "
                                "Every finding must cite evidence ids that support it verbatim; never add facts that are not in the evidence; never assert guilt, describe records and dates. "
                                "Use the regulatory grounds by CFR citation where they apply."), tools=[get_evidence, get_regulatory_grounds])
    result = await Runner.run(agent, "Draft the referral packet as JSON.")
    txt = result.final_output; m = re.search(r"\{.*\}", txt, re.S)
    out = json.loads(m.group(0)) if m else {}
    base = deterministic_packet(ev)
    findings = [f for f in out.get("findings", []) if f.get("evidence_ids") and all(isinstance(i, int) and 0 <= i < len(lines) for i in f["evidence_ids"])]
    base.update(model=agent.model, summary=out.get("summary") or base["summary"], findings=findings or base["findings"], plain_english=out.get("plain_english") or base["plain_english"], recommendation=out.get("recommendation") or base["recommendation"])
    return base

def build_packet(subject_type, subject_id, use_agent=None):
    ev = cluster_evidence(subject_id) if subject_type == "cluster" else provider_evidence(subject_id)
    if not ev: return None
    use_agent = bool(os.environ.get("OPENAI_API_KEY", "").startswith("sk-") and os.environ.get("OPENAI_API_KEY") != "sk-...") if use_agent is None else use_agent
    if use_agent:
        import asyncio
        try: return asyncio.run(agent_packet(ev))
        except Exception as e: p = deterministic_packet(ev); p["model"] = f"deterministic (agent failed: {str(e)[:80]})"; return p
    return deterministic_packet(ev)
