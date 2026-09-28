---
title: Property Tests
type: test-spec
---

# Property Tests

Property-based invariants (must hold for all valid inputs). Test specification only.

## Conservation
- `TradeCount = Wins + Losses + Breakevens` (per strategy and per portfolio)
- `StrategyNetPnL = Σ Trade.NetPnL`; `PortfolioNetPnL = Σ Trade.NetPnL`
- `Σ StrategyContributionPnL = PortfolioNetPnL`; `Σ StrategyContributionR = PortfolioNetR`
- `Σ StrategyTradeCount = PortfolioTradeCount`
- Attribution: `Σ Strategy Contribution = Portfolio Result`
- Sequence: `Σ run lengths = N`; `Σ transition counts = max(N−1,0)`

## Monotonic / Ordering
- canonical ordering `closed_time ASC, trade_id ASC` is deterministic and reproducible
- point-in-time: `Stats(T)` uses only records with `closed_time`/`period_end <= T`

## Equity / Path
- `Equity_t = StartingEquity + CumulativeNetPnL_t` (strategy & portfolio)
- portfolio path-dependent metrics equal those recomputed from the merged chronological population (never from combined strategy stats)

## Numeric
- decimal precision ≥ 28 significant digits; no display-value calculation
- `NULL ≠ 0`; exact zero preserved; sample statistics use (N−1); `n<2 → NULL`
- missing ≠ zero across all period-aligned consumers

## Integrity
- any duplicate canonical uniqueness key → `DATA_INTEGRITY_ERROR`, `affected_calculation_valid = FALSE`, no finalized snapshot
- immutability: appending later trades never mutates prior finalized observations

See [[Hard Invariants]], [[Primitive Test Matrix]], [[Golden Scenarios]].
