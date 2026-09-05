"""Grounds mapping, dash cleaning, strict schemas and the deterministic packet (no warehouse, no network)."""
import os, sys, json
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "api"))
import grounds, llm

def test_grounds_come_from_evidence_types_not_keywords():
    g = grounds.grounds_for_types(["MEDICARE_REVOKED_PAID_AFTER"])
    cfrs = [x["cfr"] for x in g]
    assert "455.416(c)" in cfrs and "455.436" in cfrs and "455.23" in cfrs
    assert all(x["text"] for x in g)
    # Medicaid referral grounds must not be the Medicare-only rule alone
    assert cfrs[0] != "424.535(a)"
    g2 = grounds.grounds_for_types(["OIG_LEIE_PAID_AFTER"]); assert "1001.1901" in [x["cfr"] for x in g2]
    g3 = grounds.grounds_for_types([]); assert [x["cfr"] for x in g3] == ["455.410"]

def test_evidence_types_are_derived_from_structured_bundle():
    ev = {"kind": "provider", "flags": [{"detector": "D3", "evidence": {"source": "OIG_LEIE"}}, {"detector": "D2", "evidence": {"label": "IMPOSSIBLE_CONCURRENT_3ORGS"}}], "revoked": [], "leie": [{"npi": "1"}], "features": {}}
    t = grounds.evidence_types(ev)
    assert "OIG_LEIE_PAID_AFTER" in t and any(x.startswith("IMPOSSIBLE") for x in t)
    assert "MEDICARE_REVOKED_PAID_AFTER" not in t

def test_clean_text_removes_every_dash_variant():
    s = llm.clean_text({"a": "before — after", "b": ["2019–2024", "x‒y"], "c": 3})
    flat = json.dumps(s)
    assert "—" not in flat and "–" not in flat and "‒" not in flat
    assert s["a"] == "before, after" and s["b"][0] == "2019 to 2024" and s["c"] == 3

def test_strict_schema_sets_additional_properties_false_everywhere():
    schema = {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "object", "properties": {"n": {"type": "integer"}}}}}}
    out = llm.strict_schema(schema)
    assert out["additionalProperties"] is False and out["properties"]["rows"]["items"]["additionalProperties"] is False

def test_cfr_texts_have_no_dashes_and_cover_every_mapped_ground():
    for t, gs in grounds.MAP.items():
        for g in gs: assert g in grounds.CFR, (t, g)
    for k, v in grounds.CFR.items(): assert "—" not in v and "–" not in v, k
