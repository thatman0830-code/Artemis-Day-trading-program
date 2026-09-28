# BOT 2.0 Phase 1 — Reproducible Data Foundation

Branch: `bot2-phase1-data-foundation`

Phase 1 is additive. Existing Databento, replay, deterministic strategy, risk, paper-ledger, monitoring, recovery, broker, and execution paths were preserved. No PyTorch or other neural dependency was installed. No live trading or production risk behavior was enabled.

## Architecture implemented

The new `bot2/data_foundation` package provides a standard-library-only boundary for future BOT 2.0 research and shadow consumers:

`raw event → validation → ES/NQ synchronization → cutoff-bounded deterministic replay → provenance manifest`

The boundary is data-only and always reports `trading_authority: false`.

## Files created

- `bot2/__init__.py`
- `bot2/data_foundation/__init__.py`
- `bot2/data_foundation/contracts.py`
- `bot2/data_foundation/validation.py`
- `bot2/data_foundation/sync.py`
- `bot2/data_foundation/replay.py`
- `bot2/data_foundation/manifest.py`
- `bot2/data_foundation/schemas/raw-market-event-v1.json`
- `bot2/data_foundation/schemas/data-quality-report-v1.json`
- `bot2/data_foundation/schemas/dataset-manifest-v1.json`
- `bot2/data_foundation/test_data_foundation.py`

## Versioned schemas

`bot2-raw-market-event-v1` requires instrument, venue, event type, exchange timestamp, local receipt timestamp, positive price, and non-negative volume. Optional sequence, event ID, and session ID fields preserve provider identity and session context.

`bot2-data-quality-report-v1` records state, checked/accepted counts, machine-readable reason counts, timestamps, maximum observed latency, normalized event hash, and the non-authority invariant.

`bot2-dataset-manifest-v1` records dataset ID, source, instruments, exchange-time range, schema version, validation status, source and normalized SHA-256 hashes, code commit, configuration hash, event count, quality report, creation time, and authority state.

## Validation rules and reason codes

Validation fails closed for invalid schema objects, invalid instruments/required fields, non-positive prices, negative volume, missing/invalid timestamps, receipt time preceding exchange time, future events, stale events, timestamp regression, duplicate identity, sequence regression, optional sequence gaps, expected-interval gaps, cross-market skew, and empty datasets.

Failures raise a `DataQualityError` containing a machine-readable `DataQualityReport`; no malformed rows are silently repaired or forwarded.

## ES/NQ synchronization

`synchronize_es_nq` deterministically pairs nearest exchange-time events within a caller-supplied maximum skew. It does not forward-fill, synthesize events, or use future observations. Missing pairs raise a machine-readable cross-market-skew failure.

## Session and instrument handling

The event contract retains instrument, venue, session ID, exchange time, and receipt time. Existing Databento session/calendar/rollover code remains the source of truth for ES/NQ session boundaries; Phase 1 does not duplicate or replace it. The new layer consumes those identified events and preserves their timestamps.

## Deterministic replay and future-information prevention

`deterministic_replay` accepts a UTC cutoff and includes only events with `exchange_time <= cutoff`, preserving source order. Future events are excluded and counted. The replay output is hashed deterministically, so identical source/configuration produces identical output. No forward fill, random shuffle, or future-derived repair is performed.

## Dataset versioning/provenance

`build_manifest` hashes canonical normalized events, accepts raw source bytes when available, hashes configuration, records the Git commit, records the validation report, and rejects empty or unhealthy datasets. Manifests are deterministic for identical inputs and carry no execution authority.

## Test results

Phase 1 tests cover:

- identical manifest generation;
- duplicate events and timestamp regression;
- invalid prices and volume;
- stale events, interval gaps, and sequence gaps;
- deterministic ES/NQ synchronization and missing-pair failure;
- cutoff replay and future-event exclusion;
- receipt-before-exchange rejection.

Run command:

```powershell
.venv\Scripts\python.exe -m pytest bot2/data_foundation/test_data_foundation.py -q
```

Result: **8 tests passed**.

## Unresolved weaknesses

- The new contract does not yet parse every existing Databento/provider format; an adapter mapping layer is required before consumption by BOT 2.0 features.
- Session calendars remain in existing futures-data modules and need a versioned adapter contract in a later hardening step.
- Trade-event gap detection is opt-in because event streams do not have a universal expected interval.
- Dataset persistence and artifact retention are not changed in Phase 1.
- Existing scheduled-task and runtime output permissions still require deployment-context verification.

## Phase 2 prerequisites

Phase 2 may begin only after review of this report and the branch diff. It may add leakage-safe feature and label contracts, but must not add neural models, training, fusion, or model-based trading logic until the data foundation is integrated with existing Databento/replay fixtures and the adapter/manifest gaps above are addressed.
