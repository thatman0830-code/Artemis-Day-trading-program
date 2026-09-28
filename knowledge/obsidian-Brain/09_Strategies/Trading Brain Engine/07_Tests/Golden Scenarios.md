---
title: Golden Scenarios
type: test-spec
---

# Golden Scenarios

Exact scenarios (test specification, not code).

## Structure / Market
- strict mechanical swing comparison; equal-high / equal-low exclusion — [[#19 Mechanical Swing Selection]]
- protected-swing body-close break — [[#20 Structural Classification]]
- range replacement produces new RangeID; MSS termination → TRANSITION; invalid range geometry → ACTIVE_RANGE_INVALID — [[#21 Active Dealing Range]]
- liquidity sweep vs touch; sweep + displacement + MSS same candle; MSS vs BOS priority — [[#23 Liquidity — Sweeps]] · [[#16 Conflict Resolution — State Priority]]
- FVG geometry; boundary touching not confluence — [[#25 FVG — IFVG]] · [[#26 Confluence]]
- OTE geometry (0.50–0.79 of active range) — [[#22 OTE]]

## Setup / Execution
- continuation stop (protected swing ± tick); reversal sweep-extreme stop — [[#13 Stop-Loss Selection]]
- 2R rejection (no farther target) — [[#24 LRL Selection]] · [[#27 Setup Qualification]]
- EQ fill / no-fill; selected-zone invalid fallback; no future zone rescue — [[#28 Entry-Zone Selection]] · [[#29.1 Entry Execution]]
- gap-through long; gap-through short; target gap; same-candle SL/TP ambiguity — [[#29.4 Exit Resolution]]
- one-position rule — [[#29.6 Position Lifecycle]]
- long/short WIN/LOSS accounting; zero-cost trade; break-even trade — [[#29.7.1 Trade Accounting]]

## CISD (#11)
- bullish strict body close > bearish delivery open → TRUE; equality → FALSE; wick-only → FALSE
- bearish strict body close < bullish delivery open → TRUE; equality → FALSE; wick-only → FALSE
- pre-MSS CISD cannot confirm; pre-sweep CISD cannot confirm
- same-candle MSS+CISD valid when both independently qualify vs frozen pre-state
- delivery candle must be the initiating candle of the immediately preceding opposing delivery leg; arbitrary older opposing candle cannot substitute
- missing valid delivery reference → NOT_CONFIRMABLE; confirmation creates no entry; confirmation opens #28 eligibility only

## Analytics
- duplicate trade fail-closed (DATA_INTEGRITY_ERROR) — [[#29.7.2.14 Trade Sequence — Path]] · [[#29.7.2.15 Strategy-Level Aggregation]] · [[#29.7.2.16 Portfolio-Level Aggregation]] · [[#29.7.2.17 Portfolio Attribution]]
- no-trade period vs missing period — [[#29.7.2.9 Time-Series — Period Statistics]]
- correlation / covariance constant series; correlation n<2; covariance n<2 — [[#29.7.2.19 Strategy Return Correlation]] · [[#29.7.2.20 Strategy Return Covariance]]
- portfolio conservation; strategy attribution conservation; merged-chronology drawdown — [[#29.7.2.16 Portfolio-Level Aggregation]] · [[#29.7.2.17 Portfolio Attribution]]

See [[Hard Invariants]], [[Primitive Test Matrix]].
