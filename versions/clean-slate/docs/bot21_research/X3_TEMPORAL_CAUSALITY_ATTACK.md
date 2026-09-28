# X3 Temporal Causality Attack

**Review role:** independent X3 adversarial review of temporal leakage and causal validity.
**Review scope:** the authoritative pasted brief, frozen R20 and frozen R1–R19 records, and the frozen registry only. No protected outputs, OOS artifacts, datasets, features, labels, manifests, or source implementation were inspected.
**Frozen inputs:** expected R20 SHA-256 `A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE`; expected freeze `F3D295541151A251401E6DED7062D655E2E390B58F0B15C40B87083E097D9553`.

## 1. Decision and severity scale

**Objection:** temporal causality is not demonstrated by a high score, a chronological split, or a frozen artifact hash alone. Any unresolved path from information published after the prediction timestamp into training, feature construction, tuning, threshold choice, or reporting is a release blocker.

**Severity:** `CRITICAL` means stop all R1 training and all performance claims; `HIGH` means the claim is inadmissible until repaired and independently checked; `MEDIUM` means the result may be used only as exploratory evidence; `LOW` means documentation or monitoring debt.

## 2. Evidence ledger and epistemic labels

**Claim:** the frozen records can establish what was asserted and hashed, but cannot prove unobserved row-level provenance.

**Support:** this report uses four labels throughout: **Claim** = statement made by the project or protocol; **Support** = what the frozen record actually establishes; **Public evidence** = independently available methodology; **Hypothesis** = a plausible failure mode that still needs an allowed audit.

**Public evidence:** scikit-learn documents chronological splitting with an explicit `gap` parameter: https://scikit-learn.org/1.4/modules/generated/sklearn.model_selection.TimeSeriesSplit.html. Bailey et al. describe the probability of backtest overfitting: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf. A practical description of purging and embargoing is available at https://python.financial/concepts/purged-cross-validation/.

## 3. Prediction-time contract

**Objection — CRITICAL:** no R1 training is admissible until each row has a single prediction timestamp, an information-availability timestamp for every input, a label start and end timestamp, and a declared decision horizon. A bar close is not automatically an availability time; vendor publication, correction, and aggregation delays matter.

**Precondition before any R1 training:** provide a machine-checkable contract proving `available_at <= prediction_at` for every input and `label_end > prediction_at`, with timezone, session, roll, correction, and missing-data rules fixed before model fitting.

## 4. Label horizon and overlap leakage

**Objection — CRITICAL:** overlapping forward labels allow a training label to consume future price information that overlaps a test label, even when row timestamps are ordered. A nominal train/test boundary therefore does not establish independence.

**Hypothesis:** a horizon or event label that crosses the split can leak direction, volatility, or barrier information across the boundary. The repair is purging by label interval plus an embargo at least as long as the maximum information and label overlap.

## 5. Feature rolling and window closure

**Objection — CRITICAL:** rolling extrema, volatility, normalization, rank, swing, displacement, gap, liquidity, and regime features can include the current bar's final values or later bars if the window closure convention is not explicit.

**Precondition:** every feature must state whether it is computable at bar open, bar close, or a delayed publication time; a feature used for a decision at `t` must be reproducible using timestamps no later than `t` under that convention.

## 6. Global transforms and fit scope

**Objection — HIGH:** fitting scalers, imputers, encoders, feature selectors, PCA, volatility targets, or class weights over the full period leaks distributional information from validation and future periods into training.

**Claim versus support:** a frozen registry can identify names and versions, but it does not by itself prove that each transform was fitted inside each training fold. This remains a **Hypothesis** until fold-local fit provenance is available.

## 7. Hyperparameter, threshold, and stopping feedback

**Objection — CRITICAL:** choosing a model, feature set, horizon, threshold, early-stopping checkpoint, or retraining cadence after inspecting validation or OOS results converts that period into training information.

**Precondition:** lock the candidate grid, selection rule, stopping rule, and primary metric before an untouched evaluation period is opened. Any post-open choice requires a new untouched period and a complete trial ledger.

## 8. Event-time versus processing-time causality

**Objection — HIGH:** event-time ordering can differ from processing-time ordering through delayed quotes, out-of-order messages, corrected bars, late settlement, and replay backfills. Sorting by exchange timestamp can still expose data that was not available to the live decision.

**Hypothesis:** a replay that uses corrected or fully aggregated bars may overstate causal availability. Required evidence is an append-only arrival log or an explicit conservative delay policy, not a visual chart check.

## 9. Session boundaries, overnight data, and roll handling

**Objection — HIGH:** ES and NQ have overnight sessions, holidays, maintenance gaps, contract rolls, and differing exchange calendars. A session close, prior-day statistic, or continuous-contract adjustment can import information from a later session or another contract.

**ES/NQ transferability:** a causality rule demonstrated on ES cannot be assumed for NQ. NQ's session liquidity, tick size, roll behavior, and event sensitivity differ; both symbols require their own timestamp and roll audits.

## 10. ES/NQ transfer and symbol-specific selection

**Objection — HIGH:** selecting features, thresholds, or regimes on ES and applying them to NQ is a domain-transfer claim, not evidence of causal validity. Selecting on a pooled ES/NQ result can also leak symbol identity and future cross-sectional information.

**Precondition:** keep symbol-specific preprocessing and selection isolated, freeze a transfer map before evaluation, and report ES and NQ independently with a genuinely forward period for each. A result on one symbol is supportive evidence for that symbol only.

## 11. Cross-sectional and portfolio leakage

**Objection — HIGH:** a timestamp-aligned ES observation can carry information from NQ or from portfolio-level aggregates whose source data arrives later. Cross-symbol features, synchronized ranks, and portfolio normalization need their own availability proof.

**Hypothesis:** pooled training or portfolio metrics may make one market's future state available to another market's prediction. This cannot be cleared by chronological ordering alone.

## 12. Retraining, warm starts, and state carryover

**Objection — CRITICAL:** warm-started models, rolling retraining, cached feature state, optimizer state, selected checkpoints, and prior-period labels can carry future information across a boundary if reset timing is not explicit.

**Precondition:** define the exact information set at each retrain, reset or version every mutable state object, and prove that no state update occurs after the decision timestamp but before the recorded prediction. A fresh process is preferable for the audit.

## 13. Missingness, corrections, and survivorship

**Objection — HIGH:** dropping rows after seeing future completeness, forward-filling corrected values, or retaining only instruments with a complete history can select on future information. Missingness itself can be a future-derived feature.

**Support limit:** no dataset or manifest inspection was permitted in this review, so this is a targeted **Hypothesis**, not a finding. The gate must require point-in-time raw snapshots, correction policy, and an audit of excluded observations.

## 14. Validation design and multiple testing

**Objection — CRITICAL:** a single favorable chronological split does not protect against repeated trials. Reusing the same validation period for architecture, features, thresholds, and narrative creates selection leakage; ordinary k-fold CV is invalid for overlapping financial labels.

**Public evidence:** the purging and embargo principle is described in the financial-ML reference at https://python.financial/concepts/purged-cross-validation/; the backtest-overfitting risk is formalized by Bailey et al. at https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf.

## 15. Release gate and minimal admissible evidence

**Objection — CRITICAL:** R1 training must remain blocked until all of the following are signed and independently reproducible: timestamp and availability contract; fold-local transform and selection logs; label-interval purge and embargo proof; event-time/processing-time policy; symbol-specific ES and NQ checks; retrain-state reset proof; trial ledger; and an untouched final evaluation with no feedback path.

**Decision:** absent that evidence, R20 may be described only as a frozen protocol or research claim. It must not be described as causal, forward-valid, transferable, or deployment-ready.

## 16. Public evidence, unresolved hypotheses, and safety attestation

**New public sources:** 3.

1. https://scikit-learn.org/1.4/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
2. https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
3. https://python.financial/concepts/purged-cross-validation/

**Unresolved hypotheses:** label overlap; current-bar or future-window feature closure; global transform fitting; event-time versus arrival-time mismatch; session and roll leakage; cross-symbol information; mutable retrain state; correction and survivorship selection; and multiple-testing feedback. Each is actionable through the gate above and is not asserted as an observed defect because protected implementation and data were intentionally not inspected.

**Safety attestation:** no protected outputs/OOS artifacts, datasets, features, labels, manifests, or source code were inspected; no tests, training, inference, scoring, benchmark, backtest, trading, installation, or Git mutation was performed. This report is the sole file written for this task.

**Completion UTC:** 2026-09-25T06:23:07Z.
