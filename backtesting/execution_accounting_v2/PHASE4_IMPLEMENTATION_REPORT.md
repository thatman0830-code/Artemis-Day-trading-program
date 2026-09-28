# V2 Phase 4 Instrument Accounting Implementation

Phase 4 implements `INSTRUMENT_ACCOUNTING_V2_PHASE4_1` as an immutable, deterministic,
single-instrument event ledger downstream of accepted Phase 3 fills.

## Implemented

- ES and NQ futures accounting with verified multipliers, long/short/add/reduce/close/reverse,
  exact Decimal weighted-average reference basis, realized/unrealized PnL, and variation settlement.
- BTC spot base-quantity/quote-cash accounting with explicit zero-margin unlevered facts and no funding.
- separately gated BTC linear-perpetual accounting requiring explicit capability, mark/oracle/funding
  lineage, margin facts, fee facts, and exact contract identity.
- immutable separate commission, exchange-fee, accepted-fill slippage, funding, and settlement
  attribution; economic identities cannot be applied twice.
- clearing and customer margin recorded separately from effective-dated facts. A maintenance breach is
  an immutable accounting fact only and creates no order or liquidation.
- canonical availability-time ordering, point-in-time specification validation, tick/quantity grids,
  deterministic fingerprints, immutable snapshots, tamper detection, replay/checkpoint equivalence,
  and explicit end-of-data residual positions.

Phase 3 `ExecutionFillV2.reference_price` is the gross accounting basis. Its separately frozen adverse
friction is monetized exactly once as `slippage_cost`; the economic fill price is preserved upstream
and is not recomputed. This makes gross economic result minus attributed costs equal net result
without double-counting price friction.

## Fail-closed boundaries

The ledger rejects mixed v1/v2 facts, identity/version mismatches, off-grid values, stale effective
specifications, missing or incompatible costs, missing/wrong mark type, unverified settlement,
duplicate economic facts, chronology regression, checkpoint tampering, unsupported settlement or
funding, and unapproved BTC perpetual capability. It never infers settlement, mark, oracle, funding,
fees, tiers, multipliers, or margin from candles.

## Excluded / Phase 5 boundary

No strategy behavior, risk authorization, limit decisions, forced flatten, margin-call order,
liquidation fill, rollover execution, provider access, exchange access, or live/paper trading was
added. Phase 5 may consume immutable `margin_breach` and residual-position facts to decide risk and
session actions; it must not mutate Phase 4 history or treat a breach as an accounting liquidation.

Core v1 and Phases 1-3 behavior remain unchanged.
