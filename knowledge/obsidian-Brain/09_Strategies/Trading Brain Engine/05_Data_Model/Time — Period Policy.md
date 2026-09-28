---
title: Time — Period Policy
governing_amendments: ["002-R1"]
---

# Time / Period Policy (Amendment 002 R1)

- **AccountTimezone** is mandatory (a runtime configuration value — see [[Runtime Configuration Registry]]).
- Period assignment uses `TradeAccounting.closed_time`.
- Period types: `DAILY`, `WEEKLY` (Monday–Sunday, ISO week), `MONTHLY`, `FULL_HISTORY`.
- Intervals are half-open `[start, end)` in AccountTimezone.
- **No-trade period:** a record **exists** with `trade_count = 0`, additive P&L/R totals `= 0`, undefined ratios/statistics `= NULL`.
- **Missing period:** **no record**. (No-trade ≠ missing; missing ≠ zero.)
- **Sessions are not accounting boundaries.**

Consumed by [[#29.7.2.9 Time-Series — Period Statistics]], [[#29.7.2.15 Strategy-Level Aggregation]], [[#29.7.2.16 Portfolio-Level Aggregation]], and via [[StrategyPeriodReturnObservation]] by [[#29.7.2.19 Strategy Return Correlation]] / [[#29.7.2.20 Strategy Return Covariance]].

See [[Amendment 002]].
