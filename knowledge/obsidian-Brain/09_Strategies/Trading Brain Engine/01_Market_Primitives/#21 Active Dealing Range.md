---
primitive_id: "#21"
title: Exact Mechanical Active Dealing Range Boundary Constructor
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["003"]
upstream: ["#20 Structural State (+#16 accepted events)"]
downstream: ["#22 OTE", "#23", "#24"]
historical_source_preserved: true
implementation_ready: true
---

# #21 — Exact Mechanical Active Dealing Range Boundary Constructor

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
`#20 Structural State → #21 Active Dealing Range → #22 OTE Geometry`. #21 owns **only** the exact structural range boundaries and lifecycle. It does not detect swings, classify structure, create BOS/MSS, calculate OTE, detect liquidity, select LRL, create FVG/IFVG, or qualify setups.

## Canonical Range Construction
Confirmed structural wick extremes; require `UpperBoundary > LowerBoundary`.
- **BULLISH:** `LowerBoundary = governing ProtectedLow.low`; `UpperBoundary = governing StructuralHigh.high` (Protected Low → governing Structural High).
- **BEARISH:** `UpperBoundary = governing ProtectedHigh.high`; `LowerBoundary = governing StructuralLow.low` (Protected High → governing Structural Low).

## Range Initialization (enum reconciliation)
`#21 conceptual UNINITIALIZED ≡ StructuralRegime.INITIALIZING` (Amendment 003 frozen set `{INITIALIZING, BULLISH, BEARISH, TRANSITION}`) — representation reconciliation only, no new persisted member. `StructuralRegime.INITIALIZING → ActiveDealingRange = NONE` until #20 establishes the initial structural regime and governing pair. Once they exist, #21 may create the first active range without requiring an additional BOS for initialization.

## Range Update Rule (event-driven)
These alone do NOT update the active range: new candle; new mechanical swing; internal HH/HL/LH/LL; wick beyond boundary; ordinary price extreme; FVG; IFVG; liquidity pool; LRL. A replacement requires a **confirmed structural event + new finalized governing structural boundary pair**. Same-direction replacement: old range → TERMINATED/HISTORICAL; new pair → NEW ACTIVE RANGE. The previous range is never mutated into the new range.

## MSS / Transition
Opposing MSS: active range → TERMINATED → HISTORICAL; `StructuralRegime → TRANSITION`; `ActiveDealingRange = NONE`. The old range may remain historically queryable but cannot feed new OTE calculations, continuation qualification, or active-range confluence. An MSS alone does not construct the opposite range; the new opposing active range is created only after the upstream structural mechanism establishes the opposing directional regime and complete valid governing boundary pair.

## Timeframe Isolation
`Range.timeframe = DefiningHigh.timeframe = DefiningLow.timeframe`. 1M structure cannot modify a 5M range; 5M cannot modify a 15M range. Nested ranges may coexist without merging.

## Range Object
```
StructuralRange {
  id; timeframe; upper_boundary; lower_boundary;
  defining_high_swing_id; defining_low_swing_id; defining_high_price; defining_low_price;
  regime; creation_time; confirmation_time; active; historical; created_by_event_id;
  termination_time; terminated_by_event_id; predecessor_range_id; successor_range_id
}
```
Historical terminated ranges are immutable. No look-ahead: a range cannot exist before its complete defining structural information is confirmed.

## ACTIVE_RANGE_INVALID (owner-authorized error)
`error_code: ACTIVE_RANGE_INVALID`; `owning_module: #21`; `severity: BLOCKING`. Trigger: `UpperBoundary <= LowerBoundary`, or the required boundary relationship fails validation after the governing pair is supplied. Behavior: `ActiveDealingRange = NONE`; no downstream #22 OTE from the invalid candidate; historical valid ranges not rewritten; immutable `ErrorRecord`. Do not reverse values, widen the range, substitute internal swings, or guess boundaries. Do not silently map to another code.

## Missing Boundary (distinct from invalid)
`DefiningHigh = NONE` or `DefiningLow = NONE` → `ActiveDealingRange = NONE`. This is **not** an error (missing/not-yet-established structural information ≠ an invalid completed range geometry). Not permission to find an alternative swing.

## Downstream Ownership
#21 emits `RangeID`, `RangeHigh`, `RangeLow`, `Regime`. [[#22 OTE]] consumes those and owns Fibonacci orientation / 0.50 / 0.79 / OTE geometry. #21 must not calculate OTE / premium / discount / Fibonacci percentages. [[#23 Liquidity — Sweeps]] may classify liquidity relative to the range but may not modify it; [[#24 LRL Selection]] may use the range but may not modify it; [[#25 FVG — IFVG]] may not modify it; #27/#28 consume downstream consequences only.

## Hard Invariants
`UpperBoundary > LowerBoundary`; boundaries are confirmed structural wick extremes; #21 never promotes an internal swing; replacement produces a new `RangeID` (never mutates); MSS → TRANSITION → `ActiveDealingRange = NONE`; timeframe isolation; historical ranges immutable; no look-ahead.

## Dependencies
Upstream: [[#20 Structural Classification]] (+ [[#16 Conflict Resolution — State Priority]] accepted events). Downstream: [[#22 OTE]], [[#23 Liquidity — Sweeps]], [[#24 LRL Selection]].

## Amendment Overrides
Enum reconciliation per [[Amendment 003]]; `ACTIVE_RANGE_INVALID` owner-authorized addition.

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`StructuralRange`) · [[Canonical Error Registry]] (`ACTIVE_RANGE_INVALID`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (range replacement new-ID; MSS termination; invalid geometry).

## Historical Source
[[Appendix A — Recovered Historical Transcript]]
