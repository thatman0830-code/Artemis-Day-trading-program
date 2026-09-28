# X4 — Statistical and Data-Mining Attack on BOT 2.1 Research

Status: COMPLETE — independent conceptual attack, frozen after final save. This report is a methodological gate, not a model, experiment, benchmark, backtest, trading recommendation, or approval to use any data. It does not inspect protected outputs, OOS material, datasets, feature artifacts, labels, manifests, source code, models, or execution material. It does not create a statistical result.

## 1. Mission and attack posture

The question is whether a future R1 model comparison could produce apparently convincing ES/NQ evidence through selection, dependence, leakage, weak denominators, or post-hoc storytelling. The attack assumes that a competent analyst can accidentally create false discovery without malicious intent. Every reported lift must therefore survive controls that were fixed before the relevant result was visible.

The attack is deliberately asymmetric: an unknown or failed gate blocks the associated claim, while a favorable score does not waive a gate. A result may be useful as a hypothesis even when it cannot support deployment or economic claims. “Statistically significant” is never treated as synonymous with causal, stable, cost-adjusted, or transferable.

## 2. Independence and evidence boundary

Inputs were the frozen R20 synthesis (`R20_COORDINATOR_SYNTHESIS.md`), the frozen R20 dependency identities, and the frozen R1–R19/registry material available in that synthesis. I did not read X1–X3 conclusions. R20 reports HEAD `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb` on branch `bot2-phase5c-z-review-remediation`, with expected R20 SHA-256 `A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE` and R0-C freeze SHA-256 `F3D295541151A251401E6DED7062D655E2E390B58F0B15C40B87083E097D9553`.

This is documentary and methodological evidence. The frozen reports establish neither clean market-data authority nor absence of protected-material exposure. No empirical frequency, effect size, or ES/NQ winner is inferred from literature. R20’s report that no current dataset is approved remains a blocker carried into this attack.

## 3. Claim taxonomy and burden of proof

Future claims must be labeled before inspection as one of: descriptive (what the frozen sample contains), predictive (conditional forecast quality), comparative (difference from a named comparator), economic (cost/timing/fill-dependent value), transfer (ES to NQ or period-to-period), or operational (runtime/authority/safety). Each claim needs an estimand, eligible population, forecast origin, horizon/maturity rule, comparator, uncertainty procedure, and boundary.

Evidence classes are separated: FOUNDATIONAL_METHOD supports a method; TECHNICAL_CONSTRAINT supports an interface or causal requirement; EMPIRICAL_RESULT supports only its measured population; PROSPECTIVE_HYPOTHESIS is a question for R1; UNKNOWN means no claim. A literature benchmark on another market cannot silently become ES/NQ evidence. A forecast score cannot silently become a policy value claim.

## 4. Objection ledger and severity

Severity is the consequence if the issue is unresolved: **BLOCKER** invalidates the primary claim; **MAJOR** permits only a sharply narrowed descriptive claim; **MODERATE** weakens interpretation and must be disclosed; **MINOR** affects reproducibility or presentation.

| ID | Objection | Severity | Minimum rebuttal before the affected claim |
|---|---|---|---|
| O1 | Future information, correction vintages, or publication latency enter features or joins | BLOCKER | Versioned temporal contract and point-in-time audit |
| O2 | Holdout/OOS is used for architecture, feature, threshold, loss, seed, or narrative selection | BLOCKER | Immutable untouched evaluation with selection log |
| O3 | Candidate, target, horizon, instrument, and window multiplicity is uncounted | BLOCKER | Complete search ledger and multiplicity-aware inference |
| O4 | Overlapping horizons or adjacent bars are treated as independent observations | MAJOR | Cluster/block or dependence-robust uncertainty and effective-support report |
| O5 | Missingness, inner joins, and abstentions select an easier population | MAJOR | Row-level eligibility, missingness mechanism, and common paired denominator |
| O6 | Model comparison uses different origins, transforms, or information budgets | MAJOR | Matched causal origins, training-only transforms, and predeclared budgets |
| O7 | Hyperparameter/early-stopping decisions reuse validation as evidence | MAJOR | Nested or role-separated development and evaluation chronology |
| O8 | Calibration or thresholds are tuned on the reported test period | MAJOR | Training/development calibration with frozen evaluation calibration |
| O9 | A distributional score is chosen after seeing residuals or tails | MAJOR | Estimand and proper score frozen before evaluation |
| O10 | ES/NQ pooling hides instrument-specific failure or correlation | MAJOR | Per-instrument results, joint model comparison, and interaction uncertainty |
| O11 | Drift or regime labels are retrospectively defined from future paths | MAJOR | Causal rule or explicitly descriptive retrospective analysis |
| O12 | Small effective episode count is presented as large row-count support | MAJOR | Session/block-level support, uncertainty, and inconclusive status |
| O13 | Economic conclusions omit spread, fees, latency, slippage, queue, or fill semantics | BLOCKER for economic claims | Separate authorized cost/fill study with conservative assumptions |
| O14 | Repeated analyst choices are omitted because each run was “reasonable” | MAJOR | Decision diary, candidate inventory, and search accounting |
| O15 | Negative controls or label permutations fail but are ignored | BLOCKER | Stop, diagnose leakage, and repeat only under authorized protocol |
| O16 | Statistical significance is treated as stability or deployment authority | MAJOR | Forward-period, drift, calibration, and authority gates |

## 5. Data-mining attack surface

The effective search is the Cartesian product of representations, sampling cadence, lookback, horizons, targets, labels, losses, architectures, capacity, seeds, transforms, missingness rules, instruments, windows, calibration methods, thresholds, and analyst decisions. Counting only fitted checkpoints materially understates selection. A “small shortlist” still consumes search budget when alternatives were considered and discarded.

Selection bias can arise from choosing a metric after seeing residuals, reporting the best seed, dropping failed cells, changing the denominator, or choosing a favorable period. Cawley and Talbot’s selection-bias result supports treating the whole selection procedure as an overfit-able object; Bailey and coauthors support accounting for repeated backtest selection. These sources motivate controls, not a local correction factor.

## 6. Multiple testing and multiplicity governance

Before R1, register the family of primary estimands, the candidate universe, primary and secondary metrics, instrument and horizon strata, seeds, and stopping rule. The ledger must preserve attempted, failed, blocked, and abandoned cells. A cell that fails operationally remains in the denominator of the planned program audit; it is not silently replaced.

Inference must state the family to which error control applies. Options include a predeclared single primary comparison, family-wise correction, false-discovery control, hierarchical testing, or an explicitly exploratory label. White-style reality-check reasoning, Hansen SPA-style comparison, and Deflated Sharpe reasoning are possible methodological references, but none repairs leakage, bad fills, or an undisclosed candidate universe.

## 7. Dependence, overlap, and effective sample size

Intraday rows are serially dependent, volatility clustered, and often share labels when horizons overlap. A large row count therefore cannot establish a large independent sample. Session, day, event, and block dependence must be reflected in intervals and tests. Resampling must preserve the chosen dependence structure; iid bootstrap and random row shuffles are presumptively invalid for overlapping financial series.

Any reported uncertainty must identify the unit that is resampled or clustered, the number of independent units, overlap treatment, and behavior under a reasonable alternative block length. If support is too sparse for stable inference, the result is INCONCLUSIVE rather than a weak pass.

## 8. Temporal causality and leakage

Timestamp equality is not availability. The temporal contract must identify event/send time, receipt/processing time where available, bar interval completion, corrections, vendor vintage, session/contract identity, and the first permissible forecast origin. Exact joins can select a population; nearest/as-of joins can import stale or future state. Neither receives an unconditional pass.

Transforms, normalization, imputation, feature selection, regime fitting, calibration, early stopping, and threshold selection must use only eligible past data at each origin. Full-sample scaling, future-filled bars, retroactive rolls, smoothed latent states, and target-derived missingness are leakage unless explicitly identified as retrospective description.

## 9. Validation and stopping attack

The validation role must be distinct from the reported outer evaluation. If rolling development is used, all decisions made at an origin must be logged and frozen before the corresponding evaluation interval. Early stopping is a model-selection decision; calling it “training only” does not make it independent when it reads a development interval that is later reported.

The outer sequence must be chronological, with purging/embargo rules appropriate to target maturity and overlap. A final untouched period cannot be used to choose the period, metric, model, seed, calibration, or story. If any evaluation value was inspected and influenced a choice, its claim status changes to development/exploratory.

## 10. Baselines and fair comparison

Every predictive head needs a no-change or training-distribution control where meaningful, a simple linear/statistical control, and a persistence or risk control when the target supports it. Distributional targets require distributional controls; a majority classifier cannot be a return-distribution benchmark. Historical A1/A2 descriptions do not confer approval or weights.

All candidates need the same eligible origins, target maturity, information cutoff, transform fitting policy, missingness policy, and scoring denominator. Equal parameter count and equal compute are different fairness claims and should not be conflated. A complex model earns inclusion by a predeclared scientific question, not novelty.

## 11. Metrics, uncertainty, and practical effect

Choose the estimand before the data are inspected. Proper scores such as log loss, Brier, pinball, CRPS, or a justified likelihood evaluate different forecast functionals; accuracy, correlation, or a favorable tail slice cannot substitute for the selected estimand. Calibration, sharpness, interval coverage, and accepted-set coverage are separate evidence.

Report point estimates with dependence-aware intervals and practical effect units. A statistically detectable improvement can be operationally negligible; a meaningful effect can be uncertain under sparse support. Paired comparisons should use identical origins and outcomes. Any selective subset must report selection rule, numerator, denominator, coverage, and uncertainty.

## 12. Negative controls and falsification

Before accepting lift, run predeclared negative controls: label permutation within causal groups where valid, time-shifted or irrelevant covariates, feature-order controls, and a no-information comparator. A shuffled-label advantage over its no-skill comparator is a leakage or implementation alarm, not a market signal. Negative controls must remain visible even when they fail.

Falsification also includes removing a claimed information source, testing a deliberately delayed version, and checking whether the result survives simple transform alternatives. These are diagnostic hypotheses, not permission to search until a preferred answer appears.

## 13. ES/NQ transferability and heterogeneity

ES and NQ differ in price scale, tick economics, liquidity, volatility, session behavior, contract rolls, and response to common information. A pooled result can be driven by one instrument. Report each instrument and their interaction, plus a joint model only when shared information and missingness are defensible.

Transfer claims require forward periods and instrument-specific evidence, not a favorable average. A model that generalizes ES to NQ, or one regime to another, needs a predeclared transfer estimand and an uncertainty procedure that respects shared time blocks. Evidence from equities, generic forecasting, or other futures is methodological context only.

## 14. Missingness, selection, and denominator integrity

Rows disappear for different reasons: no trade, closure, halt, feed loss, correction, join mismatch, or unknown status. Dropping them can condition on market activity or data quality. Inner joins and exact-match subsets must be described as selected populations, not neutral cleaning.

Retain row-level dispositions and a frozen eligible universe. Paired metrics use the common prediction-availability intersection while preserving abstention and eligibility counts. Empty classes, too few independent sessions, failed runtime artifacts, and missing authority evidence are distinct dispositions; none may be silently dropped to improve a score.

## 15. Minimal statistical governance and blockers before R1

R1 must not begin model comparison until an authorized reviewer has accepted a signed protocol containing: causal data and contract semantics; immutable train/development/evaluation roles; estimands and target maturity; baseline ladder; candidate/search ledger; multiplicity family and correction plan; dependence-aware uncertainty; missingness and abstention rules; negative controls; ES/NQ strata; calibration policy; stopping rule; effect-size reporting; artifact/provenance hashes; and an explicit no-authority boundary.

The current blockers are unresolved scientific-source authority and custody, unresolved availability/derivation evidence, no approved dataset, no frozen R1 protocol, no registered candidate/search family, and no completed cost/fill authority for economic claims. A blocker remains a blocker even if a future score looks strong. No implementation, training, inference, scoring, benchmark, backtest, or trading is authorized by this report.

## 16. Disposition, claims, and freeze attestation

The defensible present claim is: statistical and data-mining governance is a prerequisite for interpreting any later ES/NQ model comparison, and the frozen record does not establish that the prerequisite is met. The central hypothesis for a future authorized study is narrower: after causal availability, matched baselines, dependence-aware inference, search accounting, and instrument-specific reporting, any incremental predictive information may be measurable but is presently UNKNOWN. No profitability, stability, transfer, or deployment claim follows.

Public sources newly added by X4: **0**. Existing frozen public methodological sources relied upon include Cawley & Talbot (2010), Gneiting & Raftery (2007), Pesaran & Timmermann (1992), Bailey et al. (2015), Bailey & López de Prado (2014), Hansen (2005), White (2000), and Ovadia et al. (2019), as listed in the frozen registry. No URLs were added to the registry; their frozen URLs remain the source of record.

Safety attestation: no protected outputs, OOS material, datasets, features, labels, manifests, source code, models, tests, training, inference, scoring, benchmark, backtest, trading, installation, environment changes, or Git mutations were performed. Existing dirty-tree changes were left untouched. The only intended write is this document.

Completion UTC: 2026-09-25T02:00:00Z (recorded at handoff; hash computed after final save). X4 output SHA-256 is returned outside the document to avoid self-reference.
