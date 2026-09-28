---
title: Amendment 002
status: ACTIVE
precedence: OWNER_RESOLUTION
appendix_modified: false
resolves: [R1, R2, R3]
---

# Owner Resolution Amendment 002

Resolves R1 (Time/Period), R2 (Identity/Versioning), R3 (Precision). Precedence tier 1. Appendix A unmodified.

## R1 — Time / Period Policy
See [[Time — Period Policy]].
- `AccountTimezone` mandatory.
- Period assignment uses `TradeAccounting.closed_time`.
- Periods: `DAILY`, `WEEKLY` (Monday–Sunday, ISO week), `MONTHLY`, `FULL_HISTORY`.
- Intervals are `[start, end)` in AccountTimezone.
- **No-trade period:** record exists, `trade_count = 0`, additive P&L/R totals `= 0`, undefined ratios/statistics `= NULL`.
- **Missing period:** no record.
- Sessions are **not** accounting boundaries.

## R2 — Identity / Versioning Policy
See [[Identity — Versioning Policy]].
- IDs are opaque and immutable.
- Finalized records are append-only.
- Versioning fields: `source_version`, `calculation_version`, `historical_version`.
- Correction lineage is authoritative; analytics may not choose authoritative versions themselves.
- A superseded prior record version is **not** a duplicate when version semantics make only one version authoritative.
- `portfolio_id + portfolio_version` identifies the exact portfolio definition.

## R3 — Precision / Rounding Policy
See [[Precision — Rounding Policy]].
- Deterministic decimal arithmetic; no binary-float dependence.
- ≥ 28 significant digits computation precision.
- No calculation from rounded display values.
- `NULL != 0`. Exact zero remains exact zero.
- EQ normalization: `EQ_raw = (ZoneHigh + ZoneLow) / 2`, normalized to `minimum_tick` via **ROUND HALF UP**.
- Quantity floored to the legal increment.
- Statistical equality/invariants evaluated at canonical computation precision.

Affected: all execution and analytics primitives; especially [[#28 Entry-Zone Selection]], [[#29.2 Position Sizing]], [[#29.7.1 Trade Accounting]], [[#29.7.2.15 Strategy-Level Aggregation]].
