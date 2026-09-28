---
title: StrategyPeriodReturnObservation
type: canonical-object
governing_amendments: [001-C3, 002-R1, 002-R2, 002-R3]
produced_by: "#29.7.2.15"
consumed_by: ["#29.7.2.19", "#29.7.2.20"]
---

# StrategyPeriodReturnObservation

Canonical schema (Amendment 001 C3). This is the **single** canonical strategy-period return object. No old `{timestamp, return_value}` schema may be restored.

```
StrategyPeriodReturnObservation {
    id
    strategy_id
    period_type
    period_id
    period_start
    period_end

    net_pnl
    net_r

    trade_count

    finalized
    finalized_time

    source_version
}
```

## Rules
- **Produced by** [[#29.7.2.15 Strategy-Level Aggregation]].
- Period rules owned by [[#29.7.2.9 Time-Series — Period Statistics]] + Amendment 002 R1 ([[Time — Period Policy]]).
- `net_r = Σ finalized Trade.NetR within the strategy-period`.
- **Do not** derive `net_r` by dividing aggregate P&L by an arbitrary aggregate risk.
- A **no-trade period** may exist with `net_r = 0` and `trade_count = 0`.
- A **missing period** = no record. **Missing ≠ zero.**
- A finalized `net_r = 0` is a valid real observation.
- [[#29.7.2.19 Strategy Return Correlation]] and [[#29.7.2.20 Strategy Return Covariance]] consume the **same aligned population**, keyed by `period_end`.
- Point-in-time eligibility: `period_end <= T`.

Related: [[Amendment 001]], [[Amendment 002]], [[Canonical Object Registry]].
