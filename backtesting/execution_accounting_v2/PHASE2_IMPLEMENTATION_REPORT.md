# V2 Phase 2 Order Ledger Implementation Report

Phase 2 implements a pure, immutable, append-only lifecycle ledger. `apply()` returns a new ledger;
the prior ledger and every order intent, event, transition, and snapshot remain unchanged. Exact
duplicate event ingestion returns the same ledger. Conflicting event-ID reuse fails closed.

Implemented lifecycle facts include submit, forced-close intent, accept/reject, activation, stop
trigger, candidate partial/final fill ingestion, cancel request/cancel, DAY/GTC expiry, IOC evaluation,
replacement, and terminal rejection. Replacement creates a linked child and never edits the parent.

The ledger validates candidate fill quantities and lifecycle eligibility but does not inspect OHLC,
decide a touch, choose a price, generate a fill, calculate costs/PnL/margin, liquidate a position, or
perform strategy logic. `intrabar_owner` is metadata only. The frozen adverse-collision policy remains
owned by Phase 3.

End-of-data validation rejects every nonterminal residual with `END_OF_DATA_RESIDUAL`. No fill or
accounting liquidation is created. Core v1 is unchanged.

The exact Phase 3 boundary is a separate conservative OHLC execution component that may propose
eligible fill events under `CONSERVATIVE_OHLC_1M_V1`. It must consume this ledger and Phase 1 facts;
it may not mutate ledger history or implement accounting, margin, funding, or live execution.
