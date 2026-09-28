# Phase 5C clean-slate methodology — P3 statistical comparison

**Status:** independent initial first draft; methodological proposal, not adopted or executable  
**Date:** 2026-09-24  
**Role:** P3 — statistical comparison  
**Independence statement:** This draft was prepared using only `w/docs/BOT2_PHASE5C_TECHNICAL_INVENTORY.md`. No historical protocol, proposal, review, evaluation or model output, protected data/outcome, or other repository document was consulted. No model, score, test, or trading simulation was run.

## 1. Scope and known object

The inventory identifies a declared experiment with instruments ES and NQ; walk-forward identifiers WF1–WF4; target horizons 5, 15, and 30 minutes; and three separate three-class targets: direction (DOWN/FLAT/UP), volatility (LOW/NORMAL/HIGH), and structure (RANGE/TRANSITION/TREND). It lists three A0 baselines, one A1 model, one A2 model, and ablation families ALL and five feature-removal variants. These are identities only. The inventory expressly does not specify evaluation population, dates, split semantics, eligibility, or scoring.

This proposal concerns predictive classification comparison only. Any performance claim is conditional on the prospectively specified evaluation rows and does not imply trading value, profitability, causal effect, or generalization beyond the declared instruments, horizons, periods, and data regime.

## 2. Evaluation population and row eligibility

### Population

Define the evaluation key as `(walk-forward window, instrument, forecast/anchor time, target horizon)`. Each key has three target heads, scored separately and, for the proposed composite, combined by a declared rule. The finite evaluation population is all keys in WF1–WF4, ES/NQ, and the 5/15/30-minute horizons that satisfy eligibility rules frozen before predictions or results are examined. The inventory provides identifiers but not calendar boundaries or the time semantics of a walk-forward window; those must be resolved from an authorized source and written into the protocol before evaluation. Do not infer them from this inventory.

The population is an out-of-sample, walk-forward population only if each window's training, validation, and test periods are explicitly defined as chronological and every forecast is generated from information available by its anchor time. That is a design requirement, not a fact established by the inventory. Record exact window boundaries, timestamp convention/time zone, anchor-time grid, instrument/contract mapping, and the rule for overlapping or repeated keys before proceeding.

### Eligibility before inference

Eligibility is a deterministic, model-independent function of source rows and the frozen protocol. A key/head is eligible only when:

1. It belongs to a declared instrument, horizon, and WF test period under the frozen date/split definition.
2. The input feature sequence and required timestamps are present, valid under the feature/data contract, and available no later than the forecast anchor. The eight-step, 24-feature identity is inventory fact; the precise as-of and missing-feature rules remain to be specified.
3. The matching target for that instrument, anchor, horizon, and head is present, valid under the target contract, and one of that head's three named classes.
4. Any source-quality exclusion rule is applied identically across all candidate models and does not depend on target value, a model's prediction, its confidence, or its score.

Freeze and version the eligibility table before predictions are made. Publish counts and exclusion reasons by WF × instrument × horizon × head. Never remove rows because a model made an error, was uncertain, produced an unfavorable score, or failed to predict. Future target availability may establish whether a key is evaluable; it may not be used to select favorable outcomes among otherwise eligible keys.

## 3. Pairwise comparability and prediction coverage

All paired comparisons use the exact same eligible key/head set and the same truth labels. The strongest protection against model-specific missing-prediction advantage is a coverage requirement: each model/configuration must return one valid prediction for every eligible key/head in the locked population. Prediction validity rules (class encoding, probability normalization if applicable, finite values, and error handling) must be frozen in advance.

Report coverage and failure counts for every model, configuration, seed, and stratum. A model with any unexplained missing or invalid predictions does not receive a favorable complete-case score. Either classify that run as a failed evaluation under a predeclared protocol or use an explicit predeclared failure penalty that cannot improve its score; do not silently drop its missing rows. If complete coverage cannot be achieved, a pairwise intersection may be shown only as a labeled sensitivity analysis alongside full-population coverage and an adverse missing-prediction sensitivity bound. It is not a confirmatory comparison unless its intersection rule was independently frozen before predictions and cannot be chosen based on observed outcomes or scores.

The same rules apply across A0/A1/A2, ALL and ablated configurations, and all seeds. Training-data or target support differences must not be repaired by changing the test rows per model.

## 4. Metrics and aggregation

### Per-head measures

For each head, report the full 3 × 3 confusion matrix and class support. The proposed principal class-sensitive measure is macro recall (multiclass balanced accuracy):

`MacroRecall = (Recall(class 1) + Recall(class 2) + Recall(class 3)) / 3`.

This gives each named state class equal weight, unlike raw accuracy, whose value depends directly on class prevalence. Report raw accuracy, per-class precision/recall/F1, and macro-F1 as descriptive secondary measures; do not switch the primary measure after seeing which one favors a candidate. Metric choice should match the intended error tradeoffs; classification measures encode different properties and are not interchangeable (Sokolova & Lapalme, 2009).

If class probabilities are part of the declared prediction interface, also report mean multiclass log loss and multiclass Brier score as secondary proper-score metrics, with the exact probability convention and any clipping rule specified before predictions. If probabilities are not emitted, do not infer or reconstruct them from hard labels. Proper scores evaluate probabilistic forecasts and reward truthful probabilities in expectation (Gneiting & Raftery, 2007).

### Proposed single primary scalar

For the primary scalar, first pool the eligible rows across WF1–WF4 separately within each instrument × horizon × head cell, calculate that cell's macro recall, then give equal weight to the 18 cells (2 instruments × 3 horizons × 3 heads). This defines a transparent, finite-population average that does not let a high-row-count instrument, horizon, or head dominate merely because it contributes more rows. Retain the confusion matrices and all per-WF cell summaries; pooling does not authorize suppressing time-window heterogeneity.

Macro recall is undefined in a cell if one or more classes have zero support. The protocol must state before inference whether this makes the primary endpoint non-estimable (recommended default), or whether a different metric/aggregation is chosen. Do not silently omit absent-class cells or average over only classes present after seeing outcomes. If the selected endpoint is not estimable under the realized labels, report that limitation and do not substitute a more favorable endpoint.

For each model comparison, calculate the paired difference in this same scalar (candidate minus comparator; positive favors candidate). Also show differences per instrument, horizon, head, and WF with denominators/support so a composite cannot conceal a regression in one target.

### Walk-forward, instrument, and horizon aggregation

The proposed primary average weights instrument, horizon, and head equally and pools rows over the four declared WF windows within each cell. This is a prospectively selected aggregation choice, not a mathematical necessity. Show each WF's corresponding cell results separately, plus row support and eligible dates. Do not treat rows, instruments, horizons, windows, or seeds as interchangeable independent replicates. In particular, the number of test rows is not the number of independent temporal replications.

## 5. Inference under temporal and cross-series dependence

Forecast errors and classification outcomes can be serially dependent; overlapping 5/15/30-minute targets and contemporaneous ES/NQ observations can also be dependent. IID row-level standard errors, ordinary row bootstrap, or an unpaired test are therefore not justified by the inventory.

The proposed inference is a paired, synchronized moving-block bootstrap over anchor time: each resample draws contiguous time blocks jointly for ES and NQ, carrying every horizon, head, model prediction, and truth at the selected anchors together. Do not resample individual model rows independently. Keep the four WF test segments separated so a sampled block does not cross a test-window boundary; compute the primary endpoint and paired differences anew in each replicate. Block resampling is a standard approach for dependent stationary observations, with validity depending on dependence and block-length conditions; those conditions are not established by this inventory (Künsch, 1989). The block length, number of replicates, treatment of gaps, and interval/test construction are design choices that must be frozen before scores are inspected. Choose block length in the time unit supported by the source grid and at least long enough to preserve known target-overlap dependence; the bar frequency and label-overlap details are absent from the inventory, so no numeric block length can be proposed responsibly here. Report sensitivity to reasonable prespecified block lengths. With only four named windows, window-level asymptotics or a four-cluster standard error should not be presented as reliable merely because four labels exist.

An alternative is a forecast-loss-differential test such as Diebold–Mariano with a dependence-robust long-run variance estimate, when the endpoint is representable by a well-defined paired loss differential and its assumptions and lag choice are justified. DM permits a broad range of loss functions and serially correlated forecast errors, but it does not remove the need to define the target estimand, dependence treatment, or multiplicity family. HAC covariance estimation is a standard method under its regularity conditions, not a cure for arbitrary dependence or an automatic solution for a small number of temporal windows (Diebold & Mariano, 1995; Newey & West, 1987). For the nonlinear macro-recall composite, the paired block-bootstrap route is preferred in this draft because it recomputes the actual endpoint rather than substituting a different loss.

Report effect estimates and confidence intervals alongside adjusted p-values. State the interpretation as uncertainty conditional on these test periods and the sampling/dependence assumptions; four walk-forward identifiers do not establish a population of independent future regimes.

## 6. Multiplicity and claim families

The inventory names three A0 variants, A1, A2, and six ablation identities including ALL. It does not name a single scientific comparator, primary endpoint, alpha, or seed count. These must be declared before unblinding.

**Proposed primary family:** test the three paired A2-versus-A0 contrasts on the single primary scalar above (A0 previous-label persistence, A0 train-majority, and A0 train-transition-matrix). Apply Holm familywise-error adjustment across these three contrasts at a prospectively selected family alpha (conventional proposal: 0.05). Report all three estimates and adjusted p-values; do not select the winning A0 after seeing results or present only a favorable contrast. This is one defensible draft choice, not an inventory fact. If the scientific question instead identifies one external/reference A0 before evaluation, that may be made the sole primary contrast, with the remaining comparisons assigned to secondary families.

**Secondary family:** comparisons involving A1, pairwise comparisons among A0s, and predeclared A2 ablations versus ALL. Treat them as secondary; if making inferential claims, define a separate family and adjust within it (Holm is a conservative standard choice; a dependence-aware stepwise procedure is another option when its assumptions and implementation are prespecified). Report the full planned family, not only significant members.

**Exploratory family:** unplanned pairings, post-hoc subgroup/stratum claims, alternative metrics, alternative block lengths not in the sensitivity plan, and any seed-specific or regime-specific pattern are exploratory. Label them as such and do not use unadjusted exploratory p-values to support confirmatory claims. If seeds are used, freeze the complete seed set; summarize all seeds (for example, mean and dispersion), never select the best-performing seed. Seeds are repeated training randomness, not extra independent market observations. The inventory does not specify whether, how many, or how seeds are paired, so this needs a separate decision.

Holm's step-down method provides familywise-error control when the component p-values are valid; dependent comparisons do not justify treating unadjusted tests as independent evidence. Romano–Wolf's stepwise formal-data-snooping procedure is a recognized alternative that accounts for joint test dependence when appropriate (Romano & Wolf, 2005). White's Reality Check addresses predictive superiority selected from a set of models and motivates accounting for the full search universe rather than reporting only a post-selected winner (White, 2000). These citations support the multiplicity concern; they do not determine which family or endpoint is scientifically primary here.

## 7. Pre-inference lock and reporting checklist

Before any model predictions or result inspection, freeze and retain:

- exact WF dates, chronology, train/validation/test semantics, anchor grid/time zone, and any gaps;
- the key-level eligibility table/rules, class/support behavior, missing-feature handling, and exclusion counts;
- the prediction-coverage and invalid-output policy for every candidate;
- the primary scalar, cell weighting, comparator family, directional hypotheses, alpha, and multiplicity procedure;
- the dependence-aware inference procedure, block definition/length selection, resample count, and planned sensitivity set;
- model/configuration/ablation list and all seeds; and
- reporting tables: denominators, confusion matrices, per-class metrics, per-WF/instrument/horizon/head results, coverage, effect estimates, intervals, adjusted p-values, and all prespecified comparisons.

These details are not available in the inventory and must not be inferred from model outputs. The inventory explicitly says it is not a protocol and does not authorize evaluation, inference, or scoring.

## References

1. Diebold, F. X. & Mariano, R. S. (1995). “Comparing Predictive Accuracy.” *Journal of Business & Economic Statistics*, 13(3), 253–263. https://doi.org/10.1080/07350015.1995.10524599 — Proposes tests of equal predictive accuracy using a broad class of loss functions and allows serially correlated forecast errors under the stated asymptotic and finite-sample methods.
2. Gneiting, T. & Raftery, A. E. (2007). “Strictly Proper Scoring Rules, Prediction, and Estimation.” *Journal of the American Statistical Association*, 102(477), 359–378. https://doi.org/10.1198/016214506000001437 — Defines proper/strictly proper scoring rules and develops categorical and probabilistic forecast scores.
3. Newey, W. K. & West, K. D. (1987). “A Simple, Positive Semi-Definite, Heteroskedasticity and Autocorrelation Consistent Covariance Matrix.” *Econometrica*, 55(3), 703–708. https://doi.org/10.2307/1913610 — Provides a HAC covariance estimator and consistency result under stated regularity conditions.
4. Romano, J. P. & Wolf, M. (2005). “Stepwise Multiple Testing as Formalized Data Snooping.” *Econometrica*, 73(4), 1237–1282. https://doi.org/10.1111/j.1468-0262.2005.00615.x — Proposes a stepwise procedure controlling asymptotic familywise error and exploiting joint dependence among tests.
5. Künsch, H. R. (1989). “The Jackknife and the Bootstrap for General Stationary Observations.” *The Annals of Statistics*, 17(3), 1217–1241. https://doi.org/10.1214/aos/1176347265 — Extends jackknife/bootstrap variance estimation to stationary sequences using blocks, with consistency under stated block-length conditions.
6. Sokolova, M. & Lapalme, G. (2009). “A Systematic Analysis of Performance Measures for Classification Tasks.” *Information Processing & Management*, 45(4), 427–437. https://doi.org/10.1016/j.ipm.2009.03.002 — Systematically analyzes classification measures and shows measure choice relates to task and confusion-matrix properties.
7. White, H. (2000). “A Reality Check for Data Snooping.” *Econometrica*, 68(5), 1097–1126. https://doi.org/10.1111/1468-0262.00152 — Develops a test of predictive superiority over a benchmark accounting for a specification search over candidate models.
