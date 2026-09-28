---
title: Amendment 001
status: ACTIVE
precedence: OWNER_RESOLUTION
appendix_modified: false
resolves: [C1, C2, C3]
---

# Owner Resolution Amendment 001

Resolves conflicts C1, C2, C3. Precedence tier 1. Appendix A unmodified.

## C1 — Canonical Analytics Numbering (frozen registry)

The canonical analytics registry governs. Frozen numbering:

```
#29.7.2.9  = Time-Series / Period Statistics
#29.7.2.10 = Distribution
#29.7.2.11 = Risk-Adjusted
#29.7.2.12 = Recovery
#29.7.2.13 = Underwater
#29.7.2.14 = Trade Sequence / Path
#29.7.2.15 = Strategy Aggregation
#29.7.2.16 = Portfolio Aggregation
#29.7.2.17 = Attribution
#29.7.2.18 = Overlap
#29.7.2.19 = Correlation
#29.7.2.20 = Covariance
```

Any older internal numbering recap inside supplied source text is historical wording and does **not** renumber the registry. Conflicting recaps are stamped `SUPERSEDED_BY_AMENDMENT_001_C1` (notably the `#29.7.2.15` §39 recap).

## C2 — Global Fail-Closed Duplicate Policy

```
duplicate canonical uniqueness key within one authoritative source_version
  → DATA_INTEGRITY_ERROR
  → dataset_status = DATA_INTEGRITY_ERROR
  → affected_calculation_valid = FALSE
  → no finalized analytical snapshot produced
```

No silent deduplication. No "retain canonical duplicate and continue." No averaging. No arbitrary record selection. Supersedes `#29.7.2.14` exclude-and-continue and `#29.7.2.17` retain-and-continue wording. `#29.7.2.16` reject-ambiguous-dataset behavior is consistent with C2. See [[Error Precedence — Fail Closed]].

## C3 — Canonical StrategyPeriodReturnObservation

See [[StrategyPeriodReturnObservation]]. Both `#29.7.2.19` Correlation and `#29.7.2.20` Covariance consume **period-aligned `net_r`**. Point-in-time eligibility uses `period_end <= T`. **Missing ≠ zero.** A valid finalized `net_r = 0` is a real observation. No old `{timestamp, return_value}` schema may be restored.

Affected primitives: [[#29.7.2.14 Trade Sequence — Path]], [[#29.7.2.15 Strategy-Level Aggregation]], [[#29.7.2.16 Portfolio-Level Aggregation]], [[#29.7.2.17 Portfolio Attribution]], [[#29.7.2.19 Strategy Return Correlation]], [[#29.7.2.20 Strategy Return Covariance]].
