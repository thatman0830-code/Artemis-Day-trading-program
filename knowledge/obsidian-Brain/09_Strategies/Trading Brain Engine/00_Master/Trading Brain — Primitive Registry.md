---
title: Trading Brain — Primitive Registry
type: master-registry
verdict: READY_FOR_IMPLEMENTATION
appendix_a_modified: false
---

# Trading Brain — Primitive Registry

Verdict: **READY_FOR_IMPLEMENTATION**. No analytics primitive remains missing. No `ACTIVE_CANONICAL_CONFLICT`.

| ID | Title | Status | Upstream | Downstream |
|----|-------|--------|----------|------------|
| #19 | Mechanical Swing Selection | LOCKED_AND_IMPLEMENTABLE | Market data | #20 |
| #20 | Structural Classification | LOCKED_AND_IMPLEMENTABLE | #19 | #16, #21, #24 |
| #16 | Conflict Resolution / State Priority | LOCKED_AND_IMPLEMENTABLE | #19,#20,#23 candidates | #21, setup |
| #21 | Active Dealing Range | LOCKED_AND_IMPLEMENTABLE | #20 (+#16) | #22, #23, #24 |
| #22 | OTE | LOCKED_AND_IMPLEMENTABLE | #21 | #26, #28 |
| #23 | Liquidity / Sweeps | LOCKED_AND_IMPLEMENTABLE | #19,#20,#21 | #24, #16 |
| #24 | LRL Selection | LOCKED_AND_IMPLEMENTABLE | #23,#21,#20 | #27 (target) |
| #25 | FVG / IFVG | LOCKED_AND_IMPLEMENTABLE | price | #26, #28 |
| #26 | Confluence | LOCKED_AND_IMPLEMENTABLE | #22,#23,#24,#25,MSS | #27 |
| #27 | Setup Qualification | LOCKED_AND_IMPLEMENTABLE | #26,#24, #11(rev) | #28, arm |
| #28 | Entry-Zone Selection | LOCKED_AND_IMPLEMENTABLE | #27,#25,#11(rev) | #13, #29.1 |
| #13 | Stop-Loss Selection | LOCKED_AND_IMPLEMENTABLE | #20/#23, #28 | #27(≥2R), #29.2, #29.3 |
| #11 | CISD / 1M Confirmation | LOCKED_AND_IMPLEMENTABLE | #16 MSS_CONFIRMED | #28 (reversal) |
| #29.0 | Execution Eligibility / Trade Authorization | **LOCKED_CONFIGURATION_REQUIRED** (execution estimates) | #27,#28,#13,#24 | #29.1 |
| #29.1 | Entry Execution | LOCKED_AND_IMPLEMENTABLE | #28 EQ | #29.2, #29.6 |
| #29.2 | Position Sizing | **LOCKED_CONFIGURATION_REQUIRED** (RiskPercent) | #13,#29.1 | #29.3, #29.7.1 |
| #29.3 | Protective Orders | LOCKED_AND_IMPLEMENTABLE | #13,#24,#29.2 | #29.4 |
| #29.4 | Exit Resolution | LOCKED_AND_IMPLEMENTABLE | #29.3 | #29.5, #29.6 |
| #29.5 | Execution Costs | **LOCKED_CONFIGURATION_REQUIRED** (cost model) | #29.4 | #29.7.1 |
| #29.6 | Position Lifecycle | LOCKED_AND_IMPLEMENTABLE | #29.1,#29.4 | #29.7.1 |
| #29.7.1 | Trade Accounting | LOCKED_AND_IMPLEMENTABLE | #29.5,#29.6 | #29.7.2.* |
| #29.7.2 | Performance (parent) | LOCKED_AND_IMPLEMENTABLE | #29.7.1 | .1–.20 |
| #29.7.2.1–.13 | Atomic analytics | LOCKED_AND_IMPLEMENTABLE | #29.7.1 | .14–.20 |
| #29.7.2.14 | Trade Sequence / Path | LOCKED_AND_IMPLEMENTABLE | #29.7.1,.8 | .15,.16 |
| #29.7.2.15 | Strategy-Level Aggregation | LOCKED_AND_IMPLEMENTABLE | #29.7.1,.9 | .16,.17,.19,.20 |
| #29.7.2.16 | Portfolio-Level Aggregation | LOCKED_AND_IMPLEMENTABLE | .15 pop. | .17 |
| #29.7.2.17 | Portfolio Attribution | LOCKED_AND_IMPLEMENTABLE | .16 | — |
| #29.7.2.18 | Strategy Interaction / Overlap | LOCKED_AND_IMPLEMENTABLE | trades | — |
| #29.7.2.19 | Strategy Return Correlation | LOCKED_AND_IMPLEMENTABLE | .15 net_r | — |
| #29.7.2.20 | Strategy Return Covariance | LOCKED_AND_IMPLEMENTABLE | .15 net_r | — |

Configuration dependencies are runtime values, not missing logic — see [[Runtime Configuration Registry]] and [[Configuration vs Logic Boundary]].

Owner for every primitive is the primitive itself; ownership boundaries are stated in each note. Related: [[Trading Brain — Implementation Readiness]].

Supporting non-numbered contracts: [[Execution Entity Hierarchy]] · [[Execution Quality EOD Metrics]].
