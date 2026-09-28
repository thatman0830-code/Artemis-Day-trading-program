---
title: Trading Brain — Dependency Graph
type: master-navigation
appendix_a_modified: false
---

# Trading Brain — Dependency Graph

Links are navigational. Ownership is one-directional and defined inside each primitive note.

## Canonical Main Chain

```
MARKET DATA
  ↓
#19 Mechanical Swing Selection
  ↓
#20 Structural Classification
  ↓
#16 Conflict Resolution / State Priority
  ↓
#21 Active Dealing Range
  ↓
#22 OTE
  ↓
#23 Liquidity / Sweeps
  ↓
#24 LRL Selection
  ↓
#25 FVG / IFVG
  ↓
#26 Confluence
  ↓
#27 Setup Qualification
  ↓
#28 Entry-Zone Selection
  ↓
#13 Stop-Loss Selection
  ↓
#29.0 Execution Eligibility / Trade Authorization
  ↓
#29.1 Entry Execution
  ↓
#29.2 Position Sizing
  ↓
#29.3 Protective Orders
  ↓
#29.4 Exit Resolution
  ↓
#29.5 Execution Costs
  ↓
#29.6 Position Lifecycle
  ↓
#29.7.1 Trade Accounting
  ↓
#29.7.2.1–.14 Analytical Primitives
  ↓
#29.7.2.15 Strategy Aggregation
  ↓
#29.7.2.16 Portfolio Aggregation
  ↓
#29.7.2.17 Attribution
  ↓
#29.7.2.18 Overlap
  ↓
#29.7.2.19 Correlation
  ↓
#29.7.2.20 Covariance
```

## Reversal #1 Subgraph

```
Existing regime
  ↓
REVERSAL_SWEEP_REFERENCE   (bearish regime → LSL ; bullish regime → BSL)  [Amendment 005A]
  ↓
LRL sweep (#23/#24)
  ↓
Counter-directional displacement
  ↓
Protected-swing break (#20)
  ↓
#16 accepted MSS
  ↓
MSS_CONFIRMED
  ↓
#11 CISD (1M strict body close through relevant opposing delivery OPEN)
  ↓
CISD_CONFIRMED
  ↓
post-confirmation 1M FVG/IFVG universe
  ↓
#28 Entry-Zone Selection
  ↓
#13 Stop-Loss Selection (reversal = sweep/reversal extreme ± 1 tick)
  ↓
execution eligibility and authorization (#29.0)
  ↓
execution (#29.1 → #29.7.1)
```

## Continuation Subgraph

```
BULLISH / BEARISH regime (#20)
  ↓
protected swing (#20)
  ↓
active range (#21)
  ↓
5M OTE (#22)     (OTE = inclusive 0.50–0.79 of the active dealing range)
  ↓
5M FVG/IFVG confluence (#25/#26)
  ↓
1M confirmation
  ↓
#28 Entry-Zone Selection
  ↓
#13 Stop-Loss Selection (continuation = protected structural swing ± 1 tick)
  ↓
≥2R validation (#27 owns; target = #24 LRL)
  ↓
execution eligibility and authorization (#29.0)
  ↓
execution (#29.1 → #29.7.1)

## Execution Entity Flow

```text
Setup (#27) → eligibility evaluation / Trade authorization (#29.0)
→ Order / Fill (#29.1) → Position (#29.6) → accounting (#29.7.1)
→ execution-quality review
```

See [[Execution Entity Hierarchy]] and [[Execution Quality EOD Metrics]].
```

Related: [[Trading Brain — Canonical Specification]] · [[Trading Brain — Primitive Registry]]
