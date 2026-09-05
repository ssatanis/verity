"""Unit tests for the pieces the detectors depend on (no warehouse needed)."""
import importlib.util, os, re, sys, types
import duckdb, numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, "detectors")); sys.path.insert(0, os.path.join(ROOT, "api"))

def npi_luhn_python(n):
    if not re.fullmatch(r"[12]\d{9}", n): return False
    s = 24
    for i, ch in enumerate(n[:9]):
        d = int(ch)
        if i % 2 == 0: d *= 2; d = d - 9 if d > 9 else d
        s += d
    return int(n[9]) == (10 - s % 10) % 10

def test_npi_check_digit_macro_matches_reference():
    src = open(os.path.join(ROOT, "detectors/d3_revoked_but_paid.py")).read()
    macro = re.search(r'con\.execute\("""(CREATE OR REPLACE MACRO npi_luhn_ok.*?)"""\)', src, re.S).group(1)
    con = duckdb.connect(); con.execute(macro)
    known_good = ["1234567893", "1497364087", "1093316739", "1346979028", "1982736492", "1962546176"]
    for n in known_good: assert npi_luhn_python(n), n
    rng = np.random.default_rng(0); sample = ["1" + "".join(str(x) for x in rng.integers(0, 10, 9)) for _ in range(2000)] + known_good
    got = dict(con.execute("SELECT n, npi_luhn_ok(n) FROM (SELECT unnest(?) AS n)", [sample]).fetchall())
    assert all(got[n] == npi_luhn_python(n) for n in sample)
    assert sum(got.values()) >= 6 and sum(got.values()) < 400   # roughly one in ten random strings pass

def test_address_and_person_keys():
    spec = importlib.util.spec_from_file_location("d1", os.path.join(ROOT, "detectors/d1_ghost_networks.py"))
    src = open(spec.origin).read()
    # load only the helper section (before data access)
    helpers = src[src.index("USPS = {"):src.index("# ------------------------------------------------------------------ A. load providers")]
    ns = {}; exec("import re, math\nimport usaddress\nfrom nameparser import HumanName\n" + helpers, ns)
    b1, u1 = ns["addr_keys"]("6320 Van Nuys Boulevard, Suite 200", None, "91401-1234")
    b2, u2 = ns["addr_keys"]("6320 VAN NUYS BLVD", "STE 200", "914011234")
    b3, u3 = ns["addr_keys"]("6320 Van Nuys Blvd Ste 300", "", "91401")
    assert b1 == b2 == b3 == "6320 VAN NUYS BLVD|91401"
    assert u1 == u2 == "6320 VAN NUYS BLVD|91401#200" and u3.endswith("#300")
    assert ns["addr_keys"]("PO BOX 12", None, "90210") == (None, None)
    assert ns["phone_key"]("(818) 555-0199") == "8185550199" and ns["phone_key"]("1-818-555-0199") == "8185550199" and ns["phone_key"]("0000000000") is None
    assert ns["org_key"]("Sunrise Hospice Care, LLC") == ns["org_key"]("SUNRISE HOSPICE CARE INC.") == "SUNRISE HOSPICE CARE"
    assert ns["person_parts"]("Robert", "O'Neil-Smith", "J") == ("ONEILSMITH", "ROBERT", "J")
    assert ns["soundex"]("Robert") == ns["soundex"]("Rupert") == "R163" and ns["soundex"]("Tymczak") == "T522"

def test_fellegi_sunter_em_separates_matches():
    # synthetic comparison vectors: 200 true matches (high agreement) and 4000 non-matches (low agreement)
    rng = np.random.default_rng(1); levels = [3, 4, 3, 4, 3, 3]
    def draw(n, agree):
        return np.column_stack([rng.choice(L, size=n, p=(np.linspace(1, 3, L) ** (3 if agree else -3)) / (np.linspace(1, 3, L) ** (3 if agree else -3)).sum()) for L in levels])
    G = np.vstack([draw(200, True), draw(4000, False)]); truth = np.r_[np.ones(200, bool), np.zeros(4000, bool)]
    m = []; u = []
    for k, Lk in enumerate(levels):
        mk = np.full(Lk, 0.05); mk[-1] = 0.8; m.append(mk / mk.sum()); ck = np.bincount(G[:, k], minlength=Lk) + 1.0; u.append(ck / ck.sum())
    lam = 0.1
    for _ in range(60):
        logm = sum(np.log(m[k][G[:, k]]) for k in range(6)); logu = sum(np.log(u[k][G[:, k]]) for k in range(6))
        pm = lam * np.exp(logm); pu = (1 - lam) * np.exp(logu); post = pm / (pm + pu); lam = post.mean()
        for k, Lk in enumerate(levels):
            mk = np.bincount(G[:, k], weights=post, minlength=Lk) + 1e-3; m[k] = mk / mk.sum(); uk = np.bincount(G[:, k], weights=1 - post, minlength=Lk) + 1e-3; u[k] = uk / uk.sum()
    pred = post >= 0.95
    precision = (pred & truth).sum() / max(pred.sum(), 1); recall = (pred & truth).sum() / truth.sum()
    assert abs(lam - 200 / 4200) < 0.02 and precision > 0.95 and recall > 0.8

def test_packet_grounds_and_evidence_shape():
    import packet
    ev = dict(kind="provider", provider=dict(npi="1234567893", name="TEST LAB", entity_type="2", city="X", state="MO", taxonomy="291U00000X", medicaid_state="MO"),
              flags=[dict(detector="D3", evidence=dict(source="MEDICARE_REVOKED", event_dt="2018-08-31", reason="424.535(A)(3) Felonies", paid_after=100.0, months_paid_after=3, first_month_after="2018-09", last_month_after="2018-11", paid_before_12m=50.0), month="2018-09-01", value=100, dollars=100, metric="m", threshold=0)],
              revoked=[dict(npi="1234567893", revoked_dt="2018-08-31", revocation_rsn="424.535(A)(3) Felonies", reenroll_bar_dt="2028-08-31")], leie=[], enrollments=[], clusters=[])
    p = packet.deterministic_packet(ev)
    cfrs = {g["cfr"] for g in p["grounds"]}
    assert {"424.535(a)(12)", "455.416(c)", "455.23"} <= cfrs and p["findings"] and all(all(0 <= i < len(p["evidence"]) for i in f["evidence_ids"]) for f in p["findings"])
