# Phase 5C clean-slate methodology draft — P4 calibration and abstention

**Date:** 2026-09-24  
**Role:** P4 — calibration / abstention  
**Status:** Independent initial first draft; proposal only, not adopted or executable.  
**Independence statement:** Prepared from the permitted technical inventory alone, plus public methodological sources. No historical protocol, proposal, review, evaluation output, model output, protected data, or outcome was consulted. No data were scored, no model was run, and no test or implementation was performed.

## 1. Scope and known object

The inventory identifies the experiment as `bot2-phase5c-future-state-esnq-v3`, with instruments ES/NQ; walk-forward identifiers WF1–WF4; horizons 5, 15, and 30 minutes; three 3-class targets (direction DOWN/FLAT/UP, volatility LOW/NORMAL/HIGH, structure RANGE/TRANSITION/TREND); and the A1/A2 neural model identities. It expressly does not define evaluation populations, dates, split semantics, thresholds, or scoring. This draft therefore defines a proposed chronology and rules, but does not assign dates or claim that a given WF identifier has any particular meaning.

The proposed unit of bookkeeping is one canonical sample × instrument × horizon × target head × model/family/ablation. The eventual protocol must specify canonical sample identity, time zone and event-time convention, target-label availability, contract/session handling, and which output dimensions are evaluated. These identities are not fully settled by the inventory.

## 2. Chronological separation

Within each walk-forward evaluation, freeze four non-overlapping chronological blocks, in this order:

1. **Fit block:** fit model weights and any learned preprocessing using this block only.
2. **Calibration block:** after weights and preprocessing are frozen, obtain logits on this later block and fit the probability calibrator. No weight, architecture, feature, or hyperparameter selection is performed here.
3. **Threshold-selection block:** after the calibrator is frozen, generate calibrated probabilities on this still-later block and select the abstention threshold using the predeclared coverage rule below. Do not refit the calibrator or model on this block.
4. **Evaluation block:** only after the preceding artifacts are frozen, generate probability predictions, apply the threshold, and assess outcomes. The evaluation outcomes may not alter fitting, calibration, or threshold selection.

Ordering and non-overlap are design requirements; their dates and sizes remain unspecified. The inventory gives only WF1–WF4 identifiers and does not provide fold dates, fit/calibration/threshold/evaluation boundaries, sample counts, label-completion rules, or sequence-boundary rules. Nor does it specify how to purge or otherwise handle overlapping 5/15/30-minute targets and sequence context at boundaries. Those details must be resolved and frozen before any predictions; no dates, embargo length, or sample allocation can be inferred here. Reuse of the same chronological block for calibration and threshold selection is not allowed by this proposal.

Fit a separate temperature for each model output head, using only that model's calibration block; do not pool labels across the three semantically different heads. If calibration is stratified by horizon, instrument, or another group, the groups and minimum support must be fixed before outcomes are examined. The inventory does not establish the intended calibration granularity, so the simplest draft is one temperature per model × head × walk-forward fold, shared across the declared horizon/instrument rows evaluated by that model within that fold. This granularity is a design choice requiring protocol confirmation, not an inventory fact.

## 3. Calibration method and measures

For each head, let the model emit three finite logits (z=(z_1,z_2,z_3)). Apply scalar temperature scaling:

\[
p_k(T)=\frac{\exp(z_k/T)}{\sum_{j=1}^3\exp(z_j/T)},\qquad T>0.
\]

Choose (T) by minimizing multiclass negative log-likelihood (NLL) over the calibration block's valid examples for that head. This is the one-parameter post-processing method described by Guo et al.; their empirical paper reports that it was effective on the image and document classification datasets they studied, not that it is guaranteed optimal for this task. [Guo et al. (2017), PMLR](https://proceedings.mlr.press/v70/guo17a.html).

For a portable deterministic draft, define candidates as (T=\exp(-4 + 8i/4000)), for integer (i=0,\ldots,4000), i.e. a fixed log-spaced grid from (e^{-4}) through (e^4). Compute mean NLL in canonical row-ID order using a specified numeric precision and stable log-softmax. Select the candidate with minimum unrounded mean NLL; exact ties go to the smaller (T). If all candidates fail numerically or there are no valid labeled calibration examples, record a calibration failure and do not silently fall back to uncalibrated probabilities. The grid, range, precision, and tie rule are explicit draft design choices, not facts established by the inventory; they must be frozen before use. A continuous optimizer could also fit temperature, but its optimizer, tolerances, and termination tie behavior would need equally explicit specification.

For each head, report the following on the evaluation block, before applying abstention:

- **Multiclass NLL:** \(-N^{-1}\sum_i \log p_{i,y_i}\), with a documented numerical floor used only to evaluate exact machine-zero values. NLL is a strictly proper probabilistic score in the population sense; it rewards probability assigned to the realized class. [Gneiting & Raftery (2007), JASA](https://doi.org/10.1198/016214506000001437).
- **Multiclass Brier score:** \(N^{-1}\sum_i\sum_{k=1}^{3}(p_{ik}-\mathbf{1}[y_i=k])^2\). State the sum convention (not divided by three), so values are comparable and unambiguous. Brier's original work introduced verification of probability forecasts; the strictly proper scoring-rule treatment covers categorical quadratic scores. [Brier (1950), Monthly Weather Review](https://doi.org/10.1175/1520-0493(1950)078%3C0001%3AVOFEIT%3E2.0.CO%3B2); [Gneiting & Raftery (2007)](https://doi.org/10.1198/016214506000001437).
- **Classwise reliability:** for each of the three classes, provide one-vs-rest reliability tables/plots comparing mean forecast probability with observed class frequency in fixed, predeclared probability bins; show bin support. Also report top-label confidence reliability by comparing maximum probability with empirical correctness. These are diagnostic summaries; bin boundaries and minimum display support must be frozen, and empty/low-count bins shown as such rather than silently merged.
- **Calibration support:** number of labeled examples with valid probability vectors divided by the common eligible denominator, so missing outputs are visible. Do not calculate calibration measures only on accepted (non-abstained) examples as the primary calibration result: that would conflate probability calibration with selective filtering.

The proper scores characterize overall probabilistic forecast quality, while reliability displays diagnose calibration at class/probability levels; no single scalar proves calibration. Macro-average only after reporting each head separately, and define the averaging weights in advance. Calibration-block NLL is used to fit temperature and is not an unbiased estimate of final performance; report evaluation-block measures separately.

## 4. Abstention score, threshold, coverage, and scoreability

For an available calibrated probability vector (p) from a head, define confidence (c=\max_k p_k). This is the abstention score; it ranges from (1/3) to (1). The predicted class is the first class in the target schema's declared order attaining the maximum. Accept the class prediction if (c\geq\tau); otherwise abstain. The inclusive comparison is fixed. Thresholding maximum confidence is a simple design choice, not a theorem that it is the optimal rejection function. Selective classification formalizes the trade-off between coverage and risk/accuracy when a reject option is used. [El-Yaniv & Wiener (2010), JMLR](https://www.jmlr.org/papers/v11/el-yaniv10a.html).

The protocol must declare a nominal threshold-selection coverage (q\in(0,1]) before looking at threshold-block outcomes. The inventory supplies no such value. A concrete candidate for protocol discussion is (q=0.80), explicitly a proposed operating point rather than an inferred requirement. For each model × head × fold, use only valid predictions from the threshold-selection block. Let (n) be their count. Sort distinct confidence values in descending order and select the **largest numeric** threshold \(\tau\) whose inclusive acceptance fraction \(\#\{c_i\geq\tau\}/n\) is at least (q). Thus tied boundary values are all accepted, and realized selection-block coverage can exceed (q); exact equality is not promised. If (n=0), threshold selection fails. This outcome-independent coverage rule needs no labels from the threshold block. It is deterministic once row order, score precision, and tie comparison are frozen. Thresholds are model/head-specific fitted artifacts, but all models retain the same evaluation denominator.

Report, for each head and model, using the frozen common eligible denominator (D):

- **Prediction availability:** valid probability vectors / \(|D|\).
- **End-to-end coverage:** accepted predictions / \(|D|\). An unavailable input, invalid output, inference failure, or abstention contributes zero accepted predictions; it is not removed from this denominator.
- **Conditional coverage:** accepted predictions / valid probability vectors, as a secondary diagnostic only.
- **Scoreability:** accepted predictions with an observed, valid target / \(|D|\). Also report accepted predictions lacking a scorable target, if any.
- **Selective risk/accuracy:** classification error/accuracy among SCORED cases, always alongside scoreability and coverage. This conditional measure alone can reward abstaining more often, so it cannot stand alone.

For proper probability scores and reliability displays, report the per-model valid-probability support and the shared paired support (sample/head keys for which every model in the comparison emitted valid probabilities). The paired-support results provide like-for-like probability comparisons; per-model results remain descriptive with their support explicitly stated. Neither measure replaces the full-denominator availability, coverage, and scoreability reports.

## 5. Eligibility, denominator, and disjoint status model

Before any model inference, freeze a **model-independent eligible denominator** for each comparison unit and head. It is built from the declared evaluation universe, chronology, input-row key, target/horizon identity, and known valid label availability, without inspecting model output, confidence, or eventual correctness. Apply the same key set (D) to all model families, ablations, and baselines in the comparison. Structural exclusions are decided once by protocol-level criteria and reported by reason; they cannot vary because a model is inconvenient to run. A row with a valid target but missing/invalid input remains in (D) and cannot disappear from coverage or scoreability denominators. If a target is unavailable, it must be excluded from the head-specific (D) by the same pre-inference rule for every model and counted as a common exclusion, not selectively omitted after seeing predictions.

The inventory does not define the evaluation universe, target-validity rule, canonical row key, feature-completeness rule, or fold dates. These must be specified before (D) can be materialized. Do not infer them from model output or recover them by inspecting protected outcomes.

Use a one-hot state field per unit/head/model, with transitions only in the order shown. The named states are mutually exclusive at any one time; the record retains an append-only transition history for audit.

| State | Entry condition and denominator treatment |
|---|---|
| `STRUCTURAL_UNAVAILABLE` | Fails a frozen model-independent structural criterion before inference (for example, outside the protocol's declared sample universe or unsupported target identity). Outside (D); report count and reason for every comparison. A model-specific inconvenience is not structural unavailability. |
| `MODEL_INPUT_UNAVAILABLE` | Is in (D), but the common required feature sequence/input cannot be formed or validated for inference. Remains in all full-denominator coverage and scoreability calculations; do not replace with another row. |
| `PREDICTION_AVAILABLE` | Is in (D) and has a finite, schema-valid three-class probability vector after the frozen calibrator, prior to threshold decision. Contributes to availability and probability metrics. This is an intermediate state. |
| `ABSTAINED` | Transitions from `PREDICTION_AVAILABLE` when (c<\tau). No class action is emitted; count against end-to-end coverage and scoreability. The probability vector remains usable for pre-abstention calibration measures. |
| `SCORED` | Transitions from `PREDICTION_AVAILABLE` when (c\geq\tau) and the predeclared valid target is available for the unit/head. The predicted class and target are compared for the selective classification measures. |
| `FAILURE` (typed) | Any failure prevents a valid next state. Record at least `PREPROCESS_FAILURE`, `INFERENCE_FAILURE`, `OUTPUT_SCHEMA_OR_NUMERIC_FAILURE`, `CALIBRATION_FAILURE`, `THRESHOLD_SELECTION_FAILURE`, and `OUTCOME_UNAVAILABLE_OR_INVALID`. Failures in (D) remain in full-denominator rates and are not recoded as structural exclusions. A failed upstream fit/calibration/threshold artifact invalidates that model/head/fold's dependent predictions and must be reported as such. |

An implementation may need an explicit accepted-but-not-yet-labeled intermediate state if prediction time and outcome-finalization time are separated. It must not label that record `SCORED` until the target is observed and validated. The final reporting snapshot should make clear how many records remain pending versus failed; no synthetic outcome or guessed label is allowed.

## 6. Consequences, standard methods, and choices

**Mathematical consequences:** a probability vector for three classes sums to one; scalar temperature scaling preserves the within-head logit ordering and therefore the argmax class except for numerical ties; thresholding by maximum probability defines a deterministic reject rule after a tie convention is fixed; coverage is the accepted fraction of a stated denominator; selective risk is conditional on acceptance. Proper scores evaluate full probability forecasts, not only whether the top class is correct.

**Standard-method facts sourced above:** temperature scaling is an established one-parameter post-hoc calibration method (Guo et al.); log and quadratic/Brier scoring rules are proper for categorical forecasts (Gneiting & Raftery); selective classification is commonly analyzed through a risk-coverage trade-off (El-Yaniv & Wiener).

**Draft design choices needing protocol authority:** four chronological blocks; one temperature per model/head/fold and a fixed grid; classwise and top-label reliability displays; max calibrated class probability as confidence; a nominal coverage target such as 0.80; inclusive threshold comparison; shared denominator construction; and the typed status taxonomy. These choices are proposed for review, not represented as inventory facts or scientific conclusions.

## 7. Unresolved facts required before any use

The technical inventory alone does not resolve dates or semantics for WF1–WF4, size/minimum support of chronological blocks, timestamp and timezone rules, row keys, exact target-generation/label availability rules, overlapping-horizon and sequence-boundary purges, calibration stratification, the nominal coverage (q), acceptable minimum calibration support, precision/serialization conventions, or evaluation aggregation weights. These are explicit protocol inputs. Until fixed independently and before prediction access, the method is a draft only.
