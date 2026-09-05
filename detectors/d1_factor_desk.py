"""Factor desk for provider networks: thirty measurable factors per network, each with a value, a percentile among all networks
and a robust z-score, grouped into families (formation timing, ownership, addresses and contacts, list exposure, market, money,
identity and enrollment, momentum). The momentum family combines the rate-of-change factors into an indicative outlook. Nothing here
is a validated forecast; the desk shows what is moving and by how much, with every number traceable to a public table.
Writes d1_factors (long format) and a Methods section."""
from __future__ import annotations
import json, os, sys, time
import duckdb, numpy as np, pandas as pd
DB = os.environ.get("VERITY_DUCKDB", "data/verity.duckdb")
con = duckdb.connect(DB)
t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.0f}s] {m}", flush=True)

cl = con.execute("SELECT cluster_id, rank, eligible, n_prov, n_hospice, n_hha, n_snf, state, county_fips, features_json, dollars_medicaid_2024, dollars_medicare_2023, chain_or_pe FROM clusters WHERE n_prov >= 3").df()
cl["f"] = [json.loads(x) if isinstance(x, str) else (x or {}) for x in cl.features_json]
mem = con.execute("SELECT cluster_id, enrollment_id, npi, ptype, inc_date, labels, medicaid_2024, medicare_2023, zip5 FROM cluster_members").df()
mem = mem[mem.cluster_id.isin(cl.cluster_id)]
mem["inc"] = pd.to_datetime(mem.inc_date, errors="coerce")
log(f"networks {len(cl):,}, members {len(mem):,}")

# Medicaid dollars by member and year (T-MSIS), for growth and concentration
con.execute("CREATE OR REPLACE TEMP TABLE fm AS SELECT DISTINCT npi FROM cluster_members WHERE npi IS NOT NULL")
sp = con.execute("""SELECT s.npi, substr(s.month, 1, 4) AS yr, SUM(s.paid) AS paid FROM spend_any_month s JOIN fm USING (npi) WHERE s.month >= '2020-01' GROUP BY 1, 2""").df()
sp = sp.pivot_table(index="npi", columns="yr", values="paid", aggfunc="sum").fillna(0.0)
for y in ("2020", "2021", "2022", "2023", "2024"):
    if y not in sp.columns: sp[y] = 0.0
mem = mem.merge(sp, left_on="npi", right_index=True, how="left").fillna({y: 0.0 for y in ("2020", "2021", "2022", "2023", "2024")})

# owners of member enrollments (ownership and managing roles), association dates
own = con.execute("""SELECT "ENROLLMENT ID" AS enrollment_id, "ASSOCIATE ID - OWNER" AS owner_id, "ROLE CODE - OWNER" AS role, "TYPE - OWNER" AS otype,
                            TRY_CAST(strptime("ASSOCIATION DATE - OWNER", '%m/%d/%Y') AS DATE) AS assoc_dt
                     FROM owners WHERE "ENROLLMENT ID" IN (SELECT enrollment_id FROM cluster_members)""").df()
own["is_owner"] = own.role.isin(["34", "35", "85", "86", "36", "37", "38"]); own["is_mgr"] = own.role.isin(["42", "25", "43", "72"])
own = own.merge(mem[["enrollment_id", "cluster_id"]].drop_duplicates(), on="enrollment_id", how="inner")

# changes of ownership among members (buyer or seller enrollment id)
try:
    ch = con.execute("""SELECT "ENROLLMENT ID - BUYER" AS b, "ENROLLMENT ID - SELLER" AS s, TRY_CAST(strptime("EFFECTIVE DATE", '%m/%d/%Y') AS DATE) AS dt FROM chow""").df()
    eids = set(mem.enrollment_id); ch = ch[ch.b.isin(eids) | ch.s.isin(eids)]
    chow_by_cluster = pd.concat([ch[["b"]].rename(columns={"b": "enrollment_id"}), ch[["s"]].rename(columns={"s": "enrollment_id"})]).merge(mem[["enrollment_id", "cluster_id"]].drop_duplicates(), on="enrollment_id").groupby("cluster_id").size()
except Exception as e:
    log(f"chow unavailable: {str(e)[:60]}"); chow_by_cluster = pd.Series(dtype=float)

# NPPES enumeration and deactivation dates
npp = con.execute("SELECT n.npi, n.enum_date, n.deact_date FROM nppes n JOIN fm USING (npi)").df()
npp["enum"] = pd.to_datetime(npp.enum_date, errors="coerce"); npp["deact"] = pd.to_datetime(npp.deact_date, errors="coerce")
mem = mem.merge(npp[["npi", "enum", "deact"]], on="npi", how="left")

# Medicaid enrollment footprint (states per member)
en = con.execute("SELECT e.npi, COUNT(DISTINCT e.state) AS n_states FROM enroll e JOIN fm USING (npi) GROUP BY 1").df()
mem = mem.merge(en, on="npi", how="left").fillna({"n_states": 0})

# plaza exposure: members at an address that hosts eight or more enrollments
hub_npis = set()
for x in con.execute("SELECT npis FROM d1_hub_addresses").fetchall():
    try: hub_npis.update(json.loads(x[0]) if isinstance(x[0], str) else list(x[0]))
    except Exception: pass

# market saturation trend for the county and the network's dominant service type
sat = con.execute("""SELECT state, lpad(CAST(state_fips AS VARCHAR), 2, '0') || lpad(CAST(county_fips AS VARCHAR), 3, '0') AS fips5, type_of_service,
                            TRY_CAST(period_year AS INTEGER) AS period_year, TRY_CAST(providers_per_10k_ffs AS DOUBLE) AS providers_per_10k_ffs, moratorium
                     FROM saturation_county WHERE state_fips IS NOT NULL AND county_fips IS NOT NULL""").df()
sat["type_of_service"] = sat.type_of_service.astype(str).str.lower()
def sat_type(row):
    return "hospice" if row.n_hospice >= max(row.n_hha, row.n_snf) else ("home health" if row.n_hha >= row.n_snf else "skilled nursing")
def sat_trend(fips, kind):
    s = sat[(sat.fips5 == str(fips).zfill(5)) & (sat.type_of_service.str.contains(kind.split()[0]))]
    if s.empty: return (np.nan, np.nan, 0)
    s = s.sort_values("period_year"); last = s.iloc[-1]; first = s[s.period_year <= last.period_year - 3]
    base = first.iloc[-1].providers_per_10k_ffs if len(first) else np.nan
    trend = (last.providers_per_10k_ffs - base) / base if base and base > 0 else np.nan
    return (float(last.providers_per_10k_ffs), float(trend) if trend == trend else np.nan, int(s.moratorium.astype(str).str.upper().isin(["Y", "YES", "1", "TRUE"]).any()))

# ---------------------------------------------------------------- factors per network
F = {  # key: (family, label, unit, direction, note)
    "burst_90": ("formation", "Companies incorporated within one 90-day window", "count", "+", "Bursts of incorporation are how ghost networks are stood up."),
    "new_share": ("formation", "Share of companies formed in 2021 or later", "share", "+", "Recently formed companies have little billing history to check."),
    "velocity": ("formation", "Most companies formed in a single year", "count", "+", "Formation velocity, 2019 to 2025."),
    "median_age": ("formation", "Median company age", "years", "-", "Younger networks have not yet been through a revalidation cycle."),
    "owner_multi": ("ownership", "Owners who sit on three or more providers", "count", "+", "From the CMS All Owners files, ownership and managing roles."),
    "max_owner_degree": ("ownership", "Providers under the most connected owner", "count", "+", ""),
    "owners_per_provider": ("ownership", "Distinct owners per provider", "ratio", "-", "Few distinct owners across many providers means concentrated control."),
    "managing_share": ("ownership", "Share of owner records that are managing employees", "share", "+", "Straw ownership often shows as managing employees rather than owners."),
    "owner_burst": ("ownership", "Owner associations recorded within one 90-day window", "count", "+", ""),
    "chow": ("ownership", "Changes of ownership among members", "count", "+", "Churn in ownership around the same providers."),
    "addr_share": ("addresses", "Most providers at one building", "count", "+", ""),
    "unit_share": ("addresses", "Most providers in one suite", "count", "+", ""),
    "phone_share": ("addresses", "Providers sharing a phone number", "count", "+", ""),
    "ao_share": ("addresses", "Providers sharing an authorized official", "count", "+", ""),
    "excluded_link": ("addresses", "Providers at the address of a revoked or excluded company", "count", "+", "Weighted 1.0 for the same suite, 0.5 for the same building."),
    "plaza_share": ("addresses", "Share of providers at an address hosting eight or more enrollments", "share", "+", "Office plazas that host dozens of enrollments."),
    "list_members": ("lists", "Providers on a revocation, exclusion or termination list", "count", "+", ""),
    "owner_hits": ("lists", "Owners whose name matches an exclusion list", "count", "+", "Name matches at the stated confidence."),
    "sat_per_10k": ("market", "Providers per 10,000 Medicare beneficiaries in the county", "per 10k", "+", "CMS Market Saturation, dominant service type."),
    "sat_trend": ("market", "Change in county saturation over three years", "share", "+", "Rising saturation means new entrants are still arriving."),
    "moratorium": ("market", "County had an enrollment moratorium", "flag", "+", "Counties that were under moratorium have a history of fraud pressure."),
    "medicaid_2024": ("money", "Medicaid paid in 2024", "$", "+", ""),
    "medicare_2023": ("money", "Medicare hospice and home health paid in 2023", "$", "+", ""),
    "medicaid_growth": ("money", "Medicaid growth, 2022 to 2024", "share", "+", "Sum over members; blank when 2022 was zero."),
    "dollar_concentration": ("money", "Share of 2024 Medicaid in the largest member", "share", "-", "Dollars spread across many new companies is the harder pattern to see."),
    "billing_share": ("money", "Share of providers with any Medicaid billing", "share", "-", "Many enrolled companies with no billing yet."),
    "enum_near_inc": ("identity", "Share of providers whose NPI was issued within six months of incorporation", "share", "+", ""),
    "deactivated": ("identity", "Providers whose NPI is deactivated", "count", "+", ""),
    "states": ("identity", "States in which members are enrolled in Medicaid", "count", "+", "Multi-state footprints move faster than state screening does."),
    "chain_share": ("identity", "Share of providers in a known chain", "share", "-", "Chains are held out of the ranking."),
}
rows = []
today = pd.Timestamp("2026-09-05")
for r in cl.itertuples(index=False):
    f = r.f; m = mem[mem.cluster_id == r.cluster_id]; o = own[own.cluster_id == r.cluster_id]
    inc = m.inc.dropna(); yrs = inc.dt.year
    vel = int(yrs[yrs >= 2019].value_counts().max()) if (yrs >= 2019).any() else 0
    age = float(((today - inc).dt.days / 365.25).median()) if len(inc) else np.nan
    n_owner_ids = o.owner_id.nunique(); n_prov = max(int(r.n_prov), 1)
    mshare = float(o.is_mgr.mean()) if len(o) else np.nan
    ad = o.assoc_dt.dropna().sort_values().to_numpy()
    oburst = 0
    if len(ad) >= 2:
        for i in range(len(ad)): oburst = max(oburst, int(((ad >= ad[i]) & (ad <= ad[i] + np.timedelta64(90, "D"))).sum()))
    kind = sat_type(r); sat_now, trend, mora = sat_trend(r.county_fips, kind) if r.county_fips else (np.nan, np.nan, 0)
    p22, p24 = float(m["2022"].sum()), float(m["2024"].sum())
    growth = (p24 - p22) / p22 if p22 > 0 else np.nan
    conc = float(m["2024"].max() / p24) if p24 > 0 else np.nan
    bill = float((m["2024"] > 0).mean()) if len(m) else np.nan
    near = m.dropna(subset=["inc", "enum"]); enum_near = float((abs((near.enum - near.inc).dt.days) <= 183).mean()) if len(near) else np.nan
    vals = {
        "burst_90": f.get("burst_90", 0), "new_share": (f.get("n_new", 0) / max(f.get("n_distinct_orgs", n_prov), 1)), "velocity": vel, "median_age": age,
        "owner_multi": f.get("owner_multi", 0), "max_owner_degree": f.get("max_owner_degree", 0), "owners_per_provider": n_owner_ids / n_prov if n_owner_ids else np.nan,
        "managing_share": mshare, "owner_burst": oburst, "chow": float(chow_by_cluster.get(r.cluster_id, 0)),
        "addr_share": f.get("addr_share", 0), "unit_share": f.get("unit_share", 0), "phone_share": f.get("phone_share", 0), "ao_share": f.get("ao_share", 0),
        "excluded_link": f.get("excluded_link", 0), "plaza_share": float(m.npi.isin(hub_npis).mean()) if len(m) else 0.0,
        "list_members": float(f.get("revoked_nbr", 0) + f.get("medicaid_term_nbr", 0) + f.get("state_excl", 0)), "owner_hits": float(len(f.get("owner_hits", []) or [])),
        "sat_per_10k": f.get("sat_per_10k", sat_now), "sat_trend": trend, "moratorium": mora,
        "medicaid_2024": float(r.dollars_medicaid_2024 or 0), "medicare_2023": float(r.dollars_medicare_2023 or 0), "medicaid_growth": growth, "dollar_concentration": conc, "billing_share": bill,
        "enum_near_inc": enum_near, "deactivated": float(m.deact.notna().sum()), "states": float(m.n_states.max()) if len(m) else 0, "chain_share": f.get("chain_share", 0),
    }
    for k, v in vals.items():
        fam, label, unit, direction, note = F[k]
        rows.append(dict(cluster_id=r.cluster_id, factor=k, family=fam, label=label, unit=unit, direction=direction, note=note, value=(None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v))))
D = pd.DataFrame(rows)
log(f"factor rows {len(D):,}")

# percentiles and robust z within the population of networks with three or more providers, direction-aware (100 = most unusual in the risky direction)
def pct_and_z(g):
    v = g.value.astype(float); ok = v.notna()
    pct = pd.Series(np.nan, index=g.index); z = pd.Series(np.nan, index=g.index)
    if ok.sum() >= 5:
        rank = v[ok].rank(pct=True, method="average")
        med = v[ok].median(); mad = (v[ok] - med).abs().median()
        zz = (v[ok] - med) / (1.4826 * mad) if mad > 0 else (v[ok] - med) * 0
        if g.direction.iloc[0] == "-": rank = 1 - rank + 1 / ok.sum(); zz = -zz
        pct[ok] = (100 * rank).round(1); z[ok] = zz.round(2)
    g = g.copy(); g["percentile"] = pct; g["z"] = z; return g
D = D.groupby("factor", group_keys=False).apply(pct_and_z)

# momentum: rate-of-change factors combined into one indicative outlook per network
MOM = ["velocity", "new_share", "medicaid_growth", "owner_burst", "sat_trend", "chow"]
mom = D[D.factor.isin(MOM)].groupby("cluster_id").z.apply(lambda s: float(np.clip(s.dropna(), -3, 3).mean()) if s.notna().any() else np.nan)
def outlook(z): return "rising fast" if z >= 1.0 else ("rising" if z >= 0.3 else ("steady" if z > -0.3 else "cooling"))
mrows = [dict(cluster_id=c, factor="momentum", family="momentum", label="Momentum across the rate-of-change factors", unit="z", direction="+", note="Mean robust z of formation velocity, new-company share, Medicaid growth, owner association bursts, saturation trend and ownership changes. Indicative, not a validated forecast.", value=(None if z != z else round(z, 2)), percentile=None, z=(None if z != z else round(z, 2))) for c, z in mom.items()]
M = pd.DataFrame(mrows); M["percentile"] = (100 * M.value.rank(pct=True)).round(1)
M["outlook"] = [outlook(z) if z == z else None for z in M.value]
D["outlook"] = None
D = pd.concat([D, M], ignore_index=True)
D["value"] = D.value.astype(float)
con.execute("CREATE OR REPLACE TABLE d1_factors AS SELECT * FROM D")
log(f"d1_factors written: {len(D):,} rows for {D.cluster_id.nunique():,} networks")

# Methods section
sys.path.insert(0, "detectors"); from _methods import write_section, md_table
top = con.execute("""SELECT d.cluster_id, c.rank, ROUND(d.value, 2) AS momentum, d.outlook FROM d1_factors d JOIN clusters c USING (cluster_id) WHERE d.factor = 'momentum' AND c.eligible ORDER BY c.rank LIMIT 10""").fetchall()
dist = con.execute("SELECT outlook, COUNT(*) FROM d1_factors WHERE factor = 'momentum' AND outlook IS NOT NULL GROUP BY 1 ORDER BY 2 DESC").fetchall()
write_section("Network factor desk", f"""
**What it is.** For every provider network with three or more providers, the desk measures {len(F)} factors in seven families: formation timing (incorporation bursts, share of new companies, formation velocity, company age), ownership (owners on several providers, concentration, managing-employee share, association-date bursts, changes of ownership), addresses and contacts (shared buildings, suites, phones, officials, addresses of revoked companies, office plazas), list exposure (members and owners on public lists), market (county saturation, its three-year trend, moratorium history), money (Medicaid 2024, Medicare 2023, Medicaid growth 2022 to 2024, dollar concentration, billing share) and identity and enrollment (NPI issued close to incorporation, deactivated NPIs, multi-state footprint, chain share). Each factor carries its value, its percentile among all such networks in the risky direction, and a robust z-score.

**Momentum.** Six rate-of-change factors (formation velocity, new-company share, Medicaid growth, owner association bursts, saturation trend and ownership changes) are averaged as clipped robust z-scores into one momentum number with an outlook label: rising fast (z at or above 1), rising (0.3 to 1), steady, cooling. This is an indicative reading of what is moving, not a validated forecast; no outcome data exist yet to calibrate it, and it never changes a tier.

Outlook across networks: {', '.join(f"{o} {n:,}" for o, n in dist)}.

{md_table(top, ["network", "rank", "momentum z", "outlook"])}
""")
log("done")
