# Implementation Phases

1. **Contracts and validation** — frozen records, schema validation, identity hashing, capability
   checks, and rejection catalogs. No fills.
2. **Order ledger** — intent acceptance, lifecycle transitions, cancellation, expiry, replacement,
   and deterministic event priority. No economic accounting.
3. **OHLC execution** — `CONSERVATIVE_OHLC_1M_V1`, partial fills, participation budgets, collision
   handling, and fill lineage.
4. **Instrument accounting** — ES/NQ futures first; BTC only after an explicit instrument profile.
   Cash, margin, fees, realized/unrealized PnL, and reconciliation snapshots.
5. **Risk and sessions** — pre/post-trade controls, session flatten, stale/gapped data halts, forced
   actions through ordinary orders.
6. **Rollover and funding** — close-then-open futures rollover; perpetual funding only when supported.
7. **Reporting and validation** — attribution, robustness facts, fingerprints, deterministic replay,
   and adversarial suites.

Each phase is separately gated. Later phases cannot substitute facts missing from an earlier phase.
No phase adds provider access, archive mutation, recorder control, brokerage, or live execution.
