# Read-only archive scanner

The archive scanner calculates immutable OOS evidence facts from retained files. It supports the canonical BTC closed-candle CSV format and ES/NQ normalized one-minute JSONL format.

For each file it computes the SHA-256 digest over exact bytes, byte and record counts, timeframe, half-open coverage interval, and every observed timestamp discontinuity. Records must be finalized, strictly ordered, unique, UTC, market/timeframe isolated, fixed-duration, finite, and OHLCV-consistent. Paths must resolve to regular files inside the repository.

The scanner is read-only and deterministic. It has no provider, network, credential, partition-selection, strategy, execution, promotion, or trading authority. Every result sets `trading_authority=false`.

Futures discontinuities are intentionally reported as `UNCLASSIFIED_ARCHIVE_DISCONTINUITY`. The scanner does not guess whether a discontinuity is a legitimate exchange closure or missing data. A later schedule-aware reconciliation must classify each interval using frozen authoritative session evidence before an OOS plan can be declared ready.

Only frozen archive copies may be used to construct OOS readiness plans. A scan of an actively growing recorder file is an operational observation, not immutable OOS evidence.
