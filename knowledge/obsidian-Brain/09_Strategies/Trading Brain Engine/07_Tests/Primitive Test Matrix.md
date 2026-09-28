---
title: Primitive Test Matrix
type: test-spec
---

# Primitive Test Matrix

Each primitive maps to: **unit**, **state-transition**, **integrity**, **no-look-ahead**, **immutability**, **property**, **golden** tests. Test specification only (no executable code yet).

| Primitive | Unit | State | Integrity | No-look-ahead | Immutability | Golden |
|---|---|---|---|---|---|---|
| [[#19 Mechanical Swing Selection]] | ✓ | — | ✓ | ✓ | ✓ | strict/equal exclusion |
| [[#20 Structural Classification]] | ✓ | ✓ | ✓ | ✓ | ✓ | body-close break |
| [[#21 Active Dealing Range]] | ✓ | ✓ | ✓ | ✓ | ✓ | replacement/TRANSITION/invalid |
| [[#22 OTE]] | ✓ | — | ✓ | ✓ | — | OTE geometry |
| [[#23 Liquidity — Sweeps]] | ✓ | ✓ | ✓ | ✓ | ✓ | sweep vs touch |
| [[#24 LRL Selection]] | ✓ | ✓ | ✓ | ✓ | ✓ | 2R rejection |
| [[#25 FVG — IFVG]] | ✓ | ✓ | ✓ | ✓ | ✓ | FVG geometry |
| [[#26 Confluence]] | ✓ | — | ✓ | ✓ | — | boundary ≠ confluence |
| [[#16 Conflict Resolution — State Priority]] | ✓ | ✓ | ✓ | ✓ | ✓ | MSS>BOS; same-candle coexist |
| [[#27 Setup Qualification]] | ✓ | ✓ | ✓ | ✓ | ✓ | 2R reject; fallback |
| [[#28 Entry-Zone Selection]] | ✓ | ✓ | ✓ | ✓ | ✓ | EQ; no future rescue |
| [[#13 Stop-Loss Selection]] | ✓ | — | ✓ | — | ✓ | cont/rev stop |
| [[#11 CISD — 1M Confirmation]] | ✓ | ✓ | ✓ | ✓ | ✓ | 18 CISD rows (Golden) |
| [[#29.0 Execution Eligibility]] | ✓ | ✓ | ✓ | ✓ | ✓ | executable-R pass/fail; revoke; unknown data |
| [[#29.1 Entry Execution]] | ✓ | ✓ | ✓ | ✓ | ✓ | EQ fill/no-fill |
| [[#29.2 Position Sizing]] | ✓ | — | ✓ | — | ✓ | quantity rounding |
| [[#29.3 Protective Orders]] | ✓ | ✓ | ✓ | — | ✓ | OCO cancel |
| [[#29.4 Exit Resolution]] | ✓ | ✓ | ✓ | ✓ | ✓ | gap/target/ambiguity |
| [[#29.5 Execution Costs]] | ✓ | — | ✓ | — | ✓ | no double-count |
| [[#29.6 Position Lifecycle]] | ✓ | ✓ | ✓ | ✓ | ✓ | one-position |
| [[Execution Entity Hierarchy]] | ✓ | ✓ | ✓ | — | ✓ | multi-fill reconciliation; no double-count |
| [[Execution Quality EOD Metrics]] | ✓ | — | ✓ | ✓ | ✓ | slippage sign; missing ≠ zero |
| [[#29.7.1 Trade Accounting]] | ✓ | — | ✓ | ✓ | ✓ | WIN/LOSS/BE/zero-cost |
| [[#29.7.2.14 Trade Sequence — Path]] | ✓ | ✓ | ✓ | ✓ | ✓ | 11 rows |
| [[#29.7.2.15 Strategy-Level Aggregation]] | ✓ | — | ✓ | ✓ | ✓ | 16 rows |
| [[#29.7.2.16 Portfolio-Level Aggregation]] | ✓ | — | ✓ | ✓ | ✓ | 21 rows |
| [[#29.7.2.17 Portfolio Attribution]] | ✓ | — | ✓ | ✓ | ✓ | conservation |
| [[#29.7.2.18 Strategy Interaction — Overlap]] | ✓ | — | ✓ | ✓ | ✓ | union not sum |
| [[#29.7.2.19 Strategy Return Correlation]] | ✓ | — | ✓ | ✓ | ✓ | constant; n<2 |
| [[#29.7.2.20 Strategy Return Covariance]] | ✓ | — | ✓ | ✓ | ✓ | constant; n<2 |

Analytics primitives .1–.13 inherit the parent [[#29.7.2 Ownership — Scope]] test scope. See [[Hard Invariants]], [[Golden Scenarios]], [[Property Tests]].
