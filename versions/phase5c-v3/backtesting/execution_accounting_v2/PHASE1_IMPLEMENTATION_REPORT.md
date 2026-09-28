# V2 Phase 1 Contracts and Validation Implementation Report

Status: implemented, offline, economically neutral.

Phase 1 adds immutable records for instrument/economic specifications, provenance, owner assumptions,
capabilities, order intents/transitions, fills, accounting snapshots, risk events, and result identity.
These types validate facts only. They cannot transition an order, generate a fill, calculate PnL,
reserve margin, liquidate, roll a contract, apply funding, or run a strategy.

Validation covers exact schema versions; timezone-aware UTC timestamps; half-open effective intervals;
gap/overlap detection; market/instrument/contract compatibility; exact finite `Decimal` economics;
tick and quantity grids; positive multiplier/step/limits; evidence paths, identities and SHA-256;
canonical serialization/fingerprints; v1/v2 separation; synthetic-fixture isolation; and collecting
production-eligibility reports.

Frozen owner policies remain unchanged: adverse threshold wins declared OHLC ambiguity, otherwise
`AMBIGUOUS_INTRABAR_REJECTED`; end-of-data residuals fail with no fabricated fill and no
accounting-only liquidation. Phase 1 does not execute either policy.

Authoritative retained values are not promoted into a default profile. ES, NQ, BTC spot, and BTC
perpetual remain production-ineligible until every effective-dated authoritative fact, historical
observation, and owner assumption required by their profile is supplied and validated.

The next boundary is Phase 2 order-ledger implementation: append-only legal state transitions,
idempotency, cancellation, replacement, expiry, and lineage. It must not implement OHLC matching or
economic fills; those remain Phase 3.
