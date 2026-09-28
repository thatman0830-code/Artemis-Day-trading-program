---
title: Trading Brain — Canonical Specification
status: READY_FOR_IMPLEMENTATION
type: master-navigation
appendix_a_modified: false
---

# Trading Brain — Canonical Specification

## Status

**READY_FOR_IMPLEMENTATION**

## Governing Principle

The canonical Trading Brain specification is a deterministic, source-preserving implementation contract. No primitive may redefine another primitive's ownership. Links in this vault are **navigational, not ownership**.

## Source Precedence

See [[Trading Brain — Source Precedence]].

1. Owner Resolution Amendments 001–007
2. Later explicit owner-supplied locked definitions
3. Canonical implementation specification
4. Appendix A / recovered historical transcript (immutable)

## Canonical Dependency Graph

See [[Trading Brain — Dependency Graph]].

## Primitive Registry

See [[Trading Brain — Primitive Registry]].

## Implementation Readiness

See [[Trading Brain — Implementation Readiness]].

## Architecture (canonical order)

```
Market Data
→ #19 Mechanical Swing Selection
→ #20 Structural Classification
→ #16 Conflict Resolution / State Priority
→ #21 Active Dealing Range
→ #22 OTE
→ #23 Liquidity / Sweeps
→ #24 LRL Selection
→ #25 FVG / IFVG
→ #26 Confluence
→ #27 Setup Qualification
→ #28 Entry-Zone Selection
→ #13 Stop-Loss Selection
→ #29.0 Execution Eligibility / Trade Authorization
→ #29.1 Entry Execution
→ #29.2 Position Sizing
→ #29.3 Protective Orders
→ #29.4 Exit Resolution
→ #29.5 Execution Costs
→ #29.6 Position Lifecycle
→ #29.7.1 Trade Accounting
→ #29.7.2.1–.14 Analytical Primitives
→ #29.7.2.15 Strategy Aggregation
→ #29.7.2.16 Portfolio Aggregation
→ #29.7.2.17 Attribution
→ #29.7.2.18 Overlap
→ #29.7.2.19 Correlation
→ #29.7.2.20 Covariance
```

## Market Primitives
- [[#11 CISD — 1M Confirmation]]
- [[#13 Stop-Loss Selection]]
- [[#16 Conflict Resolution — State Priority]]
- [[#19 Mechanical Swing Selection]]
- [[#20 Structural Classification]]
- [[#21 Active Dealing Range]]
- [[#22 OTE]]
- [[#23 Liquidity — Sweeps]]
- [[#24 LRL Selection]]
- [[#25 FVG — IFVG]]
- [[#26 Confluence]]

## Setup Engine
- [[#27 Setup Qualification]]
- [[#28 Entry-Zone Selection]]

## Execution
- [[#29.0 Execution Eligibility]] · [[#29.1 Entry Execution]] · [[#29.2 Position Sizing]] · [[#29.3 Protective Orders]] · [[#29.4 Exit Resolution]] · [[#29.5 Execution Costs]] · [[#29.6 Position Lifecycle]] · [[#29.7.1 Trade Accounting]]
- Data contract: [[Execution Entity Hierarchy]] · EOD review: [[Execution Quality EOD Metrics]]

## Analytics
- [[#29.7.2 Ownership — Scope]]
- [[#29.7.2.1 Trade Classification — Count]] · [[#29.7.2.2 Return Statistics]] · [[#29.7.2.3 Expectancy]] · [[#29.7.2.4 Profit Factor]] · [[#29.7.2.5 Cumulative PnL — R]] · [[#29.7.2.6 Equity Curve]] · [[#29.7.2.7 Drawdown]] · [[#29.7.2.8 Streak Statistics]] · [[#29.7.2.9 Time-Series — Period Statistics]] · [[#29.7.2.10 Distribution Statistics]] · [[#29.7.2.11 Risk-Adjusted Statistics]] · [[#29.7.2.12 Recovery]] · [[#29.7.2.13 Underwater — Time Underwater]] · [[#29.7.2.14 Trade Sequence — Path]] · [[#29.7.2.15 Strategy-Level Aggregation]] · [[#29.7.2.16 Portfolio-Level Aggregation]] · [[#29.7.2.17 Portfolio Attribution]] · [[#29.7.2.18 Strategy Interaction — Overlap]] · [[#29.7.2.19 Strategy Return Correlation]] · [[#29.7.2.20 Strategy Return Covariance]]

## Supporting Registries
- [[Canonical Object Registry]] · [[StrategyPeriodReturnObservation]] · [[Canonical Enum Registry]] · [[Canonical Error Registry]] · [[Hard Invariants]] · [[Runtime Configuration Registry]]

## Amendments
- [[Amendment 001]] · [[Amendment 002]] · [[Amendment 003]] · [[Amendment 004]] · [[Amendment 005A]] · [[Amendment 006]] · [[Amendment 007]]

## External Research
- [[Polymarket Bot Execution and Inventory Management Analysis]] — reference-only rationale; not a source of mechanical truth.

## Immutable Historical Source
- [[Appendix A — Recovered Historical Transcript]]
