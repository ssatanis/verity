#!/usr/bin/env python3
"""Detector 1: ghost provider networks.

Graph: hospice, home health agency and skilled nursing facility enrollments (CMS PECOS public files) linked to
  - owners and managing employees (CMS All-Owners; identity resolved with PECOS associate IDs, exact keys and a
    Fellegi-Sunter model fitted by EM),
  - practice, mailing and owner addresses (USPS-normalised; unit-level and building-level keys),
  - NPPES practice phones, fax numbers, authorised officials and secondary practice locations,
  - changes of ownership (SNF and hospital CHOW files),
with hub nodes (national chains, large medical buildings, corporate phone banks) held out of component formation.
Components are split with Leiden where large. Every community gets structural features (incorporation bursts, address and owner
sharing, phone sharing), label links (LEIE, SAM, Medicare revocations, Medicaid terminations, state exclusions, NPI deactivations),
market context (CMS Market Saturation providers per 10k FFS beneficiaries in the county, moratorium flag), dollars (Medicaid 2024,
Medicare PAC PUF 2023) and a robust-z composite score. Chains and private-equity platforms are scored but excluded from the ranked list.
"""
import argparse, json, math, os, re, sys, time
from collections import defaultdict
import duckdb, numpy as np, pandas as pd, networkx as nx, usaddress
from nameparser import HumanName
from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT); sys.path.insert(0, "detectors")
from _methods import write_section, md_table
ap = argparse.ArgumentParser(); ap.add_argument("--types", default="HOSPICE,HHA,SNF"); a = ap.parse_args()
PTYPES = a.types.split(",")
T0 = time.time()
def log(*x): print(f"[{time.time()-T0:6.0f}s]", *x, flush=True)
con = duckdb.connect(os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"))
con.execute("SET memory_limit='8GB'"); con.execute("SET threads=8"); con.execute("SET temp_directory='data/tmp_duckdb'")

# ------------------------------------------------------------------ normalisation helpers
USPS = {"STREET":"ST","AVENUE":"AVE","BOULEVARD":"BLVD","ROAD":"RD","DRIVE":"DR","LANE":"LN","COURT":"CT","PLACE":"PL","NORTH":"N","SOUTH":"S","EAST":"E","WEST":"W",
        "HIGHWAY":"HWY","PARKWAY":"PKWY","CIRCLE":"CIR","TERRACE":"TER","TRAIL":"TRL","WAY":"WAY","SUITE":"STE","BUILDING":"BLDG","FLOOR":"FL","UNIT":"UNIT","APARTMENT":"APT",
        "NORTHEAST":"NE","NORTHWEST":"NW","SOUTHEAST":"SE","SOUTHWEST":"SW","EXPRESSWAY":"EXPY","FREEWAY":"FWY","TURNPIKE":"TPKE","SQUARE":"SQ","CENTER":"CTR","PLAZA":"PLZ"}
def _norm_tok(p): p = p.upper().strip(". ,#"); return USPS.get(p, p)
def addr_keys(line1, line2, zip_):
    """Returns (building_key, unit_key). building = number + street + zip5; unit adds the secondary designator."""
    z = re.sub(r"[^0-9]", "", str(zip_ or ""))[:5]
    raw = " ".join(str(x) for x in (line1, line2) if x and str(x).strip())
    if not raw or not z: return None, None
    try: t, _ = usaddress.tag(raw)
    except usaddress.RepeatedLabelError: t = {}
    num = re.sub(r"[^0-9A-Z]", "", str(t.get("AddressNumber", "")).upper())
    parts = [t.get("StreetNamePreDirectional", ""), t.get("StreetName", ""), t.get("StreetNamePostType", ""), t.get("StreetNamePostDirectional", "")]
    street = " ".join(_norm_tok(p) for p in parts if p)
    street = re.sub(r"[^A-Z0-9 ]", "", street).strip()
    if not num or not street: return None, None
    unit = re.sub(r"[^A-Z0-9]", "", str(t.get("OccupancyIdentifier", "")).upper())
    b = f"{num} {street}|{z}"
    return b, (f"{b}#{unit}" if unit else None)
def phone_key(p):
    d = re.sub(r"[^0-9]", "", str(p or ""))
    if len(d) == 11 and d[0] == "1": d = d[1:]
    if len(d) != 10 or len(set(d)) < 3 or d[:3] in ("000", "111", "999"): return None
    return d
CORP = re.compile(r"\b(LLC|L L C|INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|LTD|LIMITED|PC|P C|LP|L P|LLP|PLLC|LLLP|HOLDINGS?|GROUP|ENTERPRISES?|PARTNERS(HIP)?|TRUST|THE)\b")
def org_key(n):
    s = re.sub(r"[^A-Z0-9 ]", " ", str(n or "").upper()); s = CORP.sub(" ", s); s = re.sub(r"\s+", " ", s).strip()
    return s or None
def person_parts(first, last, middle=None):
    if not last: return None
    hn = HumanName(f"{first or ''} {middle or ''} {last}".strip())
    ln = re.sub(r"[^A-Z]", "", (hn.last or str(last)).upper()); fn = re.sub(r"[^A-Z]", "", (hn.first or str(first or "")).upper()); mi = re.sub(r"[^A-Z]", "", (hn.middle or str(middle or "")).upper())[:1]
    return (ln, fn, mi) if ln else None
def soundex(s):
    s = re.sub(r"[^A-Z]", "", str(s).upper())
    if not s: return ""
    codes = {**dict.fromkeys("BFPV", "1"), **dict.fromkeys("CGJKQSXZ", "2"), **dict.fromkeys("DT", "3"), "L": "4", **dict.fromkeys("MN", "5"), "R": "6"}
    out = s[0]; last = codes.get(s[0], "")
    for ch in s[1:]:
        c = codes.get(ch, "")
        if c and c != last: out += c
        if ch not in "HW": last = c
    return (out + "000")[:4]
class DSU:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x: self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): ra, rb = self.find(a), self.find(b); self.p[rb] = ra if ra != rb else ra

# ------------------------------------------------------------------ A. load providers and owners
tsel = ",".join(f"'{t}'" for t in PTYPES)
prov = con.execute(f"""
SELECT p.ptype, p."ENROLLMENT ID" AS enrollment_id, p."NPI" AS npi, p."CCN" AS ccn, p."ASSOCIATE ID" AS associate_id, p."ORGANIZATION NAME" AS org_name,
       p."DOING BUSINESS AS NAME" AS dba, p.inc_date, p."INCORPORATION STATE" AS inc_state, p."ORGANIZATION TYPE STRUCTURE" AS org_structure,
       p."PROPRIETARY_NONPROFIT" AS proprietary, p."ADDRESS LINE 1" AS addr1, p."ADDRESS LINE 2" AS addr2, p."CITY" AS city, p."STATE" AS state, p.zip5, p."ZIP CODE" AS zip9,
       n.addr1 AS np_addr1, n.addr2 AS np_addr2, n.city AS np_city, n.state AS np_state, n.zip5 AS np_zip5, n.mail_addr1, n.mail_city, n.mail_state, n.mail_zip5,
       n.phone AS np_phone, n.fax AS np_fax, n.ao_first, n.ao_last, n.ao_phone, n.ein, n.enum_date, n.deact_date, n.taxonomy, n.parent_org_lbn, n.other_org_name,
       zc.county_fips, zc.county_name
FROM (SELECT 'HOSPICE' AS ptype, * FROM hospice UNION ALL BY NAME SELECT 'HHA' AS ptype, * FROM hha UNION ALL BY NAME SELECT 'SNF' AS ptype, * FROM snf) p
LEFT JOIN nppes n ON n.npi = p."NPI" LEFT JOIN zcta_primary_county zc ON zc.zcta = p.zip5
WHERE p.ptype IN ({tsel})""").df()
own = con.execute(f"""SELECT * FROM owners WHERE ptype IN ({tsel})""").df()
own.columns = [(c.replace(" - OWNER", "").replace(" ", "_").lower() + "_owner") if c.endswith(" - OWNER") else c.replace(" ", "_").lower() for c in own.columns]  # "ORGANIZATION NAME" (enrollee) and "ORGANIZATION NAME - OWNER" must not collide
log(f"providers {len(prov):,} ({prov.ptype.value_counts().to_dict()}), owner rows {len(own):,}")

# keys
b_u = [addr_keys(a1, a2, z) for a1, a2, z in zip(prov.addr1, prov.addr2, prov.zip9)]
prov["addr_b"], prov["addr_u"] = [x[0] for x in b_u], [x[1] for x in b_u]
b_u = [addr_keys(a1, a2, z) for a1, a2, z in zip(prov.np_addr1, prov.np_addr2, prov.np_zip5)]
prov["np_addr_b"], prov["np_addr_u"] = [x[0] for x in b_u], [x[1] for x in b_u]
b_u = [addr_keys(a1, None, z) for a1, z in zip(prov.mail_addr1, prov.mail_zip5)]
prov["mail_addr_b"] = [x[0] for x in b_u]
prov["phone_k"] = [phone_key(p) for p in prov.np_phone]; prov["fax_k"] = [phone_key(p) for p in prov.np_fax]
prov["ao_key"] = [(f"{pp[0]}|{pp[1][:3]}|{phone_key(ph) or st}" if (pp := person_parts(f, l)) else None) for f, l, ph, st in zip(prov.ao_first, prov.ao_last, prov.ao_phone, prov.state)]
prov["ein_k"] = [e if (e and re.fullmatch(r"\d{9}", str(e))) else None for e in prov.ein]
prov["org_k"] = [org_key(n) for n in prov.org_name]
prov["date_new"] = pd.to_datetime(prov.inc_date, errors="coerce").fillna(pd.to_datetime(prov.enum_date, errors="coerce"))
b_u = [addr_keys(a1, a2, z) for a1, a2, z in zip(own.address_line_1_owner, own.address_line_2_owner, own.zip_code_owner)]
own["oaddr_b"], own["oaddr_u"] = [x[0] for x in b_u], [x[1] for x in b_u]
own["is_person"] = own.type_owner == "I"
prov_loc = prov.set_index("enrollment_id")[["zip5", "city", "state"]]
own["zip5"] = own.zip_code_owner.fillna("").str[:5]
_blank = own.zip5 == ""
own.loc[_blank, "zip5"] = own.loc[_blank, "enrollment_id"].map(prov_loc.zip5).fillna("")
own["city_owner"] = own.city_owner.where(own.city_owner.fillna("") != "", own.enrollment_id.map(prov_loc.city))
own["state_owner"] = own.state_owner.where(own.state_owner.fillna("") != "", own.enrollment_id.map(prov_loc.state))
own["loc_is_proxy"] = _blank
pp = [person_parts(f, l, m) if ip else None for f, l, m, ip in zip(own.first_name_owner, own.last_name_owner, own.middle_name_owner, own.is_person)]
own["p_last"] = [x[0] if x else None for x in pp]; own["p_first"] = [x[1] if x else None for x in pp]; own["p_mi"] = [x[2] if x else None for x in pp]
own["org_k"] = [org_key(n) if not ip else None for n, ip in zip(own.organization_name_owner, own.is_person)]
own["pct"] = pd.to_numeric(own.percentage_ownership, errors="coerce").fillna(0)
own["assoc_dt"] = pd.to_datetime(own.association_date_owner, errors="coerce")
own["role_class"] = np.where(own.role_code_owner.isin(["34", "35", "85", "86", "36", "37", "38"]), "owner", np.where(own.role_code_owner.isin(["42", "25", "43", "72"]), "managing", "governance"))
own["chain"] = own.get("chain_home_office_owner", pd.Series(index=own.index)).eq("Y"); own["pe"] = own.get("private_equity_company_owner", pd.Series(index=own.index)).eq("Y")
prov_ids = set(prov.enrollment_id); own = own[own.enrollment_id.isin(prov_ids)].reset_index(drop=True)
log(f"keys built; owner rows on selected providers {len(own):,} (persons {int(own.is_person.sum()):,})")

# ------------------------------------------------------------------ B. entity resolution for owner persons (PECOS ID + exact key + Fellegi-Sunter/EM)
per = own[own.is_person & own.p_last.notna()].copy()
per["exact_key"] = per.p_last + "|" + per.p_first.str[:3] + "|" + per.zip5
dsu = DSU(); aid_col = "associate_id_owner"
for i, aid in zip(per.index, per[aid_col]):
    if aid: dsu.union(("aid", aid), ("rec", i))
for i, k in zip(per.index, per.exact_key):
    if k and "|" in k and not k.endswith("|"): dsu.union(("key", k), ("rec", i))
# representatives after deterministic merging
per["det_id"] = [dsu.find(("rec", i)) for i in per.index]
def _first_str(s, f=lambda x: x):
    for x in s:
        if isinstance(x, str) and x: return f(x)
    return ""
rep = per.groupby("det_id").agg(p_last=("p_last", "first"), p_first=("p_first", "first"), p_mi=("p_mi", _first_str),
                                zip5=("zip5", _first_str), city=("city_owner", lambda s: _first_str(s, lambda x: x.upper())),
                                state=("state_owner", _first_str), street=("oaddr_b", lambda s: _first_str(s, lambda x: x.split("|")[0].split(" ")[0])),
                                n=("p_last", "size")).reset_index()
rep["p_first"] = rep.p_first.fillna(""); rep["p_last"] = rep.p_last.fillna("")
log(f"person records {len(per):,} -> {len(rep):,} after PECOS-ID and exact-key merging; fitting Fellegi-Sunter")
# candidate pairs: same state and (same last name, or same soundex(last) + first initial)
rep["snd"] = [soundex(x) for x in rep.p_last]; rep["fi"] = rep.p_first.str[:1]
pairs = set()
for key_cols in (["state", "p_last"], ["state", "snd", "fi"]):
    for _, g in rep.groupby(key_cols):
        idx = g.index.to_numpy()
        if len(idx) < 2: continue
        if len(idx) > 400: idx = idx[np.argsort(g.zip5.to_numpy())]  # very common names: only neighbours in zip order
        for i in range(len(idx)):
            for j in range(i + 1, min(len(idx), i + (400 if len(idx) <= 400 else 6))):
                pairs.add((min(idx[i], idx[j]), max(idx[i], idx[j])))
pairs = np.array(sorted(pairs)) if pairs else np.zeros((0, 2), int)
log(f"candidate pairs {len(pairs):,}")
L = rep.p_last.to_numpy(); F = rep.p_first.to_numpy(); M = rep.p_mi.to_numpy(); Z = rep.zip5.to_numpy(); C = rep.city.to_numpy(); S = rep.street.to_numpy()
def lvl_last(a, b): return 2 if a == b else (1 if JaroWinkler.normalized_similarity(a, b) >= 0.92 else 0)
def lvl_first(a, b):
    if not a or not b: return 1
    if a == b: return 3
    if JaroWinkler.normalized_similarity(a, b) >= 0.9 or (len(a) >= 3 and len(b) >= 3 and (a.startswith(b) or b.startswith(a))): return 2
    return 1 if a[0] == b[0] else 0
def lvl_mi(a, b): return 1 if (not a or not b) else (2 if a == b else 0)
def lvl_zip(a, b): return 1 if (not a or not b) else (3 if a == b else (2 if a[:3] == b[:3] else 0))
def lvl_city(a, b): return 1 if (not a or not b) else (2 if a == b else 0)
def lvl_street(a, b): return 1 if (not a or not b) else (2 if a == b else 0)
if len(pairs):
    G = np.array([[lvl_last(L[i], L[j]), lvl_first(F[i], F[j]), lvl_mi(M[i], M[j]), lvl_zip(Z[i], Z[j]), lvl_city(C[i], C[j]), lvl_street(S[i], S[j])] for i, j in pairs], dtype=int)
    levels = [3, 4, 3, 4, 3, 3]
    m = []; u = []
    for k, Lk in enumerate(levels):
        mk = np.full(Lk, 0.05); mk[-1] = 0.8; mk[1] = 0.1 if Lk > 2 else mk[1]; m.append(mk / mk.sum())
        ck = np.bincount(G[:, k], minlength=Lk) + 1.0; u.append(ck / ck.sum())
    lam = 0.1
    for it in range(60):
        logm = sum(np.log(m[k][G[:, k]]) for k in range(6)); logu = sum(np.log(u[k][G[:, k]]) for k in range(6))
        pm = lam * np.exp(logm); pu = (1 - lam) * np.exp(logu); post = pm / (pm + pu)
        lam = float(post.mean())
        for k, Lk in enumerate(levels):
            mk = np.bincount(G[:, k], weights=post, minlength=Lk) + 1e-3; m[k] = mk / mk.sum()
            uk = np.bincount(G[:, k], weights=1 - post, minlength=Lk) + 1e-3; u[k] = uk / uk.sum()
    weight = sum(np.log2(m[k][G[:, k]] / u[k][G[:, k]]) for k in range(6))
    # a match needs posterior >= 0.95 and at least one locational agreement (zip5, street number or city), never names alone
    loc_ok = (G[:, 3] == 3) | (G[:, 5] == 2) | ((G[:, 3] == 2) & (G[:, 4] == 2))
    matched = (post >= 0.95) & loc_ok & (G[:, 0] >= 1) & (G[:, 1] >= 2)
    for (i, j) in pairs[matched]: dsu.union(("rep", i), ("rep", j))
    # keep every candidate pair with its comparison vector and posterior; the borderline band (0.2 to 0.98) is adjudicated by the model
    cand = pd.DataFrame({"i": pairs[:, 0], "j": pairs[:, 1], "posterior": post, "weight": weight, "matched": matched,
                         "g_last": G[:, 0], "g_first": G[:, 1], "g_mi": G[:, 2], "g_zip": G[:, 3], "g_city": G[:, 4], "g_street": G[:, 5]})
    for side in ("i", "j"):
        for col in ("p_last", "p_first", "p_mi", "zip5", "city", "state", "street"):
            cand[f"{col}_{side}"] = rep[col].to_numpy()[cand[side].to_numpy()]
    cand["det_id_i"] = rep.det_id.to_numpy()[cand.i.to_numpy()]; cand["det_id_j"] = rep.det_id.to_numpy()[cand.j.to_numpy()]
    con.execute("CREATE OR REPLACE TABLE d1_er_candidates AS SELECT * FROM cand")
    log(f"saved {len(cand):,} candidate pairs; borderline band 0.2 to 0.98: {int(((post >= 0.2) & (post < 0.98)).sum()):,}")
    fs_stats = dict(pairs=int(len(pairs)), matched=int(matched.sum()), lam=round(lam, 4), m=[np.round(x, 3).tolist() for x in m], u=[np.round(x, 3).tolist() for x in u],
                    pct_persons_with_zip=round(100 * float((per.zip5.fillna("") != "").mean()), 1), pct_persons_with_state=round(100 * float((per.state_owner.fillna("") != "").mean()), 1))
    log(f"owner persons with ZIP {fs_stats['pct_persons_with_zip']}%, with state {fs_stats['pct_persons_with_state']}%; m={fs_stats['m']}; u={fs_stats['u']}")
    log(f"Fellegi-Sunter: {matched.sum():,} of {len(pairs):,} candidate pairs matched (lambda={lam:.4f})")
else: fs_stats = {}
rep["person_id"] = [dsu.find(("rep", i)) for i in rep.index]
det2person = dict(zip(rep.det_id, rep.person_id)); per["person_id"] = per.det_id.map(det2person)
own["person_id"] = per.person_id.reindex(own.index)
# person labels
plabel = per.groupby("person_id").apply(lambda g: f"{g.first_name_owner.iloc[0] or ''} {g.last_name_owner.iloc[0] or ''}".strip().title()).to_dict()
# org owners: PECOS ID, then normalised name + state, then fuzzy token-set within state
org = own[~own.is_person & own.org_k.notna()].copy()
dsu_o = DSU()
for i, aid, k, st in zip(org.index, org[aid_col], org.org_k, org.state_owner.fillna("")):
    if aid: dsu_o.union(("aid", aid), ("rec", i))
    dsu_o.union(("key", f"{k}|{st}"), ("rec", i))
org["det_id"] = [dsu_o.find(("rec", i)) for i in org.index]
orep = org.groupby("det_id").agg(org_k=("org_k", "first"), state=("state_owner", "first")).reset_index()
for st, g in orep.groupby("state"):
    ks = g.org_k.tolist(); ids = g.det_id.tolist()
    if len(ks) < 2 or len(ks) > 3000: continue
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            if ks[i][:4] == ks[j][:4] and fuzz.token_set_ratio(ks[i], ks[j]) >= 94: dsu_o.union(ids[i], ids[j])
org["org_id"] = [dsu_o.find(d) for d in org.det_id]
own["org_id"] = org.org_id.reindex(own.index)
olabel = org.groupby("org_id").apply(lambda g: str(g.organization_name_owner.iloc[0]).title()).to_dict()
log(f"org owner records {len(org):,} -> {org.org_id.nunique():,} organisations; persons -> {per.person_id.nunique():,}")

# ------------------------------------------------------------------ C. labels
con.execute("CREATE OR REPLACE MACRO npi_luhn_ok(n) AS (n IS NOT NULL AND regexp_matches(n, '^[12][0-9]{9}$'))")  # check digit verified in D3; here presence is enough
lab_npi = defaultdict(set)
for npi, in con.execute("SELECT DISTINCT npi FROM revoked WHERE npi IS NOT NULL AND revoked_dt IS NOT NULL").fetchall(): lab_npi[npi].add("MEDICARE_REVOKED")
for npi, in con.execute("SELECT DISTINCT npi FROM leie WHERE npi IS NOT NULL").fetchall(): lab_npi[npi].add("OIG_LEIE")
for npi, in con.execute("SELECT DISTINCT npi FROM sam WHERE npi IS NOT NULL AND excluding_agency <> 'HHS'").fetchall(): lab_npi[npi].add("SAM")
for npi, st in con.execute("""SELECT DISTINCT s.npi, s.state FROM state_exclusions s JOIN nppes n ON n.npi = s.npi
                              WHERE s.npi IS NOT NULL AND list_has_any(list_filter(string_split(regexp_replace(upper(s.name),'[^A-Z ]',' ','g'),' '), x -> length(x)>=3),
                                    list_filter(string_split(regexp_replace(upper(COALESCE(n.org_name,'')||' '||COALESCE(n.first_name,'')||' '||COALESCE(n.last_name,'')),'[^A-Z ]',' ','g'),' '), x -> length(x)>=3))""").fetchall(): lab_npi[npi].add(f"STATE_EXCL_{st}")
for npi, in con.execute("""WITH latest AS (SELECT npi, state, status_cd FROM enroll QUALIFY ROW_NUMBER() OVER (PARTITION BY npi, state ORDER BY start_dt DESC) = 1),
                                bulk AS (SELECT state, status_cd, COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY state) AS share FROM enroll WHERE status_cd BETWEEN '60' AND '83' GROUP BY 1,2)
                           SELECT DISTINCT l.npi FROM latest l JOIN bulk b ON b.state = l.state AND b.status_cd = l.status_cd AND b.share <= 0.20
                           WHERE l.status_cd IN ('60','65','66','67','70','72','75','78','81')""").fetchall(): lab_npi[npi].add("MEDICAID_TERM")
for npi, in con.execute("SELECT npi FROM nppes WHERE deact_date IS NOT NULL AND react_date IS NULL").fetchall(): lab_npi[npi].add("NPI_DEACTIVATED")
rev_dates = dict(con.execute("SELECT npi, MIN(revoked_dt) FROM revoked WHERE npi IS NOT NULL GROUP BY 1").fetchall())
leie_dates = dict(con.execute("SELECT npi, MIN(excl_dt) FROM leie WHERE npi IS NOT NULL GROUP BY 1").fetchall())
# excluded persons and businesses without NPI: keyed by name and location (tiers: zip5 = high, state = medium)
leie_people = con.execute("SELECT lastname, firstname, midname, state, zip, excltype, excl_dt FROM leie WHERE busname = '' OR busname IS NULL").df()
leie_hi, leie_md = {}, {}
for r in leie_people.itertuples(index=False):
    pp_ = person_parts(r.firstname, r.lastname, r.midname)
    if not pp_: continue
    z = str(r.zip or "")[:5]
    leie_hi.setdefault(f"{pp_[0]}|{pp_[1][:3]}|{z}", (r.excltype, r.excl_dt)); leie_md.setdefault(f"{pp_[0]}|{pp_[1]}|{r.state}", (r.excltype, r.excl_dt))
leie_biz = {f"{org_key(b)}|{st}": (t, d) for b, st, t, d in con.execute("SELECT busname, state, excltype, excl_dt FROM leie WHERE busname <> '' AND busname IS NOT NULL").fetchall() if org_key(b)}
sam_people = con.execute("SELECT first_name, last_name, middle_name, state, zip5, excluding_agency, active_dt FROM sam WHERE classification = 'Individual' AND excluding_agency <> 'HHS' AND country = 'USA'").df()
sam_hi = {}
for r in sam_people.itertuples(index=False):
    pp_ = person_parts(r.first_name, r.last_name, r.middle_name)
    if pp_ and r.zip5: sam_hi.setdefault(f"{pp_[0]}|{pp_[1][:3]}|{r.zip5}", (r.excluding_agency, r.active_dt))
rev_people = con.execute("SELECT first_name, last_name, mdl_name, state, revoked_dt, revocation_rsn FROM revoked WHERE org_name IS NULL OR org_name = ''").df()
rev_md = {}
for r in rev_people.itertuples(index=False):
    pp_ = person_parts(r.first_name, r.last_name, r.mdl_name)
    if pp_: rev_md.setdefault(f"{pp_[0]}|{pp_[1]}|{r.state}", (r.revocation_rsn, r.revoked_dt))
def person_labels(g):
    """label links for a resolved person: list of (source, tier, detail)"""
    out = []
    seen = set()
    for r in g.itertuples(index=False):
        st = (r.state_owner if isinstance(r.state_owner, str) and r.state_owner else None) or (r.prov_state if isinstance(r.prov_state, str) else None)
        k_hi = f"{r.p_last}|{(r.p_first or '')[:3]}|{r.zip5}"; k_md = f"{r.p_last}|{r.p_first}|{st}"
        if r.zip5 and k_hi in leie_hi and ("OIG_LEIE", "high") not in seen: out.append(("OIG_LEIE", "high", leie_hi[k_hi])); seen.add(("OIG_LEIE", "high"))
        elif r.p_first and len(r.p_first) >= 3 and k_md in leie_md and ("OIG_LEIE", "medium") not in seen: out.append(("OIG_LEIE", "medium", leie_md[k_md])); seen.add(("OIG_LEIE", "medium"))
        if r.zip5 and k_hi in sam_hi and ("SAM", "high") not in seen: out.append(("SAM", "high", sam_hi[k_hi])); seen.add(("SAM", "high"))
        if r.p_first and len(r.p_first) >= 3 and k_md in rev_md and ("MEDICARE_REVOKED", "medium") not in seen: out.append(("MEDICARE_REVOKED", "medium", rev_md[k_md])); seen.add(("MEDICARE_REVOKED", "medium"))
    return out
prov_state_by_enr = dict(zip(prov.enrollment_id, prov.state))
per["prov_state"] = per.enrollment_id.map(prov_state_by_enr)
excl_addr, excl_unit = {}, {}
for a1, city, st, z, bus, ln, fn, t, d in con.execute("SELECT address, city, state, zip, busname, lastname, firstname, excltype, excl_dt FROM leie WHERE address IS NOT NULL AND address <> ''").fetchall():
    b, u = addr_keys(a1, None, z)
    if b and not re.match(r"^\d+ (PO BOX|P O BOX|BOX)", b):
        excl_addr.setdefault(b, ("OIG_LEIE", (bus or f"{fn} {ln}").strip(), str(d)))
        if u: excl_unit.setdefault(u, ("OIG_LEIE", (bus or f"{fn} {ln}").strip(), str(d)))
for npi, a1, a2, z, nm, d in con.execute("""SELECT r.npi, n.addr1, n.addr2, n.zip5, COALESCE(n.org_name, n.first_name || ' ' || n.last_name), r.revoked_dt FROM revoked r JOIN nppes n ON n.npi = r.npi WHERE n.addr1 IS NOT NULL AND n.entity_type = '2'""").fetchall():
    b, u = addr_keys(a1, a2, z)
    if b: excl_addr.setdefault(b, ("MEDICARE_REVOKED", nm, str(d)))
    if u: excl_unit.setdefault(u, ("MEDICARE_REVOKED", nm, str(d)))
log(f"excluded/revoked entity addresses indexed: {len(excl_addr):,} buildings, {len(excl_unit):,} suites")
person_lab = {pid: person_labels(g) for pid, g in per.groupby("person_id")}
person_lab = {k: v for k, v in person_lab.items() if v}
org_lab = {}
for oid, g in org.groupby("org_id"):
    hits = [leie_biz[k] for k in {f"{kk}|{st}" for kk, st in zip(g.org_k, g.state_owner.fillna(""))} if k in leie_biz]
    if hits: org_lab[oid] = [("OIG_LEIE", "high", h) for h in hits]
log(f"label sets: NPI-labelled providers {sum(1 for n in prov.npi if n in lab_npi):,}; persons with LEIE/SAM/revocation name links {len(person_lab):,}; org owners on LEIE {len(org_lab):,}")

# ------------------------------------------------------------------ D. graph
G = nx.Graph()
HUB = {"person": 40, "org": 25, "addr": 25, "unit": 12, "phone": 25, "fax": 25, "ao": 40, "mail": 25, "ein": 60}
def add_edge(u, v, **attr):
    if G.has_edge(u, v): G[u][v]["weight"] = max(G[u][v]["weight"], attr.get("weight", 1.0))
    else: G.add_edge(u, v, **attr)
for r in prov.itertuples(index=False):
    G.add_node(("prov", r.enrollment_id), kind="provider", ptype=r.ptype, npi=r.npi, ccn=r.ccn, label=str(r.org_name).title(), dba=r.dba, state=r.state, city=str(r.city).title(),
               zip5=r.zip5, county_fips=r.county_fips, county=r.county_name, inc_date=str(r.inc_date) if pd.notna(r.inc_date) else None,
               date_new=r.date_new, taxonomy=r.taxonomy, labels=sorted(lab_npi.get(r.npi, [])), org_structure=r.org_structure, proprietary=r.proprietary)
# owner edges
for r in own.itertuples(index=False):
    pid = ("prov", r.enrollment_id)
    if r.is_person and pd.notna(r.person_id): key = ("person", r.person_id)
    elif (not r.is_person) and pd.notna(r.org_id): key = ("org", r.org_id)
    else: continue
    if key not in G: G.add_node(key, kind=key[0], label=plabel.get(key[1], "") if key[0] == "person" else olabel.get(key[1], ""), labels=[])
    w = 1.0 if r.role_class == "owner" else (0.8 if r.role_class == "managing" else 0.6)
    add_edge(pid, key, rel=str(r.role_text_owner).title(), weight=w, pct=float(r.pct), assoc=str(r.assoc_dt.date()) if pd.notna(r.assoc_dt) else None, chain=bool(r.chain), pe=bool(r.pe))
    if r.oaddr_b: add_edge(key, ("addr", r.oaddr_b), rel="owner_address", weight=0.5)
# address / phone / AO / mailing / secondary location edges
for r in prov.itertuples(index=False):
    pid = ("prov", r.enrollment_id)
    for k in {r.addr_b, r.np_addr_b}:
        if k: add_edge(pid, ("addr", k), rel="located_at", weight=0.6)
    for k in {r.addr_u, r.np_addr_u}:
        if k: add_edge(pid, ("unit", k), rel="located_at_unit", weight=1.0)
    if r.mail_addr_b and r.mail_addr_b != r.addr_b: add_edge(pid, ("mail", r.mail_addr_b), rel="mailing_address", weight=0.5)
    if r.phone_k: add_edge(pid, ("phone", r.phone_k), rel="phone", weight=0.8)
    if r.fax_k and r.fax_k != r.phone_k: add_edge(pid, ("fax", r.fax_k), rel="fax", weight=0.6)
    if r.ao_key: add_edge(pid, ("ao", r.ao_key), rel="authorized_official", weight=0.9)
    if r.ein_k: add_edge(pid, ("ein", r.ein_k), rel="ein", weight=1.0)
npi2pid = defaultdict(list)
for r in prov.itertuples(index=False): npi2pid[r.npi].append(("prov", r.enrollment_id))
for npi, a1, a2, z in con.execute(f"SELECT npi, addr1, addr2, zip5 FROM nppes_locations WHERE npi IN (SELECT \"NPI\" FROM hospice UNION SELECT \"NPI\" FROM hha UNION SELECT \"NPI\" FROM snf)").fetchall():
    b, uk = addr_keys(a1, a2, z)
    for pid in npi2pid.get(npi, []):
        if b: add_edge(pid, ("addr", b), rel="secondary_location", weight=0.4)
# CHOW (buyer-seller) edges
for r in con.execute("""SELECT "ENROLLMENT ID - BUYER", "ENROLLMENT ID - SELLER", effective_dt FROM chow""").fetchall():
    b, s_, d = ("prov", r[0]), ("prov", r[1]), r[2]
    if b in G and s_ in G: add_edge(b, s_, rel="change_of_ownership", weight=0.7, chow_dt=str(d))
for n, d in G.nodes(data=True):
    d.setdefault("kind", n[0]); d.setdefault("labels", [])
    if d["kind"] != "provider": d["label"] = d.get("label") or (str(n[1]) if d["kind"] in ("addr", "unit", "mail", "phone", "fax", "ein") else (str(n[1]).split("|")[0].title() if d["kind"] == "ao" else ""))
# hub detection (degree to providers)
hubs = set()
for n, d in G.nodes(data=True):
    if d["kind"] == "provider": continue
    deg = sum(1 for v in G.neighbors(n) if G.nodes[v]["kind"] == "provider")
    d["prov_degree"] = deg
    if deg >= HUB.get(d["kind"], 30): hubs.add(n)
log(f"graph: {G.number_of_nodes():,} nodes, {G.number_of_edges():,} edges; hubs held out of components: {len(hubs):,} ({', '.join(f'{k}:{sum(1 for h in hubs if h[0]==k)}' for k in HUB)})")
# edge weights for shared nodes: divide building/mail/phone links by log2(1 + tenants) so big buildings and call centres count little
for n in G.nodes:
    d = G.nodes[n]
    if d["kind"] in ("addr", "mail", "phone", "fax") and d.get("prov_degree", 0) >= 6:
        f = 1.0 / math.log2(1 + d["prov_degree"])
        for v in G.neighbors(n): G[n][v]["weight"] = G[n][v]["weight"] * f

# ------------------------------------------------------------------ D2. provider plazas (addresses hosting many enrollments)
plaza_rows = []
for n, d in G.nodes(data=True):
    if d["kind"] not in ("addr", "unit") or d.get("prov_degree", 0) < 8: continue
    members = [v for v in G.neighbors(n) if G.nodes[v]["kind"] == "provider"]
    md = [G.nodes[v] for v in members]
    plaza_rows.append(dict(address=n[1], level=d["kind"], n_providers=len(members), n_hospice=sum(1 for x in md if x["ptype"] == "HOSPICE"), n_hha=sum(1 for x in md if x["ptype"] == "HHA"),
                           n_snf=sum(1 for x in md if x["ptype"] == "SNF"), n_since_2019=sum(1 for x in md if pd.notna(x["date_new"]) and x["date_new"] >= pd.Timestamp("2019-01-01")),
                           n_labelled=sum(1 for x in md if x["labels"]), revoked_entity_here=int(n[1] in excl_addr or n[1] in excl_unit), city=md[0]["city"], state=md[0]["state"], zip5=md[0]["zip5"],
                           county_fips=md[0]["county_fips"], npis=[x["npi"] for x in md], hub=n in hubs))
plazas = pd.DataFrame(plaza_rows).sort_values("n_providers", ascending=False) if plaza_rows else pd.DataFrame()
if len(plazas):
    plazas["npis"] = [json.dumps(x) for x in plazas.npis]; con.execute("CREATE OR REPLACE TABLE d1_hub_addresses AS SELECT * FROM plazas")
    log(f"provider plazas (8+ enrollments at one address): {len(plazas):,}; largest {plazas.iloc[0].address} with {plazas.iloc[0].n_providers}")

# ------------------------------------------------------------------ E. components and communities
H = G.subgraph([n for n in G.nodes if n not in hubs]).copy()
comps = []
try:
    import igraph as ig, leidenalg as la
    have_leiden = True
except Exception: have_leiden = False
for c in nx.connected_components(H):
    nprov = sum(1 for n in c if H.nodes[n]["kind"] == "provider")
    if nprov < 2: continue
    if nprov > 120 and have_leiden:
        sub = H.subgraph(c); nodes = list(sub.nodes); idx = {n: i for i, n in enumerate(nodes)}
        g = ig.Graph(n=len(nodes), edges=[(idx[u], idx[v]) for u, v in sub.edges], edge_attrs={"weight": [sub[u][v]["weight"] for u, v in sub.edges]})
        part = la.find_partition(g, la.RBConfigurationVertexPartition, weights="weight", resolution_parameter=1.0, seed=42)
        for comm in part:
            cset = {nodes[i] for i in comm}
            if sum(1 for n in cset if H.nodes[n]["kind"] == "provider") >= 2: comps.append(cset)
    else: comps.append(set(c))
log(f"communities with 2+ providers: {len(comps):,} (largest {max(sum(1 for n in c if H.nodes[n]['kind']=='provider') for c in comps)} providers)")

# ------------------------------------------------------------------ F. features
sat = con.execute("""SELECT type_of_service, lpad(state_fips, 2, '0') || lpad(county_fips, 3, '0') AS county_fips, providers_per_10k_ffs, moratorium, providers, ffs_beneficiaries FROM saturation_county
                     WHERE aggregation_level = 'COUNTY' AND reference_period = (SELECT MAX(reference_period) FROM saturation_county WHERE aggregation_level = 'COUNTY')
                       AND type_of_service IN ('Hospice','Home Health','Skilled Nursing Facility') AND state_fips <> '' AND county_fips <> ''""").df()
SVC = {"HOSPICE": "Hospice", "HHA": "Home Health", "SNF": "Skilled Nursing Facility"}
sat_stats = {}
for svc, g in sat.groupby("type_of_service"):
    v = np.log1p(g.providers_per_10k_ffs.dropna().to_numpy()); med = np.median(v); mad = np.median(np.abs(v - med)) or 1e-9
    sat_stats[svc] = (med, mad)
sat_lookup = {(r.type_of_service, r.county_fips): (r.providers_per_10k_ffs, r.moratorium) for r in sat.itertuples(index=False)}
med24 = dict(con.execute("SELECT billing_npi, SUM(paid) FROM spend_totals WHERE year = '2024' GROUP BY 1").fetchall())
medall = dict(con.execute("SELECT billing_npi, SUM(paid) FROM spend_totals GROUP BY 1").fetchall())
pac = {}
for f, ptype in (("data/cms_utilization/post_acute/2023_RY_2025_RY_25_PAC_PUF_HOS_2023_main_final_unformatted.csv", "HOSPICE"), ("data/cms_utilization/post_acute/2023_RY_2025_RY_25_PAC_PUF_HH_2023_main_final_unformatted.csv", "HHA")):
    if os.path.exists(f):
        cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_csv_auto('{f}', all_varchar=true, header=true)").fetchall()]
        extra = [c for c in cols if re.search(r"(LIVE_DSCHRG|180|GT_180|LOS|ALOS|AVG_LNGTH|STAY)", c, re.I)]
        rows = con.execute(f"""SELECT PRVDR_ID, TRY_CAST(TOT_MDCR_PYMT_AMT AS DOUBLE), TRY_CAST(BENE_DSTNCT_CNT AS DOUBLE){''.join(', TRY_CAST("'+c+'" AS DOUBLE)' for c in extra)} FROM read_csv_auto('{f}', all_varchar=true, header=true) WHERE SMRY_CTGRY = 'PROVIDER'""").fetchall()
        for r in rows: pac[r[0]] = dict(ptype=ptype, medicare_pay_2023=r[1], medicare_benes_2023=r[2], **{extra[i].lower(): r[3 + i] for i in range(len(extra))})
log(f"context: saturation counties {len(sat_lookup):,}, PAC PUF providers {len(pac):,}")

def burst(dates, window_days):
    ds = sorted(d for d in dates if pd.notna(d))
    if len(ds) < 2: return len(ds), None
    best, bi, bj = 1, 0, 0; j = 0
    for i in range(len(ds)):
        while j < len(ds) and (ds[j] - ds[i]).days <= window_days: j += 1
        if j - i > best: best, bi, bj = j - i, i, j - 1
    return best, (ds[bi].date(), ds[bj].date()) if best >= 2 else None
feat_rows, member_rows, graphs = [], [], {}
for ci, c in enumerate(comps):
    P = [n for n in c if G.nodes[n]["kind"] == "provider"]; pd_ = [G.nodes[n] for n in P]
    n_prov = len(P); types = pd.Series([d["ptype"] for d in pd_]).value_counts().to_dict()
    states = pd.Series([d["state"] for d in pd_]).value_counts(); state = states.index[0]; multi_state = int(len(states) > 1)
    cities = pd.Series([f"{d['city']}, {d['state']}" for d in pd_]).value_counts(); city = cities.index[0]
    counties = pd.Series([d["county_fips"] for d in pd_ if d["county_fips"]]).value_counts(); county = counties.index[0] if len(counties) else None
    dates = [d["date_new"] for d in pd_]
    # one date per distinct organisation (several enrollments of one legal entity share an incorporation date), recent = 2019 onward
    org_dates = {}
    for d in pd_:
        k = org_key(d["label"]) or d["label"]
        if pd.notna(d["date_new"]) and (k not in org_dates or d["date_new"] < org_dates[k]): org_dates[k] = d["date_new"]
    recent = [v for v in org_dates.values() if v >= pd.Timestamp("2019-01-01")]
    b90, b90_span = burst(recent, 90); b180, _ = burst(recent, 180); b365, _ = burst(recent, 365)
    n_distinct_orgs = len({org_key(d["label"]) or d["label"] for d in pd_})
    for_profit_ratio = sum(1 for d in pd_ if d.get("proprietary") == "P") / n_prov
    # same suite as an excluded or revoked entity counts fully; same building only half (medical office buildings have many tenants)
    excl_addr_hits = []
    for n in P:
        unit_hit = next((excl_unit[v[1]] for v in G.neighbors(n) if v[0] == "unit" and v[1] in excl_unit), None)
        bld_hit = next((excl_addr[v[1]] for v in G.neighbors(n) if v[0] == "addr" and v[1] in excl_addr), None)
        if unit_hit: excl_addr_hits.append((G.nodes[n]["label"], unit_hit, "same suite", 1.0))
        elif bld_hit: excl_addr_hits.append((G.nodes[n]["label"], bld_hit, "same building", 0.5))
    n_new = sum(1 for d in dates if pd.notna(d) and d >= pd.Timestamp("2021-01-01")); n_dated = sum(1 for d in dates if pd.notna(d))
    def share_stat(kind):
        best = 0; n_shared_nodes = 0
        for n in c:
            if G.nodes[n]["kind"] == kind:
                k = sum(1 for v in G.neighbors(n) if v in c and G.nodes[v]["kind"] == "provider")
                if k >= 2: n_shared_nodes += 1
                best = max(best, k)
        return best, n_shared_nodes
    addr_share, n_shared_addr = share_stat("addr"); unit_share, n_shared_unit = share_stat("unit"); phone_share, _ = share_stat("phone"); ao_share, _ = share_stat("ao"); mail_share, _ = share_stat("mail"); ein_share, _ = share_stat("ein")
    owners = [n for n in c if G.nodes[n]["kind"] in ("person", "org")]
    odeg = {n: sum(1 for v in G.neighbors(n) if v in c and G.nodes[v]["kind"] == "provider" and G[n][v].get("weight", 0) >= 0.8) for n in owners}   # ownership or managing roles only
    gdeg = {n: sum(1 for v in G.neighbors(n) if v in c and G.nodes[v]["kind"] == "provider") for n in owners}
    owner_multi = sum(1 for n, k in odeg.items() if k >= 3); max_owner_degree = max(odeg.values()) if odeg else 0
    governance_multi = sum(1 for n, k in gdeg.items() if k >= 3 and odeg.get(n, 0) < 3)
    n_persons = sum(1 for n in owners if n[0] == "person"); n_orgs = len(owners) - n_persons
    # in-community members sharing an address that also touches a hub chain? (chain flag from edges)
    chain_members = sum(1 for u in P if any((G[u][v].get("chain") or G[u][v].get("pe") or (v in hubs and G.nodes[v]["kind"] in ("org", "person"))) for v in G.neighbors(u) if G.nodes[v]["kind"] in ("person", "org")))
    chain_share = chain_members / n_prov
    chain_or_pe = chain_share >= 0.5          # a community is a chain when most of its members are chain-owned; one chain-owned member among many is not
    hub_owner = False
    # labels
    prov_labels = defaultdict(list)
    for n in P:
        for lab in G.nodes[n]["labels"]: prov_labels[lab].append(G.nodes[n]["npi"])
    owner_hits = []
    for n in owners:
        for src, tier, det in (person_lab.get(n[1], []) if n[0] == "person" else org_lab.get(n[1], [])): owner_hits.append((G.nodes[n]["label"], src, tier, str(det[1]) if det and len(det) > 1 else None))
    excluded_link = float(len(prov_labels.get("OIG_LEIE", [])) + len(prov_labels.get("SAM", [])) + sum(1.0 if h[2] == "high" else 0.5 for h in owner_hits if h[1] in ("OIG_LEIE", "SAM")) + sum(h[3] for h in excl_addr_hits))
    state_excl = sum(len(v) for k, v in prov_labels.items() if k.startswith("STATE_EXCL"))
    revoked_nbr = len(prov_labels.get("MEDICARE_REVOKED", [])) + sum(0.5 for h in owner_hits if h[1] == "MEDICARE_REVOKED")
    medicaid_term_nbr = len(prov_labels.get("MEDICAID_TERM", [])); deact_nbr = len(prov_labels.get("NPI_DEACTIVATED", []))
    # market context (dominant type, dominant county)
    dom_type = max(types, key=types.get); svc = SVC[dom_type]
    sat_v, mor = sat_lookup.get((svc, county), (None, None)) if county else (None, None)
    sat_z = ((np.log1p(sat_v) - sat_stats[svc][0]) / sat_stats[svc][1] * 0.6745) if (sat_v is not None and svc in sat_stats) else None
    moratorium = int(bool(mor)) if mor is not None else 0
    npis = [d["npi"] for d in pd_]
    dollars_medicaid_2024 = float(sum(med24.get(n, 0) or 0 for n in npis)); dollars_medicaid_all = float(sum(medall.get(n, 0) or 0 for n in npis))
    ccns = [d["ccn"] for d in pd_ if d["ccn"]]
    dollars_medicare_2023 = float(sum((pac.get(cc, {}).get("medicare_pay_2023") or 0) for cc in ccns))
    feat_rows.append(dict(cluster_ix=ci, n_prov=n_prov, n_hospice=types.get("HOSPICE", 0), n_hha=types.get("HHA", 0), n_snf=types.get("SNF", 0), state=state, city=city, county_fips=county,
                          multi_state=multi_state, n_dated=n_dated, n_new=n_new, new_ratio=(n_new / n_dated) if n_dated else 0.0, burst_90=b90, burst_180=b180, burst_365=b365,
                          burst_90_span=b90_span, addr_share=addr_share, unit_share=unit_share, n_shared_addr=n_shared_addr, n_shared_unit=n_shared_unit, phone_share=phone_share,
                          ao_share=ao_share, mail_share=mail_share, ein_share=ein_share, n_persons=n_persons, n_orgs=n_orgs, owner_multi=owner_multi, max_owner_degree=max_owner_degree,
                          governance_multi=governance_multi, n_distinct_orgs=n_distinct_orgs, for_profit_ratio=for_profit_ratio, excl_addr_hits=[[a, b[0], b[1], b[2], how] for a, b, how, w in excl_addr_hits],
                          owners_per_provider=(len(owners) / n_prov), excluded_link=excluded_link, state_excl=state_excl, revoked_nbr=revoked_nbr, medicaid_term_nbr=medicaid_term_nbr,
                          deact_nbr=deact_nbr, sat_per_10k=sat_v, sat_z=sat_z, moratorium=moratorium, dollars_medicaid_2024=dollars_medicaid_2024, dollars_medicaid_all=dollars_medicaid_all,
                          dollars_medicare_2023=dollars_medicare_2023, chain_or_pe=int(bool(chain_or_pe)), chain_members=chain_members, chain_share=chain_share, owner_hits=owner_hits, prov_labels={k: v for k, v in prov_labels.items()}))
    for n in P:
        d = G.nodes[n]
        member_rows.append(dict(cluster_ix=ci, enrollment_id=n[1], npi=d["npi"], ccn=d["ccn"], ptype=d["ptype"], org_name=d["label"], dba=d["dba"], city=d["city"], state=d["state"], zip5=d["zip5"],
                                county_fips=d["county_fips"], inc_date=d["inc_date"], labels=d["labels"], medicaid_2024=float(med24.get(d["npi"], 0) or 0),
                                medicare_2023=float(pac.get(d["ccn"], {}).get("medicare_pay_2023") or 0) if d["ccn"] else 0.0))
    # graph payload for the UI (community nodes plus their hub neighbours, without hub-to-hub fan-out)
    nodes = []; edges = []; seen = set()
    for n in c:
        d = G.nodes[n]; seen.add(n)
        nodes.append(dict(id=f"{n[0]}:{n[1]}", kind=d["kind"], label=d.get("label", ""), npi=d.get("npi"), ptype=d.get("ptype"), city=d.get("city"), state=d.get("state"),
                          inc_date=d.get("inc_date"), labels=d.get("labels", []), owner_labels=[h for h in (person_lab.get(n[1], []) if n[0] == "person" else org_lab.get(n[1], []))] and
                          [[h[0], h[1]] for h in (person_lab.get(n[1], []) if n[0] == "person" else org_lab.get(n[1], []))], hub=False, prov_degree=d.get("prov_degree")))
    for n in c:
        for v in G.neighbors(n):
            if v in c and (n < v):
                e = G[n][v]; edges.append(dict(source=f"{n[0]}:{n[1]}", target=f"{v[0]}:{v[1]}", rel=e.get("rel"), weight=round(float(e.get("weight", 1)), 3), pct=e.get("pct"), assoc=e.get("assoc")))
            elif v in hubs and v not in seen and G.nodes[n]["kind"] == "provider":
                seen.add(v); d = G.nodes[v]
                nodes.append(dict(id=f"{v[0]}:{v[1]}", kind=d["kind"], label=d.get("label", ""), hub=True, prov_degree=d.get("prov_degree")))
                edges.append(dict(source=f"{n[0]}:{n[1]}", target=f"{v[0]}:{v[1]}", rel=G[n][v].get("rel"), weight=0.0))
            elif v in hubs and G.nodes[n]["kind"] == "provider":
                edges.append(dict(source=f"{n[0]}:{n[1]}", target=f"{v[0]}:{v[1]}", rel=G[n][v].get("rel"), weight=0.0))
    graphs[ci] = dict(nodes=nodes, edges=edges)
F = pd.DataFrame(feat_rows); Mm = pd.DataFrame(member_rows)
log(f"features for {len(F):,} communities")

# ------------------------------------------------------------------ G. scoring, evaluation
def rz(x):
    x = pd.to_numeric(x, errors="coerce"); med = x.median(); mad = (x - med).abs().median()
    if not mad or np.isnan(mad): mad = x.std() or 1.0; z = (x - med) / mad
    else: z = 0.6745 * (x - med) / mad
    return z.clip(lower=-5, upper=5).fillna(0)
F["z_burst"] = rz(F.burst_90.where(F.burst_90 >= 3, 0) / F.n_distinct_orgs.clip(lower=2)); F["z_addr"] = rz(F[["addr_share", "unit_share"]].max(axis=1) / F.n_prov.clip(lower=2)); F["z_owner"] = rz(F.owner_multi / F.n_distinct_orgs.clip(lower=2))
F["z_new"] = rz(F.new_ratio); F["z_phone"] = rz(F[["phone_share", "ao_share", "mail_share"]].max(axis=1) / F.n_prov.clip(lower=2)); F["z_term"] = rz(F.medicaid_term_nbr / F.n_prov.clip(lower=2)); F["z_profit"] = rz(F.for_profit_ratio)
F["sat_z"] = pd.to_numeric(F.sat_z, errors="coerce"); F["sat_per_10k"] = pd.to_numeric(F.sat_per_10k, errors="coerce")
F["z_sat"] = F.sat_z.fillna(0).clip(-5, 5); F["z_size"] = rz(np.log1p(F.n_prov))
F["structure_score"] = 1.5 * F.z_burst + 1.5 * F.z_addr + 1.0 * F.z_owner + 1.5 * F.z_new + 0.5 * F.z_phone + 0.5 * F.z_size   # for-profit share is recorded but not scored: nearly every hospice and HHA in the markets that matter is for-profit
F["context_score"] = 0.8 * F.z_sat + 0.5 * F.moratorium
F["label_score"] = 2.0 * F.excluded_link.clip(upper=3) + 1.0 * F.z_term + 1.0 * F.revoked_nbr.clip(upper=3) + 0.5 * F.state_excl.clip(upper=3) + 0.3 * F.deact_nbr.clip(upper=3)
F["risk_score"] = F.structure_score + F.context_score + F.label_score
F["structure_family"] = ((F.burst_90 >= 3) | (F[["addr_share", "unit_share"]].max(axis=1) >= 3) | (F.owner_multi >= 1) | (F.phone_share >= 3) | (F.new_ratio >= 0.5)).astype(int)
F["label_family"] = ((F.excluded_link > 0) | (F.revoked_nbr >= 1) | (F.medicaid_term_nbr >= 1) | (F.state_excl >= 1)).astype(int)
F["context_family"] = ((F.sat_z.fillna(0) >= 2) | (F.moratorium == 1)).astype(int)
F["families"] = F.structure_family + F.label_family + F.context_family
F["eligible"] = (F.chain_or_pe == 0) & (F.n_distinct_orgs >= 3) & (F.families >= 2) & (F.n_new >= 1)
F = F.sort_values(["eligible", "risk_score"], ascending=[False, False]).reset_index(drop=True); F["rank"] = np.arange(1, len(F) + 1)
# evaluation: structure-only score vs held-out labels (any member revoked by Medicare or excluded by OIG in 2023-2024)
label23 = set(); 
for npi, d in rev_dates.items():
    if d and d >= pd.Timestamp("2023-01-01").date(): label23.add(npi)
for npi, d in leie_dates.items():
    if d and d >= pd.Timestamp("2023-01-01").date(): label23.add(npi)
Mm["label_2324"] = Mm.npi.isin(label23)
haslab = Mm.groupby("cluster_ix").label_2324.any()
F["holdout_label"] = F.cluster_ix.map(haslab).fillna(False).astype(int)
F["any_label"] = (F.label_family == 1).astype(int)
ev = F[(F.chain_or_pe == 0) & (F.n_distinct_orgs >= 3)].sort_values("structure_score", ascending=False)
base = float(ev.any_label.mean()); base_holdout = float(ev.holdout_label.mean())
prec = {k: float(ev.head(k).any_label.mean()) for k in (10, 25, 50, 100, 250)}
from math import comb
def binom_tail(n, k, p):  # P(X >= k) for X ~ Binomial(n, p)
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))
pvals = {k: binom_tail(min(k, len(ev)), int(round(prec[k] * min(k, len(ev)))), base) for k in prec}
log(f"evaluation: base rate {base:.3f}; precision@K (structure-only score, chains excluded): {prec}")
# explanations
def explain(r):
    parts = [f"{int(r.n_prov)} {'providers' if r.n_prov != 1 else 'provider'} ({', '.join(f'{v} {k}' for k, v in {'hospices': r.n_hospice, 'home health agencies': r.n_hha, 'SNFs': r.n_snf}.items() if v)}) around {r.city}"]
    if r.owner_multi: parts.append(f"{int(r.owner_multi)} owner{'s' if r.owner_multi > 1 else ''} tied to 3 or more of them (max {int(r.max_owner_degree)})")
    if max(r.addr_share, r.unit_share) >= 2: parts.append(f"up to {int(max(r.addr_share, r.unit_share))} providers at one address{' (same suite)' if r.unit_share >= 2 else ''}")
    if r.phone_share >= 2: parts.append(f"{int(r.phone_share)} share a phone number")
    if r.burst_90 >= 3 and r.burst_90_span: parts.append(f"{int(r.burst_90)} distinct organisations incorporated within 90 days ({r.burst_90_span[0]} to {r.burst_90_span[1]})")
    if r.excl_addr_hits:
        h = sorted(r.excl_addr_hits, key=lambda x: x[4] != "same suite")[0]; parts.append(f"{h[0]} is in the {h[4]} as {h[1]} entity {h[2]} ({h[3]}); {len(r.excl_addr_hits)} member(s) share an address with an excluded or revoked entity")
    if r.n_new: parts.append(f"{int(r.n_new)} formed since 2021")
    labs = []
    if r.prov_labels.get("OIG_LEIE"): labs.append(f"{len(r.prov_labels['OIG_LEIE'])} member NPI(s) on the OIG exclusion list")
    if r.prov_labels.get("MEDICARE_REVOKED"): labs.append(f"{len(r.prov_labels['MEDICARE_REVOKED'])} revoked by Medicare")
    if r.prov_labels.get("MEDICAID_TERM"): labs.append(f"{len(r.prov_labels['MEDICAID_TERM'])} terminated for cause by a state Medicaid program")
    if r.state_excl: labs.append(f"{int(r.state_excl)} on a state exclusion list")
    oh = [h for h in r.owner_hits if h[1] in ("OIG_LEIE", "SAM")]
    if oh: labs.append(f"owner name match to {oh[0][1]} ({oh[0][2]} confidence): {oh[0][0]}")
    if labs: parts.append("; ".join(labs))
    if r.sat_per_10k is not None and not (isinstance(r.sat_per_10k, float) and np.isnan(r.sat_per_10k)) and r.sat_z is not None and not (isinstance(r.sat_z, float) and np.isnan(r.sat_z)): parts.append(f"county has {r.sat_per_10k:.1f} providers per 10k FFS beneficiaries (robust z {r.sat_z:+.1f})")
    if r.chain_or_pe: parts.append(f"{int(r.chain_members)} of {int(r.n_prov)} members are chain or private-equity owned (excluded from ranking)")
    elif r.chain_members: parts.append(f"{int(r.chain_members)} member(s) have a chain-affiliated owner")
    return ". ".join(parts) + "."
F["summary"] = [explain(r) for r in F.itertuples(index=False)]

# ------------------------------------------------------------------ H. write out
F["cluster_id"] = ["D1-" + f"{i:05d}" for i in F["rank"]]
ix2id = dict(zip(F.cluster_ix, F.cluster_id)); Mm["cluster_id"] = Mm.cluster_ix.map(ix2id)
def _clean(o):
    if isinstance(o, dict): return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list): return [_clean(v) for v in o]
    if isinstance(o, float) and np.isnan(o): return None
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    return o
F["graph_json"] = [json.dumps(_clean(graphs[i]), allow_nan=False) for i in F.cluster_ix]
def _py(v):
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return None if np.isnan(v) else float(v)
    if isinstance(v, (np.bool_,)): return bool(v)
    if isinstance(v, float) and np.isnan(v): return None
    if isinstance(v, tuple): return [str(x) for x in v]
    return v
F["features_json"] = [json.dumps({k: _py(v) for k, v in r.items() if k not in ("graph_json", "owner_hits", "prov_labels", "burst_90_span", "summary", "excl_addr_hits")} | {"owner_hits": r["owner_hits"], "prov_labels": r["prov_labels"], "burst_90_span": [str(x) for x in r["burst_90_span"]] if r["burst_90_span"] else None, "excl_addr_hits": r["excl_addr_hits"]}, default=str) for r in F.to_dict("records")]
out = F.drop(columns=["owner_hits", "prov_labels", "burst_90_span", "excl_addr_hits"]).copy()
out["sat_per_10k"] = pd.to_numeric(out.sat_per_10k, errors="coerce"); out["sat_z"] = pd.to_numeric(out.sat_z, errors="coerce")
con.execute("CREATE OR REPLACE TABLE clusters AS SELECT * FROM out")
Mm["labels"] = [json.dumps(x) for x in Mm.labels]
con.execute("CREATE OR REPLACE TABLE cluster_members AS SELECT * FROM Mm")
con.execute("CREATE OR REPLACE TABLE d1_persons AS SELECT * FROM per"); con.execute("CREATE OR REPLACE TABLE d1_orgs AS SELECT * FROM org")
con.execute("CREATE OR REPLACE TABLE d1_providers AS SELECT * FROM prov")
json.dump(dict(fs=fs_stats, precision=prec, precision_pvalues=pvals, base_rate=base, base_rate_holdout=base_holdout, excluded_addresses=len(excl_addr), n_comms=len(F), hubs=len(hubs), nodes=G.number_of_nodes(), edges=G.number_of_edges()), open("demo/cache/d1_summary.json", "w"), indent=1, default=str)
top = con.execute("""SELECT cluster_id, n_prov, n_hospice, n_hha, n_snf, city, ROUND(risk_score,2) score, burst_90, GREATEST(addr_share, unit_share) addr, owner_multi, phone_share, ROUND(excluded_link,1) excl, revoked_nbr, medicaid_term_nbr, ROUND(sat_z,1) sat_z, ROUND(dollars_medicaid_2024/1e6,2) medicaid_2024_m, ROUND(dollars_medicare_2023/1e6,2) medicare_2023_m
                     FROM clusters WHERE eligible ORDER BY rank LIMIT 25""").fetchall()
print("\n== top 25 eligible communities"); [print("  ", r) for r in top]
print("\n== summaries of top 5"); [print("  ", r[0], "|", r[1][:400]) for r in con.execute("SELECT cluster_id, summary FROM clusters WHERE eligible ORDER BY rank LIMIT 5").fetchall()]
n_elig = con.execute("SELECT COUNT(*) FROM clusters WHERE eligible").fetchone()[0]; n_chain = con.execute("SELECT COUNT(*) FROM clusters WHERE chain_or_pe = 1").fetchone()[0]
by_state = con.execute("SELECT state, COUNT(*), SUM(n_prov), ROUND(SUM(dollars_medicaid_2024)/1e6,1) FROM clusters WHERE eligible AND rank <= 200 GROUP BY 1 ORDER BY 2 DESC LIMIT 10").fetchall()
body = f"""
**Graph.** {len(prov):,} enrollments ({', '.join(f'{v:,} {k}' for k, v in prov.ptype.value_counts().items())}) and {len(own):,} owner or managing-employee rows. Nodes: providers, resolved owner persons ({per.person_id.nunique():,}) and organisations ({org.org_id.nunique():,}), building and suite-level addresses, NPPES phones, faxes, authorised officials, EINs, mailing addresses, secondary practice locations; CHOW buyer to seller edges. {G.number_of_nodes():,} nodes and {G.number_of_edges():,} edges. {len(hubs):,} hub nodes (chains with 25+ facilities, buildings with 25+ tenants, phone numbers on 25+ records, and similar) are held out of component formation so national operators do not swallow the graph; shared buildings, mailing addresses and phones are down-weighted by 1/log2(1 + tenants).

**Identity resolution.** Owner persons are merged on the PECOS associate ID and on an exact key (last name, first three letters, ZIP5), then a Fellegi-Sunter model over six comparison fields (last name with Jaro-Winkler levels, first name with nickname and initial levels, middle initial, ZIP5/ZIP3, city, street number) is fitted by EM on {fs_stats.get('pairs', 0):,} blocked candidate pairs (same state and last name, or same state, Soundex and first initial). Pairs are linked when the posterior match probability is at least 0.95 and at least one locational field agrees, so names alone never merge two people. EM fitted lambda = {fs_stats.get('lam', 0)}, {fs_stats.get('matched', 0):,} pairs linked. Organisations merge on associate ID, on a normalised name (corporate suffixes stripped) plus state, and on token-set similarity of at least 94 within a state.

**Communities.** Connected components of the hub-free graph, with Leiden (RB configuration, resolution 1.0) applied to components above 120 providers: {len(F):,} communities with two or more providers.

**Features per community.** n_prov by type and distinct organisations; incorporation bursts over distinct organisations formed 2019 or later (most organisations incorporated inside any 90, 180 or 365 day window; NPPES enumeration date when the incorporation date is missing); for-profit share; share of members formed since 2021; largest number of members at one building and at one suite; phone, fax, authorised-official, mailing-address and EIN sharing; owners tied to three or more members; label links (member NPIs on LEIE, SAM, Medicare revocations, state exclusion lists, Medicaid for-cause terminations, NPI deactivations; owner-name links to LEIE and SAM at high (name + ZIP5) or medium (name + state) confidence); CMS Market Saturation providers per 10k FFS beneficiaries for the dominant county and service, as a robust z on the log scale across all counties; county moratorium flag; Medicaid 2024 and all-years dollars (billing NPI) and Medicare 2023 hospice/HHA payments (PAC PUF).

**Score.** Each feature is converted to a robust z (median/MAD, capped at 5): structure = 1.5 z(burst_90 over distinct organisations, bursts of three or more only) + 1.5 z(address share/n) + 1.0 z(owner_multi/n) + 1.5 z(new ratio) + 0.5 z(phone or official share/n) + 0.5 z(log size); the for-profit share is recorded as a feature but not scored, because nearly every hospice and home health agency in Los Angeles, Houston, Phoenix and Las Vegas is for-profit; context = 0.8 z(saturation) + 0.5 moratorium; labels = 2.0 excluded links (member NPI on LEIE or SAM, owner name on LEIE or SAM at high 1.0 or medium 0.5 confidence, same suite as an excluded or revoked entity 1.0, same building 0.5; cap 3) + 1.0 z(Medicaid for-cause terminations/n, bulk-coded states suppressed) + 1.0 revoked (cap 3) + 0.5 state exclusions (cap 3) + 0.3 deactivations (cap 3). Owner counts use ownership and managing-control roles only (5 percent direct or indirect owners, managing employees, operational control, administrators); boards, officers and trustees are recorded but not scored, so hospital systems with a shared board do not look like networks. Ranked list eligibility: no chain or private-equity owner ({n_chain:,} communities are scored but held out: consolidation is not a ghost network), at least three distinct organisations, at least one organisation formed since 2021, and at least two independent evidence families (structure, label, context). Every ranked community is a referral candidate for records review, not a finding. {n_elig:,} communities are eligible.

**Evaluation.** The CMS enrollment files only contain providers that are still enrolled, so Medicare revocations cannot be held out as labels (only {base_holdout:.4f} of communities contain a member revoked or excluded in 2023 or 2024: the revoked ones have already left the file). The structure-only score, which uses no label information, is instead evaluated against any label link (member NPI on LEIE, SAM, the revoked list, a state exclusion list or a for-cause Medicaid termination; owner name on LEIE or SAM; address shared with an excluded or revoked entity). Base rate {base:.3f}; precision at K of the structure-only score among communities of three or more distinct organisations, chains excluded: {', '.join(f'P@{k} = {v:.2f} (one-sided binomial p = {pvals[k]:.3f})' for k, v in prec.items())}. Read this honestly: the top-10 figure is ten items and is not statistically meaningful on its own; the label set is incomplete (it cannot contain providers that have already left the enrollment file) and it overlaps the inputs of the full risk score, so only the structure-only score is evaluated against it. {len(excl_addr):,} addresses of LEIE-excluded entities and revoked organisations were indexed for the address test.

{md_table(by_state, ["state","communities in top 200","providers","Medicaid 2024 $M"])}

**Top 25.**

{md_table(top, ["cluster","n","hospice","HHA","SNF","city","score","burst90","addr","owner_multi","phone","excl","revoked","Medicaid term","sat z","Medicaid 2024 $M","Medicare 2023 $M"])}

Tables: `clusters` (features, score, rank, summary, graph JSON), `cluster_members`, `d1_persons`, `d1_orgs`, `d1_providers`. Code: `detectors/d1_ghost_networks.py`.
"""
write_section("Detector 1: ghost networks", body)
con.execute("CHECKPOINT"); con.close(); log("done")
