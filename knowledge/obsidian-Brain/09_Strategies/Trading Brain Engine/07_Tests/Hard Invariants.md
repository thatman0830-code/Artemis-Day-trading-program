---
title: Hard Invariants
type: test-spec
---

# Hard Invariants (cross-cutting)

Executable test specification (no test code yet).

| # | Invariant | Owner |
|---|---|---|
| I1 | Swing requires strict `>`/`<`; equal highs/lows excluded | [[#19 Mechanical Swing Selection]] |
| I2 | Structure breaks only on candle **body** close beyond protected swing | [[#20 Structural Classification]] |
| I3 | `UpperBoundary > LowerBoundary`; range from protected/structural swings; new RangeID on replacement | [[#21 Active Dealing Range]] |
| I4 | OTE = inclusive 0.50–0.79 of active range; 0.50 = midpoint; consumes #21 boundaries | [[#22 OTE]] |
| I5 | Sweep ⇔ penetration **+ close back across**; touch ≠ sweep; internal sweep never mutates range/regime | [[#23 Liquidity — Sweeps]] |
| I6 | LRL External > Internal absolute; CONSUMED ineligible; no per-candle reselect; ≥2R gate no farther target | [[#24 LRL Selection]] |
| I7 | REVERSAL_SWEEP_REFERENCE = LSL(bear→bull)/BSL(bull→bear); continuation target unchanged | [[Amendment 005A]] |
| I8 | IFVG = one-time inversion; no arbitrary 50% mitigation | [[#25 FVG — IFVG]] |
| I9 | #26 facts only; never arms/rejects/triggers/executes | [[#26 Confluence]] |
| I10 | #28 runs at eligible state (not ARMED); freezes candidate set; no future-zone rescue | [[#28 Entry-Zone Selection]] |
| I11 | EQ = (ZoneHigh+ZoneLow)/2 ROUND HALF UP to minimum_tick | [[Precision — Rounding Policy]] |
| I12 | ≥2R decision owned by #27 after one zone selected | [[#27 Setup Qualification]] |
| I13 | #11 strict body close through relevant opposing delivery OPEN; equality/wick fail; CISD ≠ MSS ≠ displacement | [[#11 CISD — 1M Confirmation]] |
| I14 | #16 candidate eval vs frozen StateBefore(t); MSS > same-direction BOS; timeframes isolated; suppressed events immutable | [[#16 Conflict Resolution — State Priority]] |
| I15 | Continuation stop = protected swing ± tick; reversal stop = sweep extreme ± tick; StopPrice immutable ≠ ExitPrice | [[#13 Stop-Loss Selection]] |
| I16 | Entry limit at frozen EQ; no touch → no fill; one live position | [[#29.1 Entry Execution]] · [[#29.6 Position Lifecycle]] |
| I17 | Normal stop ExitPrice = StopPrice; gap ExitPrice = FirstObservablePrice; target gap = TargetPrice; gap-stop precedence | [[#29.4 Exit Resolution]] |
| I18 | GrossPnL/NetPnL/R/PostTradeEquity exact; decimal ≥28 digits; exact-zero breakeven; ActualRisk>0 | [[#29.7.1 Trade Accounting]] |
| I19 | Cost anti-double-count: friction in economic prices not re-charged as cash cost | [[#29.5 Execution Costs]] |
| I20 | Attribution conservation Σ Strategy = Portfolio; overlap `[opened,closed)` union not sum | [[#29.7.2.17 Portfolio Attribution]] · [[#29.7.2.18 Strategy Interaction — Overlap]] |
| I21 | Correlation/Covariance sample (N−1); missing ≠ zero; NULL ≠ 0; n<2 → NULL; net_r by period_end | [[#29.7.2.19 Strategy Return Correlation]] · [[#29.7.2.20 Strategy Return Covariance]] |
| I22 | Duplicate canonical key → DATA_INTEGRITY_ERROR fail-closed; no finalized snapshot | [[Error Precedence — Fail Closed]] |
| I23 | Period assignment = closed_time; `[start,end)`; no-trade ≠ missing | [[Time — Period Policy]] |
| I24 | No look-ahead / historical immutability across #11, .14, .15, .16, .17, .19, .20 | [[#29.7.2 Ownership — Scope]] |
| I25 | Portfolio path-dependent stats from merged chronology; no double aggregation | [[#29.7.2.16 Portfolio-Level Aggregation]] |
| I26 | #27 theoretical ≥2R setup gate and #29.0 executable ≥2R authorization gate both pass; failure of the latter does not invalidate the setup | [[#29.0 Execution Eligibility]] |
| I27 | Setup → Trade → Order → Fill identity is preserved; Position exposure/average price derives only from fills | [[Execution Entity Hierarchy]] · [[#29.6 Position Lifecycle]] |
| I28 | Unknown mandatory execution data fails closed; theoretical, expected executable, and actual prices remain distinct and immutable | [[#29.0 Execution Eligibility]] |
| I29 | Research-only concepts explicitly excluded by Amendment 007 never enter core rules | [[Amendment 007]] |

See [[Golden Scenarios]], [[Primitive Test Matrix]], [[Property Tests]].
