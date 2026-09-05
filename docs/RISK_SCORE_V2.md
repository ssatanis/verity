# Verity Fraud Risk Score v2

A calibrated, out-of-time-validated probability of a future integrity action for every Medicaid-billing NPI, a Monte Carlo probability of physically impossible billing, and an expected-loss queue. Built and run on the Verity warehouse on September 5, 2026. Code: detectors/risk_score_v2.py. Outputs: data/risk_v2.duckdb, demo/cache/risk_v2_summary.json.

## 1. What the score is and the four principles behind it

The score answers one question per provider: given everything public data shows about how this NPI billed Medicaid, what is the probability that a federal integrity action (a fraud-authority OIG exclusion or an integrity-ground Medicare revocation) follows, and how many dollars are exposed if it does? Four principles govern the design, each of which fixes a specific weakness in hand-set scores.

- Out-of-time validation. Features use only 2018 to 2022 data; the label is an action dated 2023 or later. Nothing the model sees can be caused by the outcome. This is the test the CMS Fraud Prevention System and the academic literature on CMS data mostly do not run (they train and test within the same years), and it is why our AUC is lower than the 0.80 to 0.85 reported in papers that leak time.

- Additive log-odds evidence. Every feature is converted to a weight of evidence, and the score is a sum of those weights, which is the same structure as Fellegi-Sunter record linkage and credit scorecards. Each provider's score decomposes exactly into per-feature contributions, so the packet can say why.

- Calibrated probabilities, not points. The output is a probability that has been checked against observed outcomes decile by decile. A score of 0.018 means about 18 in 1,000 providers like this one received an action within roughly three years.

- Bounds where the data are censored. T-MSIS suppresses every cell under 12 claim lines, so unit prices are never observed. Implied hours are therefore computed as bounds, and the residual uncertainty is propagated by Monte Carlo into a probability of impossibility rather than a threshold.

## 2. What the field does, and where v2 sits

CMS's Fraud Prevention System runs four model families on every Medicare claim before payment: rules, peer-group anomaly detection, predictive models trained on known cases, and associative link analysis; it reported $3.3 to $10 identified per $1 spent, but OIG found verified savings were about 10 percent of identified [1, 2, 5]. OIG's own data briefs use robust thresholds per measure, for example a pharmacy is "questionable" above the 75th percentile plus three interquartile ranges on any of eight measures, and a prescriber is flagged when it is more than three standard deviations above the mean and in the top 0.3 percent [12, 13]. The academic work on public CMS files (Herland, Bauder, Johnson and Khoshgoftaar) labels providers with LEIE fraud authorities 1128(a)(1), (a)(2), (a)(3) and (b)(7), observes positive rates of 0.03 to 0.3 percent, and reports AUC 0.80 to 0.85 for logistic regression and gradient boosting, with logistic regression matching tree ensembles once class imbalance is handled [16, 17, 18]. The 2025 to 2026 CMS posture ("stop and caught" rather than "pay and chase," the Fraud Defense Operations Center, WISeR, the CRUSH request for information) uses AI for triage followed by clinician adjudication [6, 7, 8, 9]. v2 keeps the FPS structure (rules for documented actions, peer-relative features, a predictive model, a network detector feeding it), adopts the FAU labeling convention, and adds what none of them publish: an out-of-time test with confidence intervals, decile calibration, and expected loss.

## 3. Cohort, label and base rate

Cohort. Every NPI with at least $1,000 of Medicaid payments in service months 2018-01 through 2022-12 in the T-MSIS provider spending file: 1,422,023 NPIs.
Label. y = 1 if the NPI appears on the OIG LEIE with a fraud-authority exclusion type (1128(a)(1) program-related crime, (a)(2) patient abuse, (a)(3) health care fraud felony, (b)(7) fraud, kickbacks and other prohibited activities) dated 2023-01-01 or later, or on the CMS Revoked Providers list with an integrity ground under 42 CFR 424.535(a)(2), (3), (4), (5), (7), (8), (10), (12), (13), (14), (18), (19), (20), (22) or (23) dated 2023-01-01 or later. Administrative revocations and license-based exclusions are not labels. 1,340 positives.
Base rate. π = 1,340 / 1,422,023 = 0.00094 (9.4 per 10,000 over about three years), inside the 0.03 to 0.3 percent band the literature reports for fraud-authority labels [16, 18].

## 4. Features and their information value

All features are computed per NPI from monthly Medicaid payment rows (dollars, claim lines, patients, distinct billing counterparties), from Detector 2's per-month implied hours, and from administrative history. Information value (IV) measures how well a feature separates positives from negatives on its own: IV = Σ over bins of (share of negatives − share of positives) × WOE. Credit-scoring convention: under 0.02 useless, 0.02 to 0.1 weak, 0.1 to 0.3 medium, over 0.3 strong.

| Feature | Definition (2018 to 2022 window) | IV | Logit coefficient |

| log_patients | log(1 + max monthly patients) | 0.253 | 0.543 |

| log_paid | log10 total paid | 0.198 | 0.265 |

| log_paid_ly | log10 paid in the last year of the window | 0.184 | 0.332 |

| peak_pt_personal_hpd | peak implied personal-service hours per day (point estimate) | 0.181 | 0.414 |

| individual | NPPES entity type 1 | 0.167 | 0.434 |

| growth | log((paid last year + 1) / (paid prior year + 1)), clipped to ±6 | 0.140 | 0.585 |

| paid_per_patient | log10(1 + peak month paid / max patients) | 0.122 | 0.274 |

| m_over16 | months with implied hours over 16 per day | 0.093 | 0.225 |

| m_over24 | months with implied hours over 24 per day | 0.057 | 0.112 |

| m_over24_concurrent | impossible months billed by three or more organisations | 0.047 | 0.042 |

| max_billing_orgs | max organisations billing for this rendering NPI in a month | 0.046 | 0.200 |

| n_months | months with any payment | 0.027 | 0.079 |

| log_ramp | log of max(month paid / median of prior six months) | 0.021 | 0.111 |

| log_counterparties | log(1 + max distinct counterparties) | 0.017 | 0.068 |

| top3_share | share of total paid in the three largest months | 0.003 | −0.014 |

| prior_admin | administrative revocation, NPPES deactivation or opt-out before the window end | 0.001 | 0.001 |

Detector 1 community membership is recorded but not used in the model: the ownership files are a 2026 snapshot, so membership cannot be computed as of 2022 without leaking. In the cohort, 0.07 percent of NPIs sit in an eligible community and 0.00 percent of positives do, which is itself informative: the ghost-network signal and the individual-action label describe different populations (facilities versus clinicians).
Two findings matter for the story. Growth is the single strongest coefficient: a provider whose payments jump from one year to the next is the most likely to be acted on, which is the bust-out pattern. And the concurrency rule the pipeline uses for Detector 2 tier A (impossible hours billed by three or more organisations) adds almost nothing once impossible hours themselves are in the model (coefficient 0.04). That does not mean concurrency is not fraud; it means regulators have not yet been acting on it, which is an argument for the product, not against the rule.

## 5. The model

### 5.1 Weight of evidence

Each feature x is cut into up to ten quantile bins on the training set. For bin b, with n₁ᵦ positives and n₀ᵦ negatives out of N₁ and N₀ in total (Laplace-smoothed by 0.5):

```
WOE_b = ln[ (n₁ᵦ + ½) / (N₁ + ½K) ] − ln[ (n₀ᵦ + ½) / (N₀ + ½K) ]      K = number of bins
```

A provider's feature value is replaced by the WOE of its bin. WOE is the log likelihood ratio of that bin under "will be acted on" versus "will not," so a score built by adding WOEs is a naive-Bayes log-odds, the same object as the Fellegi-Sunter match weight Σ log(mᵢ/uᵢ) [24, 25].

### 5.2 Logistic regression on WOE features

```
logit p = β₀ + Σᵢ βᵢ · WOEᵢ(xᵢ)            fitted by L2-penalised maximum likelihood (C = 0.5) on a 70 percent split
β₀ = −6.90 (≈ ln π/(1−π) at the base rate)
```

Fitting β on top of WOE, instead of using β = 1 for everything, lets correlated features (total paid and last-year paid, over-16 and over-24 months) share credit instead of double counting. The coefficients are in the table above; every one is positive except a negligible top-3 share.

### 5.3 Calibration

Raw logistic outputs are mapped through isotonic regression fitted on the 30 percent held-out split [26]: a monotone step function ẑ(f) minimising Σ(y − ẑ(f))². The result is checked by decile on the same held-out set:

| Decile | n | Predicted | Observed | Decile | n | Predicted | Observed |

| 1 | 42,661 | 0.00013 | 0.00014 | 6 | 42,660 | 0.00074 | 0.00075 |

| 2 | 42,661 | 0.00019 | 0.00016 | 7 | 42,661 | 0.00104 | 0.00105 |

| 3 | 42,660 | 0.00024 | 0.00028 | 8 | 42,660 | 0.00127 | 0.00124 |

| 4 | 42,661 | 0.00047 | 0.00049 | 9 | 42,661 | 0.00146 | 0.00152 |

| 5 | 42,661 | 0.00069 | 0.00059 | 10 | 42,661 | 0.00320 | 0.00319 |

The top decile carries 3.4 times the base rate and the bottom decile 0.15 times; predicted and observed agree to the fourth decimal in every decile. Above p ≈ 0.02 the isotonic fit rests on a handful of positives, so probabilities over 0.5 (six NPIs) should be read as "very high," not as 0.78 versus 0.63.

## 6. Out-of-time evaluation with confidence intervals

Held-out set: 426,607 NPIs, 402 positives, base rate 0.00094. Intervals are percentile bootstrap, 1,000 resamples of the held-out set [36].

| Metric | Point | 95 percent interval | Lift over base rate |

| AUC | 0.735 | 0.713 to 0.759 |  |

| Average precision | 0.0054 | 0.0027 to 0.0134 | 5.7× |

| Precision at 50 | 0.020 | 0.000 to 0.100 | 21× |

| Precision at 250 | 0.024 | 0.008 to 0.044 | 25× |

| Precision at 500 | 0.014 | 0.006 to 0.028 | 15× |

| Precision at 1,000 | 0.011 | 0.005 to 0.018 | 12× |

| Precision at 2,500 | 0.008 | 0.004 to 0.011 | 8.5× |

Read this honestly. An AUC of 0.735 out of time is a real, defensible signal for an event this rare, and the intervals at K = 250 and above exclude the base rate by a wide margin. It is not "we can find fraud with 60 percent precision." A reviewer working the top 1,000 of the held-out ranking would find about 11 future federal actions instead of the single one they would find at random, and the future actions are themselves an undercount of fraud, since most fraud is never acted on. That is the right framing for Robbins and for McCarthy: measured lift on a label nobody can argue with, with the uncertainty printed next to it.

## 7. Probability of impossibility (Detector 2, Monte Carlo)

Implied hours are computed from dollars through an estimated unit price, and the estimator is biased in a known direction: because T-MSIS suppresses cells under 12 lines, paid / lines averages over one or more units per line and sits above the true unit price, so hours are understated. The Minnesota validation measures that bias directly for 131 code-years: u = estimated price / published price, i.e. true hours = hours_pt × u. Its log is roughly normal:

```
ln u ~ Normal(μ = 1.160, σ = 1.148)        median u = 3.19  (the point estimate understates hours about threefold on median)
P_impossible(npi) = P( u × peak_hours_pt_personal_per_day > 24 )      estimated with 4,000 draws of u
P_impossible = 1 whenever the rate-free lower bound  lines × minutes_per_unit / days  already exceeds 24 (no assumption needed)
P_impossible = 0 for organisation NPIs (a physical constraint applies only to a person)
```

Among individual NPIs: 2,144 have P_impossible ≥ 0.95, 31,794 are between 0.5 and 0.95, and 418,913 between 0.05 and 0.5. The last group is the honest cost of the Minnesota calibration: because the estimator understates hours by 3× on median, a clinician whose point estimate is 8 hours a day has a real chance of being over 24. That is why P_impossible feeds the tiers only at 0.95 (tier 2, with concurrency) and 0.5 (tier 4), and why the primary probability is P_action, which is validated against outcomes.

## 8. Tiers, expected loss and the single score

```
lift(npi) = P_action / π                                     π = 0.00094
tier 1  documented: on a tier-A list and Medicaid paid in later months (Detector 3). A fact, not a prediction.
tier 2  P_impossible ≥ 0.95 and at least one impossible month billed by ≥ 3 organisations
tier 3  lift ≥ 10        (P_action ≥ 0.0094)
tier 4  lift ≥ 3  or  P_impossible ≥ 0.5
tier 5  everything else

exposure_12m   = Medicaid paid in the last 12 observed months (2024)
LGD            = 0.9   (CMS FPS adjusted savings ran near 10 percent of identified; OIG 2019 [5])
expected_loss  = P_action × exposure_12m × LGD                                  (tiers 2 to 5)
               = paid_after_action × LGD + exposure_12m × LGD                  (tier 1)

score (0 to 100) = 100 × [ 1 − (1 − P_action)(1 − ½ P_impossible) ]            tier 1 fixed at 100
```

The score is a probability-of-at-least-one-problem under independence, with impossibility discounted by half because its label link is weaker than P_action's. Expected loss follows the credit-risk identity EL = PD × EAD × LGD [28]. Ranking by raw expected loss puts Medicaid's largest legitimate payers (county health departments, fiscal intermediaries, transportation brokers with $500M to $1B a year and P_action near 0.005) at the top, because a tiny probability times a huge exposure is still a large number. That is mathematically correct and operationally useless, so the queue is expected loss within lift ≥ 10: providers who are already ten times more likely than average to be acted on, ordered by how much money is riding on them.

## 9. Results on the full 2018 to 2024 window (1,680,326 NPIs scored)

| Tier | Meaning | NPIs | Expected loss |

| 1 | Documented action, then Medicaid payment | 369 | $75.1M |

| 2 | Impossible personal hours (P ≥ 0.95) with concurrency | 228 | $7.6M |

| 3 | Lift ≥ 10 (1,008 individuals, 111 organisations) | 1,151 | $22.7M |

| 4 | Lift ≥ 3, or P_impossible ≥ 0.5 | 94,503 | $502.2M |

| 5 | Informational | 1,584,075 | $204.5M |

Total expected loss over the next year under the model is $812M, of which $608M sits in tiers 1 to 4 (96,251 NPIs, 5.7 percent of providers). Expected loss in tiers 1 to 4 by state: California $101.2M (13,652 NPIs), New York $79.6M, Texas $34.2M, Ohio $24.5M, Massachusetts $23.4M, New Jersey $23.3M, Michigan $21.9M, Arizona $18.8M, Virginia $17.6M, Illinois $17.4M.

### The queue (lift ≥ 10, by expected loss), first ten, NPIs only

| NPI | State | Type | Tier | P_action | Lift | P_impossible | Expected loss | 12-month exposure | Drivers (log-odds contribution) |

| 1891803037 | NY | individual | 3 | 0.018 | 20 | 1.00 | $1.55M | $93.2M | over-16h months +0.77, patients +0.51, peak hours +0.34, over-24h months +0.33 |

| 1962476903 | NJ | individual | 2 | 0.484 | 513 | 1.00 | $0.90M | $2.1M | over-16h months +0.99, patients +0.51, over-24h months +0.45, peak hours +0.34 |

| 1730366824 | TN | organisation | 3 | 0.018 | 20 | 0.00 | $0.76M | $45.5M | patients +0.51, peak hours +0.34, growth +0.20 |

| 1043528235 | IN | individual | 3 | 0.018 | 20 | 1.00 | $0.59M | $35.2M | over-16h months +1.05, patients +0.51, peak hours +0.34, over-24h months +0.26 |

| 1316982309 | IN | individual | 2 | 0.018 | 20 | 1.00 | $0.50M | $30.1M | patients +0.51, over-16h months +0.48, peak hours +0.34 |

| 1073629069 | NY | individual | 2 | 0.745 | 791 | 1.00 | $0.44M | $0.7M | over-16h months +0.79, patients +0.51, over-24h months +0.38 |

| 1801954474 | WI | individual | 3 | 0.018 | 20 | 1.00 | $0.31M | $18.5M | patients +0.51, over-16h months +0.48, peak hours +0.34 |

| 1952628422 | CA | individual | 2 | 0.018 | 20 | 1.00 | $0.22M | $13.5M | patients +0.51, over-16h months +0.48, peak hours +0.34 |

| 1558452730 | NY | individual | 3 | 0.018 | 20 | 1.00 | $0.21M | $12.9M | patients +0.51, over-16h months +0.48, peak hours +0.34 |

| 1730272709 | NV | individual | 3 | 1.000 | 1,061 | 1.00 | $0.00M | $0.0M | over-16h months +0.99, patients +0.51, over-24h months +0.47 (no 2024 billing: exited) |

An individual NPI with $93M of Medicaid in twelve months is almost certainly a supervising or umbrella NPI under a state billing convention, which is why the reasons panel must accompany every row and why these are referral candidates for records review, not findings. Names are deliberately omitted here; the console shows them behind login.

## 10. The reviewer feedback loop, restated properly

Each reviewer decision on a packet updates a Beta posterior on the precision of the evidence family that produced it. With a accepts and b rejects and a Beta(2, 2) prior:

```
precision_f | data ~ Beta(a + 2, b + 2)        posterior mean (a + 2) / (a + b + 4)
w_f = 2 × posterior mean                        starts at 1.0, moves toward 2.0 or 0.0
```

In v2 the same posterior can be used as a queue allocator: draw a precision for each family from its posterior (Thompson sampling) and route the next packet from the family with the highest draw, which spends reviewer time where the evidence is proving out and keeps exploring the rest [33]. With 17 draft packets the weights are prior-dominated and should be described as the mechanism, not as a result.

## 11. Limitations, stated the way a judge would state them

- The label is "was acted on," not "was fraudulent." Most fraud is never acted on and some actions are wrong. Lift over the base rate is a lower bound on lift over true fraud, and the calibration is calibration to enforcement, which lags behavior by years.

- Suppression bias. T-MSIS hides cells under 12 lines, so small providers are underrepresented and the impossibility bound cannot see a solo clinician's small-cell billing at all.

- Supervising-NPI conventions. Some states put a clinic's whole volume under one rendering NPI. The model learns that this pattern predicts action (it does), but a large share of tier 3 and 4 individuals will be legitimate umbrella billers. The packet says so and the reviewer decides.

- Calibration tail. Above p ≈ 0.02 the isotonic step function rests on very few positives; treat p over 0.5 as "very high," not as a point estimate.

- Snapshot features. Ownership (Detector 1) is a 2026 snapshot and is excluded from the out-of-time model for that reason; the community score remains a separate, structure-based rank with its own precision-at-K evaluation.

- Expected loss uses last-year exposure as a proxy for next-year exposure and a single LGD of 0.9. Both are defensible defaults from CMS's own recovery record, not estimates from this data.

## 12. How to run it and what to put on screen

```
.venv/bin/python detectors/risk_score_v2.py           # ~6 minutes on the Mac; writes data/risk_v2.duckdb and demo/cache/risk_v2_summary.json
# tables: risk_v2 (one row per NPI: p_action, lift, p_impossible, tier, score, expected_loss, top_drivers, ...),
#         risk_v2_eval (metrics JSON), risk_v2_woe (bins, WOE, IV), risk_v2_calibration (deciles)
```

On stage, three numbers and one table carry the whole argument: AUC 0.735 (0.713 to 0.759) out of time on 1.4 million providers; precision at 250 of 2.4 percent against a base rate of 0.09 percent, a 25× lift with the interval printed; and the calibration table, which says the probabilities mean what they say. Then the queue: providers ten times more likely than average to be acted on, ordered by the dollars riding on them, each with its drivers. When the ML judge asks what the confidence intervals are, they are already on the slide.

## References

[1] CMS, Fraud Prevention System Report to Congress, first year. [2] CMS, FPS second year report. [5] HHS-OIG (2019), CMS could improve evaluating and reporting FPS payment-recovery savings. [6] CMS, Fraud Defense Operations Center fact sheet. [7] CMS, Crushing Fraud annual report (2025). [8] CMS Innovation Center, WISeR model. [9] Federal Register, CRUSH RFI, Feb 27 2026. [12] HHS-OIG OEI-02-09-00600, Retail pharmacies with questionable Part D billing. [13] HHS-OIG OEI-02-17-00250, Opioids in Medicare Part D. [16] Herland, Khoshgoftaar, Bauder (2018), Big Data fraud detection using multiple Medicare data sources, J. Big Data. [17] Herland, Bauder, Khoshgoftaar (2019), The effects of class rarity, J. Big Data. [18] Johnson, Khoshgoftaar (2019), Medicare fraud detection using neural networks, J. Big Data. [24] Fellegi and Sunter (1969); Splink documentation of the model. [25] Weight of evidence and information value, credit-scoring convention. [26] Niculescu-Mizil and Caruana (2005), Predicting good probabilities with supervised learning, ICML. [28] Expected loss = PD × EAD × LGD. [29] Adams and MacKay (2007), Bayesian online changepoint detection. [33] Russo et al., A tutorial on Thompson sampling. [36] DiCiccio and Efron (1996), Bootstrap confidence intervals, Statistical Science. [45] CMS FY2025 improper payments fact sheet. Full URLs in docs/RISK_SCORE_V2.md.

## Reference URLs
- [1] https://www.cms.gov/About-CMS/Components/CPI/Widgets/Fraud_Prevention_System_Report_toCongress-1stYear.pdf
- [2] https://www.cms.gov/About-CMS/Components/CPI/Widgets/Fraud_Prevention_System_2ndYear.pdf
- [5] https://oig.hhs.gov/reports/all/2019/the-centers-for-medicare-medicaid-services-could-improve-its-processes-for-evaluating-and-reporting-payment-recovery-savings-associated-with-the-fraud-prevention-system
- [6] https://www.cms.gov/files/document/cpi-fdoc-fact-sheet-updated-first-year.pdf
- [7] https://www.cms.gov/files/document/crushing-fraud-annual-report.pdf
- [8] https://www.cms.gov/priorities/innovation/innovation-models/wiser
- [9] https://www.federalregister.gov/documents/2026/02/27/2026-03968/request-for-information-rfi-related-to-comprehensive-regulations-to-uncover-suspicious-healthcare
- [12] https://oig.hhs.gov/oei/reports/oei-02-09-00600.pdf
- [13] https://oig.hhs.gov/oei/reports/oei-02-17-00250.pdf
- [16] https://link.springer.com/article/10.1186/s40537-018-0138-3
- [17] https://link.springer.com/article/10.1186/s40537-019-0181-8
- [18] https://link.springer.com/article/10.1186/s40537-019-0225-0
- [24] https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html
- [25] https://www.listendata.com/2015/03/weight-of-evidence-woe-and-information.html
- [26] https://www.cs.cornell.edu/~alexn/papers/calibration.icml05.crc.rev3.pdf
- [28] https://en.wikipedia.org/wiki/Expected_loss
- [29] https://arxiv.org/abs/0710.3742
- [33] https://web.stanford.edu/~bvr/pubs/TS_Tutorial.pdf
- [36] https://projecteuclid.org/journals/statistical-science/volume-11/issue-3/Bootstrap-confidence-intervals/10.1214/ss/1032280214.pdf
- [45] https://cms.gov/newsroom/fact-sheets/fiscal-year-2025-improper-payments-fact-sheet
