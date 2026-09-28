# BOT 2.0 Phase 4 — Causal Regime Foundation

Status: complete on `bot2-phase4-regime-foundation` for architecture review. Phase 3's result remains accurate: no reliable predictive trading signal was demonstrated. This phase does not reinterpret the earlier AUC result, optimize P&L, train neural networks, or connect regime output to orders.

## 1. Candidate taxonomy and representation

The implementation uses a multi-dimensional representation rather than forcing one mutually exclusive label:

- `direction_state`: `UP`, `DOWN`, `NEUTRAL`, or `UNKNOWN`
- `volatility_state`: `EXPANDING`, `CONTRACTING`, `STABLE`, or `UNKNOWN`
- `structure_state`: `TRENDING`, `RANGING`, or `UNKNOWN`
- `primary_state`: `TREND_UP`, `TREND_DOWN`, `RANGE`, `VOLATILITY_EXPANSION`, `VOLATILITY_CONTRACTION`, `TRANSITION`, or `UNCERTAIN`

Weak or incomplete observations become `UNCERTAIN`; they are never force-classified. Every assignment carries a simple probability distribution, confidence, validity, reason codes, source dataset identity, feature/config versions, and `trading_authority: false`.

## 2. Mathematical definitions

At cutoff T, direction is `UP` when `log_return_3 >= 0.001`, `DOWN` when `<= -0.001`, otherwise `NEUTRAL`. Volatility compares causal realized volatility: `ratio = realized_volatility_3 / realized_volatility_5`; `ratio >= 1.20` is expansion and `ratio <= 0.80` is contraction. Structure is `TRENDING` when `abs(log_return_3) >= 0.0005`, otherwise `RANGING`. Primary state selection is deterministic: directional trending states first, then volatility expansion/contraction, then range, then transition, with missing inputs resulting in uncertainty. Thresholds are versioned and configurable in `RegimeConfig`.

## 3. Causal inputs

The layer consumes only Phase 2 causal features: returns, observed-price structure/range, realized volatility, volume-compatible feature rows, VWAP relationship, session/time, and latest-at-or-before-cutoff ES/NQ cross-market values. No order-book or microstructure feature is introduced. Future labels are used only by separate conditional-outcome analytics.

## 4. Baseline regime methods

Phase 4 implements an interpretable deterministic threshold baseline and a multi-dimensional state representation. It does not add clustering or Gaussian mixtures because the current approved data sample and regime stability evidence do not justify extra complexity. This creates a benchmark a future Model A must beat in stability, calibration, and conditional understanding—not P&L.

## 5–7. Frequency, duration, persistence, and transitions

The assignment API provides state frequencies, run-length average/median/max duration, transition counts, normalized transition matrices (via downstream normalization), transition frequency, and churn rate. It supports analysis of RANGE→TREND, CONTRACTION→EXPANSION, TREND→TRANSITION, and TREND→RANGE without assuming those transitions predict anything.

On the known synthetic fixture, ES assignments were: `UNCERTAIN` 5, `TREND_UP` 1, `TREND_DOWN` 3. Durations were UNCERTAIN 5, TREND_UP 1, and TREND_DOWN 3 observations; two off-diagonal transitions occurred. These are fixture-validation numbers, not market results.

## 8. Conditional outcomes

`conditional_outcomes()` joins only valid Phase 2 labels to non-uncertain regime assignments and reports count, mean forward return, probability of up direction, future volatility, MFE/MAE arrays, and barrier-outcome counts. It is designed for out-of-sample evaluation using Phase 3 chronological/purged splits. No real ES/NQ conditional outcome claim is made in this implementation-only milestone.

## 9–10. ES/NQ differences and cross-market relationships

`cross_market_relationship()` pairs an ES assignment with the latest NQ assignment at or before the ES cutoff. It reports simultaneous same-state and divergent-state rates and explicitly records `lag_direction_claim: NOT_ESTABLISHED`; it does not assume either market leads. The synthetic paired fixture produced 9 pairs and 100% same-state rate, which is not evidence of a live relationship.

## 11. Stability across chronological windows

The regime API is deterministic and compatible with Phase 3 chronological and walk-forward windows. Window-by-window frequency, duration, transition, and churn metrics can be compared without using future observations. A production review must reject unstable taxonomies with excessive churn or collapsing state coverage rather than tuning thresholds to favorable periods.

## 12. Uncertainty handling

Missing feature history, missing volatility denominators, and weak evidence generate `UNCERTAIN` plus machine-readable reason codes. The future neural Model A must preserve an abstain/uncertain output and probability distribution rather than treating every timestamp as a confident class.

## 13. Leakage and sanity tests

Phase 4 tests cover future mutation, deterministic reproduction, missing-data uncertainty, transition accounting, cross-market cutoff integrity, and conditional-outcome exclusion. Phase 2 causal feature tests remain active and cover future ES/NQ mutation and past-only VWAP. No test allows a future counterpart observation into an earlier assignment.

## 14. Regime baseline benchmarks

Benchmarks are deterministic assignment reproducibility, uncertainty rate, state duration/persistence, transition frequency, churn, cross-market same/divergent rates, and out-of-sample conditional outcome distributions. They are structural diagnostics, not trading profitability targets. A future neural regime model must beat or improve these benchmarks while preserving temporal isolation and calibration.

## 15. Limitations

The current implementation has no real-data regime report, no exchange-calendar refinement beyond Phase 2 session identifiers, no OHLC/order-book state, no confidence intervals, and no learned transition model. Scalar trade-price events cannot represent same-bar high/low ambiguity. Synthetic fixture results must not be treated as ES/NQ evidence.

## 16. Files changed

- `bot2/regimes/contracts.py`
- `bot2/regimes/assign.py`
- `bot2/regimes/analytics.py`
- `bot2/regimes/test_regimes.py`
- this report

No production strategy, risk, broker, execution, or live-trading files were changed.

## 17. Branch and commit

- Branch: `bot2-phase4-regime-foundation`
- Commit: `68a6a18 Implement BOT 2.0 Phase 4 regime foundation`

## 18. Recommendation for Model A architecture

Model A should be a research-only causal sequence model over versioned Phase 2 feature rows, with separate direction/volatility/structure heads, calibrated probability distributions, and an explicit abstain/UNCERTAIN output. It should be compared against this deterministic baseline under purged walk-forward evaluation and untouched holdout governance. It must not submit orders, alter risk, or replace the deterministic strategy until a separate review gate approves real-data evidence. Neural training has not begun.

## Test results

- NEW PHASE 4 TESTS: 6 passed.
- PHASE 3 TESTS: 9 passed.
- PHASE 2 TESTS: 9 passed.
- PHASE 1 TESTS: 8 passed.
- EXISTING PROVIDER-NEUTRAL REGRESSION TESTS: 5 passed.
- TOTAL: 37 passed.
- Failures/skips: none.

Command used:

```text
.venv\\Scripts\\python.exe -m pytest -q bot2/regimes/test_regimes.py bot2/modeling/test_modeling.py bot2/features_labels/test_feature_label_engine.py bot2/data_foundation/test_data_foundation.py backtesting/test_provider_neutral_market_feed_v1.py backtesting/test_provider_neutral_latency_contract_v1.py backtesting/test_provider_neutral_paper_authority_v1.py backtesting/test_provider_neutral_replay_validation_v1.py backtesting/test_provider_neutral_cockpit_v1.py
```

Phase 5/neural training was not started.
