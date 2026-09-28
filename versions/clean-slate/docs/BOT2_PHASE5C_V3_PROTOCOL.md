# BOT 2.0 Phase 5C v3 Frozen Protocol

**Status:** Frozen protocol, pending independent review; OOS evaluation is not authorized.  
**Frozen:** 2026-09-22  
**Manifest:** `config/bot2_phase5c_experiment_manifest_v3.json`  
**Canonical SHA-256:** `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`

The manifest is authoritative for the dataset identity, eligibility, feature and target contracts, split dates, models, training configuration, calibration, uncertainty/abstention, shuffle control, ablations, metrics, acceptance criteria, and authority flags. Its hash is SHA-256 over sorted compact UTF-8 JSON with `manifest_sha256` excluded. The prior v2 manifest remains unchanged; see `BOT2_PHASE5C_V2_SUPERSESSION.md`.

## Frozen experimental design

- Instruments: the exact ES and NQ listed-contract inventories and source/eligibility hashes frozen in v2-derived source metadata. No continuous-contract adjustment.
- Feature registry: v3, 24 features, 60-second cadence, sequence length 8, exact-session/contract identity, contiguous timestamps, no missing-value imputation, and no future/counterpart forward fill.
- Targets: three separate 3-class heads (direction, volatility, structure) at frozen 5/15/30-minute horizons. Target intervals, categorical meanings, and feature/target hashes remain the v2-frozen contracts.
- Chronological partitions: TRAIN 2025-06-02–2025-12-31; VALIDATION_AND_CALIBRATION 2026-01-01–2026-02-27; OOS_TEST 2026-03-01–2026-08-26. Walk-forward windows and seeds `[1, 2, 3]` are taken verbatim from the manifest.
- Purge/embargo: maximum label horizon 30 minutes, maximum feature lookback 30 minutes, 30-minute purge and embargo, no session/contract bridging, and identical evaluation intersection.
- A0 and A1 remain frozen comparators. A1 is a deterministic snapshot baseline. A0 selection follows the manifest's validation-only strongest-baseline rule. No model selection may use OOS outcomes.
- A2 is the learned causal temporal convolution network documented in the implementation report. It is research-only, has no trading authority, and cannot place or authorize orders.
- Training: NumPy CPU, fixed seeds, Adam at 0.001, batch size 256, chronological contiguous batches, maximum 50 epochs, validation-based early stopping with patience 5, global gradient norm clipping at 1.0, equal head loss weights, no class weighting/resampling/synthetic examples, and frozen deterministic initialization. Exact values are in the hashed manifest.
- Calibration and abstention thresholds are selected on VALIDATION only; OOS fitting and PnL-based tuning are prohibited. Shuffled-label permutations affect TRAIN only and preserve the frozen grouping/class-count rule. Six feature ablations and the primary metrics/acceptance rules are frozen in the manifest.

## Leakage and safety controls

The TCN uses left-only zero padding, per-position causal convolutions, and a readout from the last valid timestamp only. Its temporal receptive field is 15 positions, greater than the eight available input rows; therefore only eight observed historical steps are available and the additional receptive field is left-padding zeros, never future values. No bidirectional layer, pooling over future/padded output positions, dropout, or batch normalization is used.

The current implementation is preflight-only. It does not construct dataset windows for model fitting from the protected evaluation interval, compute model performance, calibrate on OOS, or produce scores. Any subsequent scoring requires this exact protocol, clean implementation state, complete required artifacts, an independent review approval, and separate explicit authorization. Trading authority remains false.
