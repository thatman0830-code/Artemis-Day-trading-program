# Core v1 production archive adapter API

The production adapters are read-only boundaries. They contain no provider client, credential,
recorder, task-scheduler, order-submission, or trading capability.

## Shared contract

`AdapterMetadata` returns a deterministic dataset identity/fingerprint, supported market and exact
instruments, verified UTC coverage, cryptographic `SourceLineage`, and purpose-specific
`EligibilityFlags`. `iter_events()` returns a single-pass iterator of `CoreMarketDataEvent`; it does
not expose an index or future-row lookup. `data_quality_events` contains immutable sparse-gap facts.

Eligibility is explicit for smoke replay, training/validation, untouched OOS evaluation, and final
acceptance. Callers must check the intended `ArchiveEligibility` before creating a run.

## ES/NQ Pass B v3

`PassBV3ArchiveAdapter` verifies the promoted audit identity, archive-tree fingerprint, original and
continuation plans, plan artifact hashes, calendar and rollover hashes, active windows, request
inventory, per-request raw/normalized/manifest/checkpoint/transaction-descriptor hashes and sizes,
raw-to-normalized economic lineage, exact contract identities, session intervals, ordering, row
counts, sparse missing minutes, and market totals before yielding a row.

It reads normalized JSONL incrementally. Each request is bounded in memory while its corresponding
raw response is checked. Nanoseconds are converted without binary floating-point arithmetic;
sub-microsecond values outside the Core datetime contract fail closed. Every output retains exact
ticker, contract ID, request identity, normalized checksum, plan lineage, session, rollover decision,
and dataset fingerprint. No continuous or adjusted series is constructed.

## BTC Phase 7 partial archive

`BTCPhase7PartialAdapter` accepts only the manifest-declared completed 1m file whose checksum and
completion boundary match before and after reading. It validates UTC ordering, closed status,
Decimal OHLCV, geometry, duplicates, and gaps. Its classification is always
`PARTIAL_RESEARCH_ONLY`: smoke replay is allowed; training, validation, untouched OOS evaluation,
final acceptance, and the 200-trade gate are not.

## Fail-closed limits

These adapters do not broaden Core v1 execution. Limit/stop orders, collision resolution,
cancellation/expiry, forced flatten, rollover execution, full margin lifecycle, BTC funding, and BTC
spot/perpetual accounting remain unsupported and rejected by capability/preflight checks.

