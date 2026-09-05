"""Blue Button 2.0 client for Verity.

OAuth 2.0 authorization-code flow with PKCE (S256), confidential client, per the CMS docs. Then pulls Patient, Coverage and every
ExplanationOfBenefit page for the authorized beneficiary and normalizes claims into the shape api/verify.py consumes:
  {id, type, start, end, npis: [...], paid, codes: [...], provider_name}
Production base URL is https://api.bluebutton.cms.gov (real beneficiaries, requires CMS production approval; see README). The CMS sandbox
only serves synthetic test beneficiaries and is blocked by api/main.py unless BLUEBUTTON_ALLOW_SANDBOX=1 is set for integration testing.
"""
import os, re, base64, hashlib, secrets, datetime as dt, urllib.parse
import httpx
BASE = os.environ.get("BLUEBUTTON_BASE_URL", "https://sandbox.bluebutton.cms.gov").rstrip("/")
CLIENT_ID = os.environ.get("BLUEBUTTON_CLIENT_ID", ""); CLIENT_SECRET = os.environ.get("BLUEBUTTON_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("BLUEBUTTON_REDIRECT_URI", "http://localhost:8000/bluebutton/callback")
SCOPES = os.environ.get("BLUEBUTTON_SCOPES", "openid profile patient/Patient.rs patient/Coverage.rs patient/ExplanationOfBenefit.rs").replace(",", " ").split()
NPI_RE = re.compile(r"^[12]\d{9}$")

def pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge

def authorize_url(state, challenge, lang="en"):
    q = dict(client_id=CLIENT_ID, redirect_uri=REDIRECT_URI, response_type="code", scope=" ".join(SCOPES), state=state,
             code_challenge=challenge, code_challenge_method="S256", lang=lang)
    return f"{BASE}/v2/o/authorize/?" + urllib.parse.urlencode(q)

def exchange_code(code, verifier):
    r = httpx.post(f"{BASE}/v2/o/token/", auth=(CLIENT_ID, CLIENT_SECRET), timeout=60,
                   data=dict(grant_type="authorization_code", code=code, redirect_uri=REDIRECT_URI, code_verifier=verifier))
    r.raise_for_status(); return r.json()   # access_token, refresh_token (13-month apps), patient, expires_in, scope

def refresh(refresh_token):
    r = httpx.post(f"{BASE}/v2/o/token/", auth=(CLIENT_ID, CLIENT_SECRET), timeout=60, data=dict(grant_type="refresh_token", refresh_token=refresh_token))
    r.raise_for_status(); return r.json()

def _get(token, path, params=None):
    r = httpx.get(f"{BASE}{path}", params=params, timeout=120,
                  headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "Accept-Encoding": "gzip"})
    r.raise_for_status(); return r.json()

def get_patient(token):
    try: return _get(token, "/v2/fhir/Patient")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403: return {"denied": "beneficiary did not share demographic data"}
        raise

def get_coverage(token, patient_id=None):
    return _get(token, "/v2/fhir/Coverage", {"beneficiary": patient_id} if patient_id else None)

def get_all_eobs(token, patient_id=None, types=None, max_pages=200):
    """Follow Bundle.link[rel=next] until exhausted. _count max is 50."""
    params = {"_count": 50}
    if patient_id: params["patient"] = patient_id
    if types: params["type"] = ",".join(types)
    bundle = _get(token, "/v2/fhir/ExplanationOfBenefit", params); entries = list(bundle.get("entry", [])); pages = 1
    while pages < max_pages:
        nxt = next((l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"), None)
        if not nxt: break
        r = httpx.get(nxt, timeout=120, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"}); r.raise_for_status()
        bundle = r.json(); entries += bundle.get("entry", []); pages += 1
    return {"resourceType": "Bundle", "total": bundle.get("total", len(entries)), "entry": entries}

# ---------- normalization ----------
def _date(s):
    try: return dt.date.fromisoformat(s[:10]) if s else None
    except Exception: return None

def eob_npis(eob):
    """Every NPI referenced by an EOB: careTeam (with role), provider identifier, contained Organizations/Practitioners."""
    found = {}
    for ct in eob.get("careTeam", []) or []:
        ident = (ct.get("provider") or {}).get("identifier") or {}
        code = ((ident.get("type") or {}).get("coding") or [{}])[0].get("code", "")
        v = str(ident.get("value", ""))
        role = ((ct.get("role") or {}).get("coding") or [{}])[0].get("code", "")
        if NPI_RE.match(v) and (code.lower() == "npi" or "npi" in str(ident.get("system", "")).lower() or code == ""):
            found[v] = role or "careTeam"
    ident = (eob.get("provider") or {}).get("identifier") or {}
    if NPI_RE.match(str(ident.get("value", ""))) and "npi" in str(ident.get("system", "")).lower(): found[str(ident["value"])] = "billing"
    for c in eob.get("contained", []) or []:
        for i in c.get("identifier", []) or []:
            v = str(i.get("value", ""))
            if NPI_RE.match(v) and ("npi" in str(i.get("system", "")).lower() or ((i.get("type") or {}).get("coding") or [{}])[0].get("code", "").lower() == "npi"):
                found[v] = c.get("resourceType", "contained").lower()
    return found

def eob_type(eob):
    for c in (eob.get("type") or {}).get("coding", []):
        if "eob-type" in c.get("system", ""): return c.get("code")
    return ((eob.get("type") or {}).get("coding") or [{}])[0].get("code")

def eob_paid(eob):
    v = ((eob.get("payment") or {}).get("amount") or {}).get("value")
    if v is not None: return float(v)
    for t in eob.get("total", []) or []:
        code = ((t.get("category") or {}).get("coding") or [{}])[0].get("code", "")
        if code in ("benefit", "paidtoprovider", "paidbyinsurer"): return float((t.get("amount") or {}).get("value") or 0)
    # fall back to summing line-level adjudication amounts that look like payments
    s = 0.0
    for it in eob.get("item", []) or []:
        for a in it.get("adjudication", []) or []:
            code = ((a.get("category") or {}).get("coding") or [{}])[0].get("code", "")
            if code in ("benefit", "paidtoprovider") or code.endswith("_pmt_amt"):
                s += float((a.get("amount") or {}).get("value") or 0)
    return round(s, 2) if s else None

def eob_codes(eob):
    out = []
    for it in eob.get("item", []) or []:
        for c in (it.get("productOrService") or {}).get("coding", []) or []:
            if c.get("code"): out.append(c["code"])
    return out

def normalize_eobs(bundle):
    claims = []
    entries = bundle.get("entry") if isinstance(bundle, dict) else None
    for e in (entries if isinstance(entries, list) else []):
        if not isinstance(e, dict): continue
        eob = e.get("resource", e)
        if not isinstance(eob, dict) or eob.get("resourceType") != "ExplanationOfBenefit": continue
        bp = eob.get("billablePeriod") or {}
        npis = eob_npis(eob)
        claims.append(dict(id=eob.get("id"), type=eob_type(eob), start=_date(bp.get("start")), end=_date(bp.get("end")),
                           npis=sorted(npis), roles=npis, paid=eob_paid(eob), codes=eob_codes(eob)[:12],
                           diagnoses=[((d.get("diagnosisCodeableConcept") or {}).get("coding") or [{}])[0].get("code") for d in (eob.get("diagnosis") or [])][:6]))
    return claims
