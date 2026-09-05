#!/usr/bin/env python3
"""Verity fraud risk score v2: a calibrated, out-of-time-validated probability of a future integrity action, and expected loss.

Design (see docs/RISK_SCORE_V2.md):
  1. Cohort and label.  Every NPI with >= $1,000 of Medicaid payments in 2018-2022. Label y = 1 if the NPI received a fraud-authority
     OIG exclusion (1128(a)(1),(a)(2),(a)(3),(b)(7)) or an integrity-ground Medicare revocation (42 CFR 424.535(a)(2),(3),(4),(5),(7),(8),
     (10),(12),(13),(14),(18),(19),(20),(22),(23)) dated 2023-01-01 or later. Features use only 2018-2022 data, so the test is out of time.
  2. Features.  Volume, growth, ramp (max month over trailing 6-month median), concentration, concurrency (billing organisations),
     patients, impossible-hour months and peak implied hours (Detector 2 restricted to <= 2022), prior administrative history, entity type.
  3. Model.  Weight-of-evidence binning per feature (reported with information value), logistic regression on the WOE features
     (additive log-odds, the same structure as Fellegi-Sunter and credit scorecards), isotonic calibration on a held-out 30 percent.
  4. Evaluation.  AUC, average precision, precision@K and lift@K with bootstrap 95 percent intervals (2,000 resamples of the test set).
  5. Application.  The fitted scorecard is applied to 2018-2024 features for every NPI: P_action = calibrated probability of an
     integrity action in the following ~3 years. Detector 2 impossibility gets its own Monte Carlo probability P_impossible using the
     empirical distribution of the unit-price estimator's bias from the Minnesota validation. Documented actions (Detector 3 tier A)
     are not predicted, they are facts, and sit in their own tier.
  6. Expected loss.  EL = P x exposure x LGD, exposure = Medicaid paid in the last 12 observed months, LGD = 0.9 (CMS FPS adjusted
     savings ran near 10 percent of identified, OIG 2019).
Outputs: data/risk_v2.duckdb (tables risk_v2, risk_v2_eval, risk_v2_woe, risk_v2_calibration), demo/cache/risk_v2_summary.json.
"""
import os, sys, json, time, math
import duckdb, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); os.chdir(ROOT)
SRC = os.environ.get("VERITY_DUCKDB", "data/verity.duckdb"); OUT = os.environ.get("RISK_V2_DB", "data/risk_v2.duckdb")
con = duckdb.connect(SRC, read_only=True); os.makedirs("data/tmp_risk_v2", exist_ok=True); os.makedirs("data/cache_risk_v2", exist_ok=True)
con.execute("SET memory_limit='2GB'"); con.execute("SET threads=3"); con.execute(f"SET temp_directory='{os.path.expanduser('~/ddbtmp')}'"); con.execute("SET preserve_insertion_order=false"); con.execute("PRAGMA max_temp_directory_size='8GiB'")
T0 = time.time(); log = lambda *a: print(f"[{time.time()-T0:6.0f}s]", *a, flush=True)
FRAUD_LEIE = "('1128a1','1128a2','1128a3','1128b7')"
INTEGRITY = r"'\(A\)\((2|3|4|5|7|8|10|12|13|14|18|19|20|22|23)\)'"

def features(end_month):
    """Per-NPI behavioural features from spend_any_month up to end_month (inclusive), plus D2 and history features. Cached to parquet."""
    cache = f"data/cache_risk_v2/features_{end_month}.parquet"
    if os.path.exists(cache): return pd.read_parquet(cache)
    df = con.execute(f"""
WITH s AS (SELECT npi, month, month_start, paid, lines, max_patients, n_counterparties FROM spend_any_month WHERE month <= '{end_month}'),
w AS (SELECT *, median(paid) OVER (PARTITION BY npi ORDER BY month_start ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS med6,
             count(*) OVER (PARTITION BY npi ORDER BY month_start ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING) AS n6 FROM s),
agg AS (
  SELECT npi, SUM(paid) AS paid_total, COUNT(*) AS n_months, MAX(paid) AS max_month,
         SUM(CASE WHEN month >= '{end_month[:4]}-01' THEN paid ELSE 0 END) AS paid_last_year,
         SUM(CASE WHEN month BETWEEN '{int(end_month[:4])-1}-01' AND '{int(end_month[:4])-1}-12' THEN paid ELSE 0 END) AS paid_prev_year,
         SUM(CASE WHEN month_start >= DATE '{end_month}-01' - INTERVAL 11 MONTH THEN paid ELSE 0 END) AS paid_12m,
         MAX(CASE WHEN n6 >= 3 AND med6 > 0 THEN paid / med6 END) AS ramp,
         MAX(n_counterparties) AS max_counterparties, MAX(max_patients) AS max_patients, SUM(lines) AS lines_total,
         MAX(month) AS last_month, MIN(month) AS first_month
  FROM w GROUP BY npi),
top3 AS (SELECT npi, SUM(paid) AS top3 FROM (SELECT npi, paid, row_number() OVER (PARTITION BY npi ORDER BY paid DESC) rn FROM s) WHERE rn <= 3 GROUP BY npi),
d2 AS (SELECT servicing_npi AS npi,
          SUM(CASE WHEN test_hours_per_day > 24 THEN 1 ELSE 0 END) AS m_over24, SUM(CASE WHEN test_hours_per_day > 16 THEN 1 ELSE 0 END) AS m_over16,
          MAX(test_hours_per_day) AS peak_test_hpd, MAX(hours_pt_personal_per_day) AS peak_pt_personal_hpd, MAX(hours_lb_personal_per_day) AS peak_lb_personal_hpd,
          MAX(n_billing_orgs) AS max_billing_orgs, SUM(CASE WHEN test_hours_per_day > 24 AND n_billing_orgs >= 3 THEN 1 ELSE 0 END) AS m_over24_concurrent
       FROM d2_scored WHERE month <= '{end_month}' GROUP BY 1),
hist AS (SELECT npi, 1 AS prior_admin FROM (
          SELECT npi FROM revoked WHERE revoked_dt <= DATE '{end_month}-01' AND NOT regexp_matches(revocation_rsn, {INTEGRITY})
          UNION SELECT npi FROM nppes WHERE deact_date IS NOT NULL AND deact_date <= DATE '{end_month}-01'
          UNION SELECT npi FROM optout WHERE optout_start <= DATE '{end_month}-01') GROUP BY 1),
d1 AS (SELECT DISTINCT m.npi, 1 AS d1_eligible FROM cluster_members m JOIN clusters c USING (cluster_ix) WHERE c.eligible AND m.npi IS NOT NULL)
SELECT a.npi, a.paid_total, a.n_months, a.max_month, a.paid_last_year, a.paid_prev_year, a.paid_12m, COALESCE(a.ramp, 1) AS ramp,
       a.max_counterparties, a.max_patients, a.lines_total, a.last_month, a.first_month, t.top3 / NULLIF(a.paid_total, 0) AS top3_share,
       COALESCE(d2.m_over24, 0) AS m_over24, COALESCE(d2.m_over16, 0) AS m_over16, COALESCE(d2.peak_test_hpd, 0) AS peak_test_hpd,
       COALESCE(d2.peak_pt_personal_hpd, 0) AS peak_pt_personal_hpd, COALESCE(d2.peak_lb_personal_hpd, 0) AS peak_lb_personal_hpd,
       COALESCE(d2.max_billing_orgs, 0) AS max_billing_orgs, COALESCE(d2.m_over24_concurrent, 0) AS m_over24_concurrent,
       COALESCE(h.prior_admin, 0) AS prior_admin, COALESCE(d1.d1_eligible, 0) AS d1_eligible,
       n.entity_type, n.state AS nppes_state, n.taxonomy, COALESCE(n.org_name, trim(COALESCE(n.first_name,'')||' '||COALESCE(n.last_name,''))) AS name, n.city
FROM agg a LEFT JOIN top3 t USING (npi) LEFT JOIN d2 USING (npi) LEFT JOIN hist h USING (npi) LEFT JOIN d1 USING (npi) LEFT JOIN nppes n USING (npi)
WHERE a.paid_total >= 1000""").df()
    df.to_parquet(cache); return df

log("building training features (2018-2022)")
tr = features("2022-12")
lab = con.execute(f"""SELECT npi, 1 AS y FROM (SELECT npi FROM leie WHERE npi IS NOT NULL AND excl_dt >= '2023-01-01' AND excltype IN {FRAUD_LEIE}
                       UNION SELECT npi FROM revoked WHERE revoked_dt >= '2023-01-01' AND regexp_matches(revocation_rsn, {INTEGRITY})) GROUP BY 1""").df()
tr = tr.merge(lab, on="npi", how="left"); tr["y"] = tr["y"].fillna(0).astype(int)
log(f"cohort {len(tr):,} NPIs, positives {int(tr.y.sum()):,} (base rate {tr.y.mean():.5f})")

# ---------- feature engineering ----------
def engineer(df):
    X = pd.DataFrame(index=df.index)
    X["log_paid"] = np.log10(df.paid_total.clip(lower=1))
    X["log_paid_ly"] = np.log10(df.paid_last_year.clip(lower=1))
    X["growth"] = np.log((df.paid_last_year + 1) / (df.paid_prev_year + 1)).clip(-6, 6)
    X["log_ramp"] = np.log(df.ramp.clip(lower=1)).clip(0, 6)
    X["top3_share"] = df.top3_share.fillna(1).clip(0, 1)
    X["n_months"] = df.n_months
    X["log_counterparties"] = np.log1p(df.max_counterparties.fillna(0))
    X["log_patients"] = np.log1p(df.max_patients.fillna(0).astype(float))
    X["paid_per_patient"] = np.log10((df.max_month / df.max_patients.replace(0, np.nan)).fillna(0).clip(lower=0) + 1)
    X["m_over24"] = df.m_over24.clip(0, 24); X["m_over16"] = df.m_over16.clip(0, 36)
    X["peak_pt_personal_hpd"] = df.peak_pt_personal_hpd.clip(0, 200)
    X["m_over24_concurrent"] = df.m_over24_concurrent.clip(0, 24)
    X["max_billing_orgs"] = df.max_billing_orgs.clip(0, 50)
    X["prior_admin"] = df.prior_admin; X["individual"] = (df.entity_type == "1").astype(int)
    X["d1_eligible"] = df.d1_eligible
    return X
Xtr = engineer(tr); y = tr.y.values
FEATS = [c for c in Xtr.columns if c != "d1_eligible"]   # D1 membership is a 2026 snapshot: reported, not used in the out-of-time model

# ---------- weight of evidence with information value ----------
def woe_table(x, y, bins=10, name=""):
    x = pd.Series(x); q = np.unique(np.quantile(x, np.linspace(0, 1, bins + 1)))
    if len(q) < 3: q = np.unique(np.concatenate([[x.min() - 1e-9], np.unique(x)[:-1] + 1e-9, [x.max() + 1e-9]]))
    b = pd.cut(x, q, include_lowest=True, duplicates="drop")
    g = pd.DataFrame({"b": b, "y": y}).groupby("b", observed=True)["y"].agg(["sum", "count"])
    g["non"] = g["count"] - g["sum"]; e = (g["sum"] + 0.5) / (y.sum() + 0.5 * len(g)); ne = (g["non"] + 0.5) / ((1 - y).sum() + 0.5 * len(g))
    g["woe"] = np.log(e / ne); g["iv"] = (e - ne) * g["woe"]; g["feature"] = name; g["rate"] = g["sum"] / g["count"]
    return g.reset_index().rename(columns={"b": "bin", "sum": "positives", "count": "n"}), float(g["iv"].sum()), q
woe_rows, IV, edges = [], {}, {}
for f in FEATS:
    t, iv, q = woe_table(Xtr[f].values, y, name=f); woe_rows.append(t); IV[f] = iv; edges[f] = q
woe_df = pd.concat(woe_rows); woe_df["bin"] = woe_df["bin"].astype(str)
log("information value:", {k: round(v, 3) for k, v in sorted(IV.items(), key=lambda kv: -kv[1])})
def apply_woe(X):
    Z = pd.DataFrame(index=X.index)
    for f in FEATS:
        t = woe_df[woe_df.feature == f]; q = edges[f]
        b = pd.cut(X[f].clip(q[0], q[-1]), q, include_lowest=True, duplicates="drop").astype(str)
        m = dict(zip(t["bin"], t["woe"])); Z[f] = b.map(m).fillna(0.0).values
    return Z

# ---------- model, held-out evaluation, calibration ----------
from sklearn.linear_model import LogisticRegression
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, average_precision_score
from sklearn.model_selection import train_test_split
Z = apply_woe(Xtr)
itr, ite = train_test_split(np.arange(len(Z)), test_size=0.3, random_state=7, stratify=y)
lr = LogisticRegression(C=0.5, max_iter=2000); lr.fit(Z.iloc[itr], y[itr])
raw_te = lr.predict_proba(Z.iloc[ite])[:, 1]
iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0); iso.fit(raw_te, y[ite])   # calibrate on held-out (reported as in-sample for the calibration step)
p_te = iso.predict(raw_te); yte = y[ite]
def prec_at_k(p, yv, k): idx = np.argsort(-p)[:k]; return yv[idx].mean()
rng = np.random.default_rng(11); B = 2000; ks = [50, 100, 250, 500, 1000, 2500]
boots = {k: [] for k in ks}; aucs, aps = [], []
for _ in range(B):
    s = rng.integers(0, len(p_te), len(p_te)); ps, ys = p_te[s], yte[s]
    if ys.sum() == 0: continue
    aucs.append(roc_auc_score(ys, ps)); aps.append(average_precision_score(ys, ps))
    for k in ks: boots[k].append(prec_at_k(ps, ys, k))
base = yte.mean()
ev = dict(n_test=int(len(yte)), positives_test=int(yte.sum()), base_rate=float(base),
          auc=float(roc_auc_score(yte, p_te)), auc_ci=[float(np.percentile(aucs, 2.5)), float(np.percentile(aucs, 97.5))],
          ap=float(average_precision_score(yte, p_te)), ap_ci=[float(np.percentile(aps, 2.5)), float(np.percentile(aps, 97.5))],
          precision_at_k={str(k): dict(point=float(prec_at_k(p_te, yte, k)), ci=[float(np.percentile(boots[k], 2.5)), float(np.percentile(boots[k], 97.5))],
                                       lift=float(prec_at_k(p_te, yte, k) / base)) for k in ks},
          coefficients={f: float(c) for f, c in zip(FEATS, lr.coef_[0])}, intercept=float(lr.intercept_[0]), iv=IV)
log("eval:", json.dumps({k: v for k, v in ev.items() if k in ("auc", "auc_ci", "ap", "base_rate")}), "P@K:", {k: round(v["point"], 3) for k, v in ev["precision_at_k"].items()})
# calibration table (deciles of predicted p on the test set)
cal = pd.DataFrame({"p": p_te, "y": yte}); cal["decile"] = pd.qcut(cal.p.rank(method="first"), 10, labels=False) + 1
cal_t = cal.groupby("decile").agg(n=("y", "size"), predicted=("p", "mean"), observed=("y", "mean")).reset_index()

# ---------- apply to the full window (2018-2024) ----------
log("building scoring features (2018-2024)")
fu = features("2024-12"); Xfu = engineer(fu); Zfu = apply_woe(Xfu)
fu["p_action"] = iso.predict(lr.predict_proba(Zfu)[:, 1]); fu["logit_raw"] = lr.decision_function(Zfu)
# contribution of each feature to the log-odds (for the explanation panel)
contrib = Zfu.values * lr.coef_[0]; fu["top_drivers"] = [", ".join(f"{FEATS[j]}:{contrib[i, j]:+.2f}" for j in np.argsort(-np.abs(contrib[i]))[:4]) for i in range(len(fu))]

# ---------- Detector 2 Monte Carlo: P(impossible) under estimator-bias uncertainty ----------
val = con.execute("SELECT units_per_line_at_p05 FROM d2_rate_validation WHERE units_per_line_at_p05 > 0").df()["units_per_line_at_p05"].values
mu, sd = float(np.mean(np.log(val))), float(np.std(np.log(val)))   # empirical log-normal for u = true hours / hours_pt
U = np.exp(rng.normal(mu, sd, 4000))
peak = fu["peak_pt_personal_hpd"].values.astype(float)
fu["p_impossible"] = np.where(peak > 0, (np.outer(peak, U) > 24).mean(axis=1) if len(fu) < 200000 else 0.0, 0.0)
if len(fu) >= 200000:   # chunk to bound memory
    out = np.zeros(len(fu)); idx = np.where(peak > 0)[0]
    for s in range(0, len(idx), 20000):
        ii = idx[s:s + 20000]; out[ii] = (np.outer(peak[ii], U) > 24).mean(axis=1)
    fu["p_impossible"] = out
fu.loc[fu["peak_lb_personal_hpd"] > 24, "p_impossible"] = 1.0   # the rate-free lower bound needs no assumption
log(f"u ~ LogNormal(mu={mu:.3f}, sd={sd:.3f}); median u = {math.exp(mu):.2f}")

# ---------- documented actions (Detector 3 tier A) and expected loss ----------
d3 = con.execute("SELECT npi, MAX(paid_after) AS d3_paid_after, MAX(months_paid_after) AS d3_months, string_agg(DISTINCT source, ',') AS d3_sources, MIN(event_dt) AS d3_event FROM d3_top WHERE tier='A' GROUP BY 1").df()
fu = fu.merge(d3, on="npi", how="left"); fu["documented"] = fu.d3_paid_after.notna().astype(int)
LGD = 0.9
fu["exposure_12m"] = fu.paid_12m.fillna(0)
fu["expected_loss"] = fu.p_action * fu.exposure_12m * LGD
fu.loc[fu.documented == 1, "expected_loss"] = fu.loc[fu.documented == 1, "d3_paid_after"].fillna(0) * LGD + fu.loc[fu.documented == 1, "exposure_12m"] * LGD
def tier(r):
    if r.documented == 1: return 1
    if r.p_impossible >= 0.95 and r.m_over24_concurrent > 0: return 2
    if r.p_action >= 0.05: return 3
    if r.p_action >= 0.01 or r.p_impossible >= 0.5: return 4
    return 5
fu["tier"] = fu.apply(tier, axis=1)
fu["score"] = (100 * (1 - (1 - fu.p_action) * (1 - 0.5 * fu.p_impossible))).round(2)   # combined probability, capped by construction
fu.loc[fu.documented == 1, "score"] = 100.0
fu = fu.sort_values(["tier", "expected_loss"], ascending=[True, False]).reset_index(drop=True); fu["rank"] = np.arange(1, len(fu) + 1)

# ---------- write ----------
out = duckdb.connect(OUT)
out.execute("CREATE OR REPLACE TABLE risk_v2 AS SELECT * FROM fu"); out.execute("CREATE OR REPLACE TABLE risk_v2_woe AS SELECT * FROM woe_df")
out.execute("CREATE OR REPLACE TABLE risk_v2_calibration AS SELECT * FROM cal_t")
out.execute("CREATE OR REPLACE TABLE risk_v2_eval AS SELECT ? AS eval_json", [json.dumps(ev)])
summ = dict(cohort=int(len(tr)), positives=int(y.sum()), base_rate=float(y.mean()), eval=ev,
            calibration=cal_t.to_dict(orient="records"), u_lognormal=dict(mu=mu, sd=sd, median=math.exp(mu)),
            tiers=fu.groupby("tier").agg(n=("npi", "size"), expected_loss=("expected_loss", "sum"), exposure=("exposure_12m", "sum")).reset_index().to_dict(orient="records"),
            top25=fu.head(25)[["rank", "npi", "name", "entity_type", "nppes_state", "tier", "score", "p_action", "p_impossible", "expected_loss", "exposure_12m", "d3_sources", "top_drivers"]].to_dict(orient="records"),
            top25_predicted=fu[fu.documented == 0].sort_values("expected_loss", ascending=False).head(25)[["rank", "npi", "name", "entity_type", "nppes_state", "tier", "score", "p_action", "p_impossible", "expected_loss", "exposure_12m", "top_drivers"]].to_dict(orient="records"),
            scored=int(len(fu)), sum_expected_loss=float(fu.expected_loss.sum()), d1_eligible_rate_in_positives=float(Xtr.loc[y == 1, "d1_eligible"].mean()), d1_eligible_rate_overall=float(Xtr["d1_eligible"].mean()))
os.makedirs("demo/cache", exist_ok=True); json.dump(summ, open("demo/cache/risk_v2_summary.json", "w"), indent=1, default=str)
out.close(); log("done:", OUT)
