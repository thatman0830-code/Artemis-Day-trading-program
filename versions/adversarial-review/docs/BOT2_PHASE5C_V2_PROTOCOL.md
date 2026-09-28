# BOT 2.0 Phase 5C v2 — Frozen Experimental Protocol

**State:** protocol frozen for architecture review; no model scoring authorized or performed. This v2 supersedes no historical record: Phase 5C v1, Phase 5A/B, the preflight blocker report, and the v2 draft remain unchanged.

The machine-readable authority is `config/bot2_phase5c_experiment_manifest_v2.json`. Its canonical hash excludes only `manifest_sha256`. Data eligibility measurements are in `docs/BOT2_PHASE5C_DATA_ELIGIBILITY.json`. Review authorization is a separate gate.

## Dataset, source, and row eligibility

- Dataset: promoted Databento Pass B v3 normalized ES/NQ one-minute OHLCV; inclusive source date coverage 2025-06-02–2026-08-26; source manifest SHA-256 `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`.
- Listed contracts and source session inventory are pinned by that manifest and its referenced archive/calendar/rollover hashes. No continuous-contract stitching; preserve exact ticker and contract ID. Use the archived active-window rollover plan; never relabel historical contract bars.
- Timestamp provenance: normalized exchange event-window bar close. Receipt time is unavailable in this historical archive. No local receipt timestamp is fabricated.
- Expected cadence: exactly 60 seconds, checked only within exact contract and source session. No synthetic bars, no implicit carry-forward, no hidden gap compression. Source gap reason `SPARSE_NO_ELIGIBLE_TRADE_AGGREGATE` is ambiguous between absent eligible trade and source omission.
- Date range does not certify every minute as eligible. Use only rows meeting the frozen feature/target/sequence rules below. Exact counts and rates are hash-pinned in the eligibility report.
- ES/NQ cross inputs require same session and exact timestamp. Missing counterpart observations are null/invalid. No forward fill, nearest-time alignment, or future fill.

## Inputs and preprocessing

- Feature schema/version: `bot2-feature-row-v3` / `bot2-feature-registry-v3`, pinned by `config/bot2_feature_registry_v3.json` SHA-256 in the manifest. Exactly 24 features in the registry; no compatibility alias is eligible.
- Sequence: length 8, one-minute cadence across all seven deltas, one session, one exact listed contract; every one of the 24 input fields must be present at every timestep. `session_phase` encoding: OPENING=0, EARLY=1, LATE=2.
- Exact elapsed-time definitions, window requirements, and null behavior are in the registry and Phase 5C cadence repair report. No future input at T; cutoff equals T. Session aggregates use observed bars only.
- Fit per-feature mean and population standard deviation on each unique eligible row in that experiment/window's TRAIN partition exactly once (not once per overlapping sequence); clamp a zero standard deviation to `1e-12`; use those exact parameters unchanged for its validation/calibration and test rows. Main-split TRAIN parameters are then fixed for main validation/calibration and OOS. No use of validation/test/OOS statistics. Sequence categorical encoding is fixed, not learned.
- Missing/non-finite input, invalid identity, incomplete contiguous history, or synchronization failure excludes the affected sequence with the v3 reason code. No imputation.

## Targets and class mapping

- Version: `bot2-future-market-state-v3`, target spec SHA-256 frozen in the manifest; horizons are 5, 15, 30 elapsed minutes.
- Direction: sign(close[T+H]−close[T]); FLAT if absolute displacement is less than one tick; one tick = 0.25 points for ES and NQ. Indices: DOWN=0, FLAT=1, UP=2.
- Volatility: RMS of exactly H future one-minute log returns divided by RMS of the prior 30 consecutive one-minute log returns ending at T. LOW if ratio <0.8, NORMAL for 0.8–1.2 inclusive, HIGH if >1.2. Indices LOW=0, NORMAL=1, HIGH=2.
- Structure: efficiency = absolute log displacement / sum absolute future one-minute log returns; TREND if efficiency ≥0.60 and displacement ≥4 ticks; RANGE if efficiency ≤0.25; otherwise TRANSITION. Indices RANGE=0, TRANSITION=1, TREND=2.
- The target's information interval begins at the first close in the 30-return trailing reference and ends at close T+H. Future interval is T+1 through T+H. Requires exact elapsed cadence, same session and same exact listed contract, with no fill. Invalid reference/future observations invalidate that horizon; do not shorten it.
- Inputs are computed independently using only data at or before T. Future targets are never joined as a feature. Sequence target is the triplet at the final sequence timestamp and must be valid in all three heads for the primary joint eligibility set.

## Candidate architectures, seeds, and training

- A0 consists only of the following non-neural comparators: (1) previous-label persistence, using the most recent target whose information interval ends no later than T, otherwise abstain; (2) TRAIN-majority per root/head/horizon, lexical tie-break; (3) TRAIN-only first-order transition probabilities with Laplace alpha=1, conditioned on the latest eligible past target. Select the strongest A0 separately per root/head/horizon/window using VALIDATION categorical log loss (lower wins), then macro-F1 (higher wins), then fixed lexical model ID (ascending). Freeze that selected baseline for associated test/OOS comparison. No logistic comparator is included: repository logistic code is binary, not a compatible three-class multihead implementation; adding a different candidate is outside this frozen v2 candidate set.
- A1: existing NumPy shared-encoder MLP, input is flattened 8×24 standardized sequence (192 values), hidden width 8, `tanh`, three independent 3-class softmax heads. Initialization is `numpy.random.default_rng(seed)`, normal(0,0.05) for weights, zero biases. Full-batch simultaneous gradient descent, unweighted sum of three cross-entropies, 50 epochs, learning rate 0.01, no early stopping, no dropout, no regularization, no minibatch shuffle.
- A2: existing `CausalTemporalConv.transform` over [batch,8,24], then same 8-unit multihead MLP and optimizer. The code currently implements a fixed causal summary (mean over 8 timesteps, endpoint, and difference between means of x[:,1:] and x[:,:-1]), yielding 72 values. It is not a learned convolution; this exact mismatch is explicitly submitted to the architecture review and blocks approval unless resolved without changing the frozen candidate post-score.
- Fixed model seeds: `[1,2,3]`; report all seeds and aggregate, never best seed only. Candidate architecture/hyperparameters cannot be changed after the v2 freeze.
- No model, baseline, or OOS score was generated during Phase 5C-P.

## Chronological partitions and walk-forward windows

Main partition dates are inclusive and preserve v1 boundaries: TRAIN 2025-06-02–2025-12-31; VALIDATION/calibration 2026-01-01–2026-02-27; OOS 2026-03-01–2026-08-26. Dates with no source session contribute no observations; no date boundary is moved after results. No separate untouched holdout exists in this archive; OOS remains untouched until separately authorized.

Four fixed expanding walk-forward windows:

| Window | TRAIN start–end | VALIDATION start–end | TEST start–end |
|---|---|---|---|
| WF1 | 2025-06-02–2025-07-31 | 2025-08-01–2025-08-29 | 2025-09-02–2025-09-30 |
| WF2 | 2025-06-02–2025-08-29 | 2025-09-02–2025-09-30 | 2025-10-01–2025-10-31 |
| WF3 | 2025-06-02–2025-09-30 | 2025-10-01–2025-10-31 | 2025-11-03–2025-12-31 |
| WF4 | 2025-06-02–2025-12-31 | 2026-01-02–2026-01-30 | 2026-02-02–2026-02-27 |

All dates are inclusive session-date filters; weekends/closures naturally have no rows. The walk-forward test periods end before the main OOS partition starts, preserving the main OOS as untouched. Windows are not reselected or expanded based on outcomes. Walk-forward results still require scoring authorization.

## Purge, embargo, imbalance, and evaluation rows

- Maximum future target horizon = 30 minutes; max registered rolling/reference lookback = 30 minutes; sequence lookback = 7 minutes. Frozen purge/embargo = 30 elapsed minutes, the max of these requirements rounded to a minute.
- Purge any training/validation anchor whose full target-information interval intersects or reaches the next partition; specifically require `label_end_time < next_partition_first_timestamp - 30 minutes`. Apply per exact session/contract; no labels bridge sessions/contracts.
- Exclude the first 30 minutes after each validation/test partition's first in-session timestamp from scored/calibration rows (embargo). Training/validation statistics fit only on the eligible training rows. Do not share windows across partitions. The primary comparison uses the identical intersection of valid observations for every candidate/seed within a given root/head/horizon/window; report excluded counts and reasons.
- No class weights, no oversampling/undersampling, no synthetic examples. Three-head loss is unweighted. Report class prevalence and per-class metrics; do not alter treatment after results.

## Metrics, calibration, uncertainty, and abstention

- Primary: multiclass macro-F1 and categorical log loss, per root/head/horizon/window. For each root/window and each candidate, the confirmatory aggregate is the equal-weight arithmetic mean of the nine head×horizon cell values (3 heads × 3 horizons); report every cell separately as descriptive and do not select cells post hoc. Compare to the strongest A0 selected by the frozen validation rule below. Macro-F1 higher is better; log loss lower is better.
- Secondary: multiclass Brier score (sum of squared class-probability errors divided by class count), balanced accuracy, per-class precision/recall, fixed-order 3×3 confusion matrix, 10-bin equal-width reliability/ECE, and score coverage/reason counts. Raw accuracy is descriptive only, never primary. Report latency p50/p95/p99/max only if the evaluator measures inference time under a pinned environment.
- Metric conventions: predicted class is lowest class index among tied maximum probabilities; per-class precision/recall with zero denominator is 0; macro-F1 is the arithmetic mean of the three class F1 values; balanced accuracy is the arithmetic mean of the three class recalls; categorical log loss clips probabilities below `1e-15`; multiclass Brier is `mean_observation(sum_class((p−onehot)^2)/3)`. Reliability/ECE is top-label: bin `max(p)` into ten fixed equal-width intervals `[0,.1),…,[.9,1]`, compare bin mean confidence with bin accuracy, and compute weighted absolute difference `Σ(n_bin/N*|accuracy−confidence|)`.
- Calibration: one scalar temperature per root/head/horizon, fit on VALIDATION only by minimizing mean categorical log loss with deterministic bounded grid T=0.05…10.00 in 0.01 increments; transformed probability is `p_i^(1/T)/Σp_j^(1/T)`; ties choose the smallest T. Apply unchanged to test/OOS. Also report raw and calibrated metrics and 10 equal-width top-label bins. Never fit on test/OOS.
- Uncertainty: normalized predictive entropy `−Σp ln p / ln 3` with zero terms defined as zero; seed disagreement is the mean of the three pairwise Jensen–Shannon divergences using natural-log entropy divided by `ln 2`. Report both; no learned uncertainty head.
- Abstention: at coverage 100%, 90%, 75%, and 50%, retain lowest normalized entropy predictions, tie-break ascending by timestamp, instrument, then contract ID; thresholds are selected from VALIDATION only and frozen for associated test/OOS; if ties cross a requested rate, include the full tie group and report realized coverage. OOS/P&L cannot choose thresholds.
- Confidence intervals: paired session-cluster bootstrap of metric differences, 2,000 replicates, seed 20260921. Resample the same entire session IDs with replacement within root/window for candidate and comparator to retain pairing and within-session dependence; report percentile 95% intervals. Directional improvement is defined positive for `candidate macro-F1 − A0 macro-F1` and `A0 log-loss − candidate log-loss`. Two-sided empirical sign p is `min(1,2*min((1+n(Δ<=0))/2001,(1+n(Δ>=0))/2001))`; no minute-level IID standard errors. Require at least 20 eligible session clusters per root/window and at least two distinct sessions containing each of the three target classes in every cell; otherwise that cell is inconclusive.

## Shuffled-label control and ablations

- Control seeds `[17,23,42]`, three runs per candidate seed. For each root, exact contract, session, horizon, and head, permute TRAIN labels uniformly among timestamps within that same group; keep class counts fixed and permute the three heads independently. Features remain unchanged. Validation/test/OOS labels are untouched. Re-run the identical frozen pipeline and compare to the original-label result and TRAIN-majority reference. If shuffled-label performance shows a statistically significant primary-metric advantage over the no-skill comparator after the same correction, stop and investigate leakage; do not interpret as market signal.
- Ablations, in fixed order: ALL; MINUS_CROSS_MARKET (`cross_market_log_return_1m`,`cross_market_relative_return_1m`,`cross_market_rolling_correlation_5m`,`cross_market_divergence_1m`); MINUS_VWAP (`session_vwap`,`price_to_session_vwap`); MINUS_VOLUME (`cumulative_volume_session`,`relative_volume_3m`,`volume_acceleration_1m`); MINUS_VOLATILITY (`realized_volatility_3m`,`realized_volatility_5m`); MINUS_SESSION_TIME (`seconds_since_session_open`,`session_phase`,`time_sin`,`time_cos`). Apply one family removal at a time; no post-hoc search or combined ablations.

## Acceptance labels

No single best seed, market, head, horizon, or window can support a broad claim. Report exact paired effect sizes against the validation-selected strongest A0, paired session-bootstrap intervals, class-specific behavior, calibration, all seeds, all windows, and shuffled controls. For confirmatory primary-metric tests, first average each model's three fixed-seed probabilities per observation, compute the nine-cell equal-weight aggregate in each root/window, then compute paired session-bootstrap differences and two-sided empirical sign p-values (add-one correction). Holm at family-wise alpha 0.05 is applied to exactly 32 comparisons: 2 primary metrics × 2 neural architectures (A1 and A2, ALL features only) × 2 roots × 4 walk-forward test windows. A comparison passes uncertainty only when its Holm-adjusted p<0.05 and its paired percentile 95% interval excludes zero in the favorable direction. Per-cell, OOS, ablation, calibration, and coverage outputs are reported with effect sizes and intervals but are not post-hoc significance claims. Apply the same fixed bootstrap method to the 96-test shuffled-label stop family stated in the manifest.

- **SUPPORTED:** for both ES and NQ, candidate improves both nine-cell aggregate primary metrics versus the validation-selected strongest A0 with Holm-adjusted p<0.05 and paired percentile intervals excluding zero in at least 3 of 4 walk-forward windows and all three seeds; no class has zero predictions or zero recall in any reported cell; every head×horizon cell has favorable primary-metric point estimates in both roots (no cell selection); aggregate Brier/ECE point estimates are not worse than A0 in either root; and shuffled-label controls do not trigger the stop rule.
- **PARTIALLY SUPPORTED:** a narrower root/head/horizon subset satisfies the same evidence requirements, while the broad claim does not; claims must state that exact subset and all contrary results.
- **INCONCLUSIVE:** the minimum eligible cluster/class support above is not met, uncertainty spans no difference, seeds/windows disagree with the frozen rule, or incomplete data/metrics prevents the frozen test.
- **NOT SUPPORTED:** adequately powered eligible comparisons show no primary improvement or consistent degradation versus strongest A0; leakage-control failure is a STOP/INVALID experiment, not evidence for or against the model.

There is no hand-picked minimum point delta. Practical effect sizes are reported in original metric units; statistical uncertainty, corrected comparisons, seed/window consistency, both instruments, calibration, class behavior, and negative controls jointly determine the category. These criteria cannot be revised after any test/OOS inspection.

## Execution boundary

OOS, walk-forward performance, and all A0/A1/A2 scoring are prohibited until the architecture-review gate is approved and the user separately authorizes Phase 5C v2 scoring. No Phase 2–5B history is overwritten. No production strategy, risk, broker, paper order, or live-trading behavior is changed. Trading authority is false.
