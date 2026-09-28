# V2 Phase 7 Reporting and Validation Implementation

Phase 7 adds deterministic, read-only reporting downstream of finalized V2 facts.
It reconciles content-addressed lineage across contracts, orders, execution,
accounting, risk, sessions, rollover, and funding. It computes exact Decimal net
performance after separately attributed commission, fees, slippage, signed
funding, settlement cost, rollover friction, and versioned infrastructure cost.

Metrics include expectancy, profit factor, average win/loss, sample Sharpe,
downside Sortino, maximum drawdown, recovery trades, exposure, turnover, and tail
loss. Immutable point-in-time regime labels cover volatility, trend, liquidity,
and session dimensions without changing trade outcomes. Deterministic stress
records cover clustered loss, gaps, slippage, funding, rollover, degradation, and
explicit-path empirical probability of ruin.

Training, validation, untouched OOS, forward-recorded, paper, and live partitions
cannot be blended for promotion. Promotion is advisory, fail-closed, requires a
complete reconciliation, positive net expectancy and economic hurdles, planned
R:R >= 1 for every trade, and at least 200 finalized untouched-OOS trades per
market. These analytics do not guarantee profitability or authorize trading.

Final acceptance hardening makes the 200-trade floor non-lowerable, validates an
immutable cross-partition registry against relabeling and chronological overlap,
and fails promotion when explicitly required stress or ruin evidence is absent.

Unsupported: SPX/options, provider/runtime access, portfolio mutation, parameter
optimization, strategy changes, order creation, submission, and live promotion.
