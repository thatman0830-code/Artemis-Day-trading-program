# BOT 2.0 Phase 5C v3 Fixed-Dimension Ablation Contract

Status: implementation candidate contract, Phase 5C-W. This document defines engineering semantics only; it does not authorize protected scoring, out-of-sample execution, or trading.

## Frozen source and channel order

The authoritative scientific manifest remains `config/bot2_phase5c_experiment_manifest_v3.json`, SHA-256 `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`. Phase 5C-W does not modify that manifest. The machine-readable manifest projection is `config/bot2_phase5c_v3_ablation_contract.json`; runtime ablation specifications are regenerated from the verified manifest and bind the externally anchored candidate commit.

| Channel | Feature |
|---:|---|
| 0 | `price` |
| 1 | `log_return_1m` |
| 2 | `log_return_3m` |
| 3 | `log_return_5m` |
| 4 | `rolling_price_range_3m` |
| 5 | `rolling_price_range_5m` |
| 6 | `realized_volatility_3m` |
| 7 | `realized_volatility_5m` |
| 8 | `session_open_distance` |
| 9 | `session_high_distance` |
| 10 | `session_low_distance` |
| 11 | `cumulative_volume_session` |
| 12 | `relative_volume_3m` |
| 13 | `volume_acceleration_1m` |
| 14 | `session_vwap` |
| 15 | `price_to_session_vwap` |
| 16 | `seconds_since_session_open` |
| 17 | `session_phase` |
| 18 | `time_sin` |
| 19 | `time_cos` |
| 20 | `cross_market_log_return_1m` |
| 21 | `cross_market_relative_return_1m` |
| 22 | `cross_market_rolling_correlation_5m` |
| 23 | `cross_market_divergence_1m` |

All six frozen conditions use exactly this order and 24 positions. Exact 24-element arrays and active/ablated membership are in the JSON projection and are validated against the manifest in tests.

## Mask semantics and frozen conditions

Each mask element is an integer: `1` means active and `0` means ablated. The full condition `ALL` is 24 ones. The other conditions are manifest-derived:

| Ablation | Zeroed channel indices | Ablated family |
|---|---|---|
| `MINUS_CROSS_MARKET` | 20–23 | Cross-market return, relative return, rolling correlation, divergence |
| `MINUS_VWAP` | 14–15 | Session VWAP and price-to-session-VWAP |
| `MINUS_VOLUME` | 11–13 | Cumulative session volume, relative volume, volume acceleration |
| `MINUS_VOLATILITY` | 6–7 | Realized volatility at 3m and 5m |
| `MINUS_SESSION_TIME` | 16–19 | Seconds since open, session phase, time sine and cosine |

No new, combined, caller-defined, unknown, or reordered ablation is accepted. The runtime identity is a canonical-hash specification containing the ablation/schema version, canonical channel order, mask and membership, frozen manifest SHA, preprocessing version, and candidate implementation commit. `ablation_sha256` is generated from that canonical specification and carried by the split, each prepared partition, and engineering execution/result provenance. The commit-bound hash is generated post-commit; it is not embedded in its own source commit because that would be self-referential.

## Preprocessing order and neutral-value justification

For every feature, the existing `TrainingOnlyStandardizer` fits per-channel mean and population standard deviation on unique, eligible TRAIN observations only. It reuses that frozen state for each partition. Its version is `train-unique-row-population-zscore-v1`; a constant TRAIN channel uses the existing `1e-12` scale guard. Every registered channel is passed through this standardizer, including `session_phase` and time sine/cosine. Therefore standardized zero is exactly the TRAIN mean in normalized units and is the justified neutral contribution for an ablated channel.

The order is:

1. Validate raw rows against frozen instrument, time, feature-order, target, and partition rules.
2. Transform raw values with the TRAIN-fitted standardizer.
3. Apply the frozen 24-element mask; use exact `0.0` for ablated channels.
4. Preserve channel order, sequence length, and tensor dimensions through split validation and model fit.

No validation, calibration, or OOS statistics are used to choose masks or neutral values. Ablation is not missingness: zero-masked values do not receive `MISSING`, `INVALID`, or `STALE` flags, and natural data-quality/missingness handling remains separate.

## Information and architecture contracts

`create_model_input_contract` is versioned as `bot2-phase5c-v3-model-input-contract-v2` and binds model ID, architecture version/hash, canonical and active feature sets, ablated features, mask, input dimensions, preprocessing version, ablation-spec SHA, and manifest SHA. The A2 training boundary verifies that contract against the authorized split and the actual tensor before training.

- **A0:** label-only baselines have no feature tensor. Their contract states `NOT_APPLICABLE_NO_FEATURE_INPUT`; it does not falsely claim the feature-family mask is model input. The label information-end boundary remains unchanged.
- **A1:** the frozen contract uses the same 24 ordered channels and the same post-standardization mask semantics as A2; the declared flattened width is 192. There is no A1 training implementation in this repository/phase, so this is an information contract, not a claim that A1 was trained.
- **A2:** the causal TCN always receives `[batch, 8, 24]`; all six masks preserve the v3 architecture, 7,417 parameters, and every weight/head shape. Only the authorized information mask differs.

The canonical experiment manifest, architecture, optimizer/training policy, risk behavior, execution behavior, and trading authority are unchanged.

## Enforcement and fail-closed reason codes

The data-derived split applies the mask after standardization and records its ablation ID, spec SHA, and mask in prepared-partition fingerprints. Fit-time validation recomputes standardized-and-masked tensors from canonical rows and the authenticated TRAIN preprocessing state. The model rejects a split/model ablation mismatch before training.

Representative machine-readable failures include `ABLATION_NOT_IN_MANIFEST`, `FROZEN_ABLATION_FEATURES_INVALID`, `ABLATION_MANIFEST_BINDING_MISMATCH`, `ABLATION_SOURCE_FEATURE_ORDER_MISMATCH`, `ABLATION_INPUT_WIDTH_MISMATCH`, `ABLATION_INPUT_NONFINITE`, `PREPROCESSING_TRAINING_PARTITION_MISMATCH`, `MODEL_ABLATION_MASK_REQUIRED`, `MODEL_ABLATION_MASK_MISMATCH`, `MODEL_ABLATION_SPLIT_MISMATCH`, and `PREPARED_PARTITION_ABLATION_MISMATCH`.

Tests use synthetic engineering fixtures only. No protected model is scored; no OOS scores are produced; protected OOS execution remains unauthorized; trading authority remains `NONE`.
