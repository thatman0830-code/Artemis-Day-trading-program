# BOT 2.0 Phase 2 — Versioned Feature + Label Engine

Status: implemented on `bot2-phase2-feature-label-engine`. This phase is data/research-only; it does not change production strategy, risk, broker, paper-ledger, or live execution behavior.

## Architecture

Phase 1 normalized `MarketEvent` records are the only input. `generate_features()` consumes validated, strictly exchange-time-ordered ES/NQ events and emits immutable `bot2-feature-row-v1` rows. `generate_labels()` is a separate API that is allowed to inspect observations after the row cutoff and emits `bot2-label-row-v1` rows. Neither object has execution authority.

Each row carries instrument, observation/cutoff timestamps, session, feature/label version, source dataset ID and SHA-256, validity state, machine-readable reason codes, configuration hash, code commit, and generation timestamp. The registry is `config/bot2_feature_label_registry_v1.json`; JSON contracts are in `bot2/features_labels/schemas/`.

## Causal feature set

The initial registry contains 24 conservative, reproducible features: price; one/three/five-observation log returns; three/five-observation observed-price ranges; three/five-observation realized volatility; session open/high/low distances; cumulative session volume; past-only relative volume and volume acceleration; session VWAP and price-to-VWAP; elapsed session seconds, phase, and cyclic time encodings; and lagged ES/NQ cross-market return, relative return, rolling correlation, and divergence.

Every feature is calculated from observations at or before its own cutoff. Cross-market values use the latest counterpart observation at or before the cutoff; there is no forward fill. Missing values remain `null` and are accompanied by `INSUFFICIENT_HISTORY` or `SYNCHRONIZATION_UNAVAILABLE`. A genuine zero is never used as a missing sentinel. No global normalization is implemented; registry state is explicitly `NONE_CAUSAL`.

Phase 1 data contains trade price/volume rather than OHLC or order-book depth. Therefore the range is an observed-price range and order-book/microstructure features are explicitly deferred.

## Label semantics

Labels support configurable forward event horizons (default 3 and 5), forward return, direction, MFE, MAE, future realized volatility, and first favorable/adverse barrier outcome. Labels are never passed to feature generation. Insufficient future data is `INSUFFICIENT_FUTURE_DATA`; crossing a session boundary is `SESSION_BOUNDARY`; neither barrier is `NEITHER`; and simultaneous favorable/adverse conditions are `AMBIGUOUS_OUTCOME` with outcome metrics quarantined rather than silently resolved. Labels are research annotations only.

Because Phase 1 events have one price per observation (not OHLC), same-observation high/low ambiguity cannot be reconstructed; the scalar-price barrier rule remains conservative and this limitation is recorded for a later richer-data contract.

## Determinism and leakage controls

Identical source events, source hash, configuration, and code commit produce byte-identical serialized rows. The tests mutate future ES or NQ observations and verify earlier feature rows do not change, verify VWAP and rolling windows use only past/current data, reject out-of-order source data, preserve explicit missing semantics, and verify stable serialization. The default generation timestamp is a deterministic epoch value; callers may supply a run timestamp as lineage without changing the feature calculation.

## Files changed/created

- `bot2/features_labels/contracts.py`, `_common.py`, `features.py`, `labels.py`
- `bot2/features_labels/schemas/feature-row-v1.json`, `label-row-v1.json`
- `bot2/features_labels/test_feature_label_engine.py`
- `config/bot2_feature_label_registry_v1.json`
- this report

No production execution or risk files were changed by Phase 2.

## Test results

- NEW TESTS PASSED: 9 Phase 2 tests.
- EXISTING REGRESSION TESTS PASSED: 8 Phase 1 data-foundation tests.
- TOTAL TESTS PASSED (Phase 1 + Phase 2 focused suite): 17.
- Additional existing provider-neutral regression tests passed: 5.
- Combined Phase 2, Phase 1, and provider-neutral regression run: 22 passed.
- Command: `.venv\\Scripts\\python.exe -m pytest -q bot2/features_labels/test_feature_label_engine.py bot2/data_foundation/test_data_foundation.py`
- Static import/compile checks passed. The system Python did not include pytest; the repository `.venv` runner was used.

## Unresolved weaknesses and Phase 3 prerequisites

The feature layer currently uses trade price/volume only, has no bar/OHLC or order-book contract, and has no normalization, training, labels-to-model adapter, model registry, or feature selection. Session inference is based on supplied `session_id` or UTC date; an exchange-calendar contract is still needed for production-grade holiday/early-close handling. Before Phase 3, add an approved feature-store format, richer market-data contracts if required, walk-forward split and leakage audit tooling, and an explicit model/data acceptance gate. Phase 3 is not started by this change.
