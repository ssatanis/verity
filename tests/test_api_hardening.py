"""Request hardening for the FastAPI service: malformed or hostile input must come back as 400 or 422, never a 500.
These tests need no warehouse, no Postgres and no model key; every request is rejected before any backend is touched."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "api"))
from fastapi.testclient import TestClient
import main
client = TestClient(main.app, raise_server_exceptions=False)

def test_packets_reject_bad_subject():
    assert client.post("/packets", json={"subject_type": "../x", "subject_id": "y"}).status_code == 400
    assert client.post("/packets", json={"subject_type": "provider", "subject_id": "abc"}).status_code == 400
    assert client.post("/packets", json={"subject_type": "cluster", "subject_id": "../../etc"}).status_code == 400
    assert client.post("/packets", json={"subject_type": "provider"}).status_code == 422

def test_reviews_reject_bad_ids_and_decisions():
    assert client.post("/reviews", json={"packet_id": "nope", "decision": "accept"}).status_code == 400
    assert client.post("/reviews", json={"packet_id": "b06d4000-94f1-464c-8ec7-9e401c274aa7", "decision": "maybe"}).status_code == 400
    assert client.post("/reviews", data="not json", headers={"content-type": "application/json"}).status_code == 422

def test_retrain_only_known_detectors():
    assert client.post("/retrain/evil").status_code == 400

def test_ask_rejects_bad_subject_before_the_model():
    assert client.post("/ask", json={"subject_type": "x", "subject_id": "y", "question": "q"}).status_code == 400
    assert client.post("/ask", json={"subject_type": "provider", "subject_id": "x", "question": "q"}).status_code == 400
    assert client.post("/ask", json={"subject_type": "provider", "subject_id": "1811937436", "question": "   "}).status_code == 400

def test_verify_npi_rejects_non_npi():
    assert client.get("/verify/npi/%27").status_code == 400
    assert client.get("/verify/npi/abc").status_code == 400

def test_bundle_shapes_never_500():
    for bundle in ({"entry": "x"}, {"entry": [1, "a", None]}, {"entry": [{"resource": {"resourceType": "ExplanationOfBenefit", "billablePeriod": {"start": 123}, "careTeam": "x"}}]},
                   {"entry": [{"resource": {"resourceType": "ExplanationOfBenefit", "payment": {"amount": {"value": "abc"}}}}]}, {"entry": [{"resource": {"resourceType": "ExplanationOfBenefit", "item": "x"}}]}):
        r = client.post("/bluebutton/verify-bundle", json={"bundle": bundle})
        assert r.status_code in (200, 400), (bundle, r.status_code, r.text[:200])
        if r.status_code == 200: assert r.json()["claims"] == 0
    assert client.post("/bluebutton/verify-bundle", json={"bundle": []}).status_code == 422

def test_bluebutton_callback_needs_state_and_code():
    r = client.get("/bluebutton/callback?code=x")
    assert r.status_code in (400, 403, 503)
