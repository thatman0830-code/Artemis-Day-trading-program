---
primitive_id: "#13"
title: Exact Mechanical Stop-Loss Selection
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["002-R3", "003", "005A"]
upstream: ["#20 protected swings", "#23 sweep extremes", "#28 selected zone"]
downstream: ["#27 (≥2R)", "#29.2 Position Sizing", "#29.3 Protective Orders"]
historical_source_preserved: true
implementation_ready: true
---

# #13 — Exact Mechanical Stop-Loss Selection

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns `StopPrice` selection only. Consumes structural references from [[#20 Structural Classification]] and sweep extremes from [[#23 Liquidity — Sweeps]]. Does not redefine any upstream structural primitive. `#29.3` constructs the protective order from the already-selected StopPrice; `#29.4` owns `ExitPrice` (`StopPrice != ExitPrice`); #13 never determines gap-through execution.

## Canonical Definition — Stop Mappings
| Model / side | Reference | StopPrice |
|---|---|---|
| CONTINUATION LONG | relevant protected structural low | `Reference − MinimumTick` |
| CONTINUATION SHORT | relevant protected structural high | `Reference + MinimumTick` |
| REVERSAL #1 LONG | lowest traded extreme of the qualifying **sell-side (LSL)** sweep/reversal event | `Reference − MinimumTick` |
| REVERSAL #1 SHORT | highest traded extreme of the qualifying **buy-side (BSL)** sweep/reversal event | `Reference + MinimumTick` |

Reversal mapping is consistent with [[Amendment 005A]] `REVERSAL_SWEEP_REFERENCE` (bearish→bullish references LSL; bullish→bearish references BSL).

## State / Lifecycle
`StopPrice` becomes fixed when selected and is **immutable** thereafter — no tightening, no widening, no stop manipulation to manufacture ≥2R. #27 consumes it for the ≥2R decision; #29.2 uses `|Entry − Stop|` for risk distance; #29.3 builds the protective order from the exact StopPrice.

## Hard Invariants
- long stop `< reference` and `< entry`
- short stop `> reference` and `> entry`
- absolute stop buffer = **exactly one MinimumTick**
- continuation stop derives from structural invalidation; reversal stop derives from the qualifying sweep/reversal extreme
- fixed StopPrice immutable (no tighten / widen / manipulate)
- missing required reference → `STOP_SELECTION_INVALID` / non-executable
- `StopPrice != ExitPrice`; #13 never determines gap-through execution
- tick-grid normalization per [[Precision — Rounding Policy]] (references are traded prices already on-grid)

## Dependencies
Upstream: [[#20 Structural Classification]], [[#23 Liquidity — Sweeps]], [[#28 Entry-Zone Selection]]. Downstream: [[#27 Setup Qualification]] (≥2R), [[#29.2 Position Sizing]], [[#29.3 Protective Orders]].

## Amendment Overrides
Reversal side per [[Amendment 005A]]. Precision per [[Amendment 002]] R3. `STOP_SELECTION_INVALID` registered per [[Amendment 003]] (owner-authorized addition).

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`StopSelection`) · [[Canonical Error Registry]] (`STOP_SELECTION_INVALID`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (continuation stop, reversal sweep-extreme stop).

## Historical Source
[[Appendix A — Recovered Historical Transcript]]
