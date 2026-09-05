"""Verity API. Run: .venv/bin/uvicorn api.main:app --reload --port 8000

Routes
  /clusters, /clusters/{id}, /providers/{npi}     evidence for the investigator agent (Supabase serving layer)
  POST /packets, POST /reviews, POST /retrain/{d}  referral packets and the reviewer feedback loop
  POST /verify, GET /verify/npi/{npi}               NPI tripwire over the warehouse (api/verify.py)
  /bluebutton/authorize, /bluebutton/callback      CMS Blue Button 2.0 (api/bluebutton.py): pull a beneficiary's EOBs and run the tripwire
  GET /sam/lookup                                   live SAM.gov exclusions lookup (needs SAM_API_KEY)
"""
import json, os, re, sys, uuid, secrets, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg, httpx
from psycopg.rows import dict_row
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from evidence import cluster_evidence, provider_evidence, evidence_lines
from packet import build_packet
import verify as vf
import ask as askmod
import lookup
import bluebutton as bb

app = FastAPI(title="Verity API", version="0.2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
def pg(): return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)
CLUSTER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$"); UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
def check_subject(subject_type, subject_id):
    """Every subject id is validated before it reaches a query, a storage path or the model."""
    if subject_type not in ("cluster", "provider"): raise HTTPException(400, "subject_type must be cluster or provider")
    if subject_type == "provider" and not re.fullmatch(r"\d{10}", subject_id or ""): raise HTTPException(400, "subject_id must be a ten-digit NPI")
    if subject_type == "cluster" and not CLUSTER_ID_RE.match(subject_id or ""): raise HTTPException(400, "bad cluster id")
import llm
def agent_ready(): return llm.ready()

@app.get("/health")
def health(): return {"ok": True, "agent": agent_ready(), "model": llm.MODEL, "bluebutton": bool(bb.CLIENT_ID), "sam_api": bool(os.environ.get("SAM_API_KEY"))}

# ---------------- evidence ----------------
@app.get("/clusters")
def clusters(limit: int = 50, state: str | None = None):
    limit = max(1, min(limit, 500)); state = (state or "").strip().upper()[:2] or None
    with pg() as c:
        return c.execute("SELECT id, rank, score, state, city, county, n_providers, n_hospice, n_hha, n_snf, dollars_at_risk, summary FROM public.clusters WHERE eligible AND (%s::text IS NULL OR state = %s) ORDER BY rank LIMIT %s", (state, state, limit)).fetchall()

@app.get("/clusters/{cluster_id}")
def cluster(cluster_id: str):
    ev = cluster_evidence(cluster_id)
    if not ev: raise HTTPException(404)
    ev["evidence_lines"] = [dict(id=i, source=s, statement=t) for i, (s, t) in enumerate(evidence_lines(ev))]; return ev

@app.get("/providers/{npi}")
def provider(npi: str):
    ev = provider_evidence(npi)
    if not ev: raise HTTPException(404)
    ev["evidence_lines"] = [dict(id=i, source=s, statement=t) for i, (s, t) in enumerate(evidence_lines(ev))]; return ev

# ---------------- packets and the feedback loop ----------------
class PacketReq(BaseModel):
    subject_type: str; subject_id: str; use_agent: bool | None = None; created_by: str | None = "demo"
@app.post("/packets")
def make_packet(req: PacketReq):
    check_subject(req.subject_type, req.subject_id); req.created_by = (req.created_by or "demo")[:80]
    p = build_packet(req.subject_type, req.subject_id, req.use_agent)
    if not p: raise HTTPException(404)
    pid = str(uuid.uuid4())
    with pg() as c:
        c.execute("INSERT INTO public.packets (id, subject_type, subject_id, status, packet, created_by, title, cluster_id, npi, model) VALUES (%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s)",
                  (pid, req.subject_type, req.subject_id, json.dumps(p, default=str), req.created_by, p["title"], req.subject_id if req.subject_type == "cluster" else None,
                   req.subject_id if req.subject_type == "provider" else None, p["model"])); c.commit()
    try:  # copy into the private packets bucket
        K = os.environ["SUPABASE_SECRET_KEY"]
        httpx.post(f"{os.environ['SUPABASE_URL']}/storage/v1/object/verity-packets/{req.subject_type}/{req.subject_id}/{pid}.json", headers={"apikey": K, "Authorization": f"Bearer {K}", "Content-Type": "application/json", "x-upsert": "true"}, content=json.dumps(p, default=str).encode(), timeout=60)
    except Exception: pass
    return dict(id=pid, **p)

class ReviewReq(BaseModel):
    packet_id: str; decision: str; reviewer: str | None = "demo"; notes: str | None = None
@app.post("/reviews")
def review(req: ReviewReq):
    if req.decision not in ("accept", "reject", "needs_info"): raise HTTPException(400, "decision must be accept, reject or needs_info")
    if not UUID_RE.match(req.packet_id or ""): raise HTTPException(400, "packet_id must be a UUID")
    req.reviewer = (req.reviewer or "demo")[:80]; req.notes = (req.notes or "")[:4000] or None
    with pg() as c:
        p = c.execute("SELECT subject_type, subject_id FROM public.packets WHERE id = %s", (req.packet_id,)).fetchone()
        if not p: raise HTTPException(404)
        det = "D1" if p["subject_type"] == "cluster" else (c.execute("SELECT detector FROM public.flags WHERE npi = %s ORDER BY score DESC LIMIT 1", (p["subject_id"],)).fetchone() or {}).get("detector")
        score = (c.execute("SELECT score FROM public.clusters WHERE id = %s", (p["subject_id"],)).fetchone() or {}).get("score") if det == "D1" else (c.execute("SELECT MAX(score) score FROM public.flags WHERE npi = %s", (p["subject_id"],)).fetchone() or {}).get("score")
        c.execute("INSERT INTO public.reviews (packet_id, subject_type, subject_id, decision, reviewer, notes, detector, score_at_review) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                  (req.packet_id, p["subject_type"], p["subject_id"], req.decision, req.reviewer, req.notes, det, score))
        c.execute("UPDATE public.packets SET status = %s WHERE id = %s", ("accepted" if req.decision == "accept" else ("rejected" if req.decision == "reject" else "needs_info"), req.packet_id)); c.commit()
    return retrain(det or "D1")

@app.post("/retrain/{detector}")
def retrain(detector: str):
    """Feedback loop: Bayesian re-weighting of the detector's evidence families from reviewer decisions.
    For D1 the families are structure, label, context; each weight = 2 x (accepts + prior/2) / (accepts + rejects + prior) over packets where the family was present."""
    if detector not in ("D1", "D2", "D3"): raise HTTPException(400, "detector must be D1, D2 or D3")
    with pg() as c:
        rows = c.execute("SELECT r.decision, cl.features FROM public.reviews r JOIN public.clusters cl ON cl.id = r.subject_id WHERE r.detector = 'D1'").fetchall() if detector == "D1" else \
               c.execute("SELECT r.decision, NULL::jsonb AS features FROM public.reviews r WHERE r.detector = %s", (detector,)).fetchall()
        n = len(rows); prior = 4.0
        fams = ("structure", "label", "context") if detector == "D1" else ("evidence",)
        w = {}
        for fam in fams:
            pres = (lambda r: (r["features"] or {}).get(f"{fam}_family")) if detector == "D1" else (lambda r: True)
            a_ = sum(1 for r in rows if r["decision"] == "accept" and pres(r)); b_ = sum(1 for r in rows if r["decision"] == "reject" and pres(r))
            w[fam] = round(2.0 * (a_ + prior / 2) / (a_ + b_ + prior), 3)
        c.execute("INSERT INTO public.score_weights (detector, weights, n_reviews, updated_at) VALUES (%s,%s,%s,now()) ON CONFLICT (detector) DO UPDATE SET weights = excluded.weights, n_reviews = excluded.n_reviews, updated_at = now()", (detector, json.dumps(w), n)); c.commit()
    return dict(detector=detector, weights=w, n_reviews=n)

# ---------------- NPI tripwire (api/verify.py) ----------------
class Claim(BaseModel):
    id: str | None = None; type: str | None = None; start: dt.date | None = None; end: dt.date | None = None; npis: list[str] = []; paid: float | None = None; codes: list[str] = []
class VerifyReq(BaseModel):
    claims: list[Claim]
@app.post("/verify")
def verify_claims(req: VerifyReq):
    return vf.verify_claims([c.model_dump() for c in req.claims])

@app.get("/verify/npi/{npi}")
def verify_npi(npi: str):
    if not vf.NPI_RE.match(npi): raise HTTPException(400, "not an NPI")
    return dict(npi=npi, provider=vf.provider_names([npi]).get(npi), events=vf.events_for([npi]))

@app.get("/verify")
def verify_many(npis: str = Query(..., description="comma-separated NPIs")):
    ids = [n.strip() for n in npis.split(",") if n.strip()]
    return dict(providers=vf.provider_names(ids), events=vf.events_for(ids))

@app.get("/sam/lookup")
def sam_lookup(name: str | None = None, uei: str | None = None): return vf.sam_live_lookup(name=name, uei=uei)

# ---------------- Blue Button 2.0 (api/bluebutton.py) ----------------
_BB_STATE: dict[str, str] = {}   # state -> PKCE verifier (single-process demo store)
def _bb_guard():
    if not bb.CLIENT_ID: raise HTTPException(503, "BLUEBUTTON_CLIENT_ID is not set")
    if "sandbox" in bb.BASE and os.environ.get("BLUEBUTTON_ALLOW_SANDBOX") != "1":
        raise HTTPException(403, "The CMS sandbox only serves synthetic beneficiaries; set BLUEBUTTON_ALLOW_SANDBOX=1 for integration testing or point BLUEBUTTON_BASE_URL at production")

@app.get("/bluebutton/authorize")
def bb_authorize(lang: str = "en"):
    _bb_guard(); verifier, challenge = bb.pkce_pair(); state = secrets.token_urlsafe(24); _BB_STATE[state] = verifier
    return RedirectResponse(bb.authorize_url(state, challenge, lang))

@app.get("/bluebutton/callback")
def bb_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    _bb_guard()
    if error: raise HTTPException(400, error)
    verifier = _BB_STATE.pop(state or "", None)
    if not verifier: raise HTTPException(400, "unknown state")
    if not code: raise HTTPException(400, "missing code")
    try: tok = bb.exchange_code(code, verifier)
    except httpx.HTTPError as e: raise HTTPException(502, f"token exchange failed: {type(e).__name__}")
    token = tok.get("access_token"); patient_id = tok.get("patient")
    if not token: raise HTTPException(502, "token exchange returned no access token")
    patient = bb.get_patient(token); coverage = bb.get_coverage(token, patient_id); eobs = bb.get_all_eobs(token, patient_id)
    claims = bb.normalize_eobs(eobs); result = vf.verify_claims(claims)
    return dict(patient=patient if isinstance(patient, dict) and patient.get("denied") else {"id": (patient or {}).get("id")}, coverage_count=len((coverage or {}).get("entry", [])), claims=len(claims), tripwire=result)

class BundleReq(BaseModel):
    bundle: dict
@app.post("/bluebutton/verify-bundle")
def bb_verify_bundle(req: BundleReq):
    """Run the tripwire over an EOB bundle a beneficiary exported from Medicare.gov (no OAuth needed)."""
    try: claims = bb.normalize_eobs(req.bundle)
    except (AttributeError, TypeError, ValueError, KeyError) as e: raise HTTPException(400, f"not a FHIR ExplanationOfBenefit bundle ({type(e).__name__})")
    return dict(claims=len(claims), tripwire=vf.verify_claims(claims))


class AskIn(BaseModel):
    subject_type: str; subject_id: str; question: str; history: list[dict] = []

@app.post("/ask")
def ask_case(body: AskIn):
    """'Ask this case': Claude answers from evidence tools only; every sentence cites a tool row."""
    check_subject(body.subject_type, body.subject_id)
    question = (body.question or "").strip()[:2000]
    if not question: raise HTTPException(400, "question is empty")
    history = [dict(role=m["role"], content=str(m["content"])[:8000]) for m in body.history if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str) and m["content"].strip()][-8:]
    try: return askmod.ask(body.subject_type, body.subject_id, question, history)
    except RuntimeError as e: raise HTTPException(503, str(e))


@app.get("/search")
def search_any(q: str = Query(..., min_length=2), limit: int = 10):
    """Search every NPI in NPPES by number prefix or name (organization, or last and first name)."""
    try: return {"hits": lookup.search(q, limit)}
    except Exception as e: raise HTTPException(503, f"warehouse busy: {str(e)[:80]}")

@app.get("/provider/{npi}")
def provider_any(npi: str):
    """NPPES record, Medicaid states, yearly Medicaid dollars and list counts for any NPI, whether or not a detector reached it."""
    try: r = lookup.provider(npi)
    except Exception as e: raise HTTPException(503, f"warehouse busy: {str(e)[:80]}")
    if not r: raise HTTPException(404, "NPI not in NPPES")
    return r


@app.get("/")
def index():
    """Service index so the API answers at its root."""
    return {"service": "Verity API", "docs": "/docs", "health": "/health",
            "routes": ["/search?q=", "/provider/{npi}", "/clusters", "/providers/{npi}", "/packets", "/reviews", "/ask", "/verify", "/sam/lookup"],
            "model": llm.MODEL, "agent": llm.ready()}
