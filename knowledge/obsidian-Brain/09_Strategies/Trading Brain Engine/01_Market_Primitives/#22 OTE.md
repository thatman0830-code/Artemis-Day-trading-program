---
primitive_id: "#22"
title: Exact Mechanical OTE Definition
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["002-R3"]
upstream: ["#21 Active Dealing Range"]
downstream: ["#26 Confluence", "#28 Entry-Zone Selection"]
historical_source_preserved: true
implementation_ready: true
---

# #22 â€” Exact Mechanical OTE Definition

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns Fibonacci orientation and OTE geometry over the active dealing range. Consumes `RangeID / RangeHigh / RangeLow / Regime` from [[#21 Active Dealing Range]]; does not construct the range.

## Canonical Definition
**OTE = the inclusive Fibonacci 0.50â€“0.79 zone of the active dealing range.** The `0.50` bound = the dealing-range midpoint. Anchors follow the range boundaries produced by #21 (bullish: `ProtectedLow â†’ governing StructuralHigh`; bearish: `ProtectedHigh â†’ governing StructuralLow`) â€” i.e. #22 computes OTE on `RangeHigh/RangeLow`, not an independently selected displacement-anchor pair.

**Equilibrium reconciliation:** the standalone historical "Equilibrium" carried only the `50% = Equilibrium` relationship, which is fully covered by the OTE `0.50` (range midpoint). No separate Equilibrium rule exists; this is alias/terminology reconciliation only (see [[Amendment 004]] Part III). The `#28` entry-zone EQ is a **distinct** midpoint object on a different geometry (the selected entry zone) â€” see [[#28 Entry-Zone Selection]]; do not merge the two.

## Inputs / Outputs
Inputs: `RangeHigh`, `RangeLow`, `Regime` (from #21). Outputs: OTE zone `[0.50, 0.79]` of the active dealing range; premium/discount orientation.

## Hard Invariants
- OTE strictly consumes #21 boundaries; #22 never constructs or mutates the range
- `0.50` = range midpoint; zone is inclusive `0.50â€“0.79`
- computed with deterministic decimal precision ([[Precision â€” Rounding Policy]])

## Lifecycle & History (owner-supplied recovered source)

Active OTE generation:
- Only the active dealing range generates active OTE.
- A same-direction BOS terminates the old active range/OTE and creates a NEW OTE from the new range; the new OTE is recalculated from scratch.
- An MSS terminates the current directional dealing range and therefore terminates the active OTE.
- During TRANSITION: `ActiveDealingRange = NONE`, `ActiveOTE = NONE`.

Immutability:
- Historical OTE zones are immutable.
- Once created, OTE anchors, 50% price, 79% price, timeframe, direction, creation time, and associated range never change.
- Entering OTE does NOT invalidate OTE.
- OTE has NO FVG-style mitigation lifecycle.
- Price traversal does not rewrite OTE geometry.
- Timeframe isolation.

## OTE State Machine
```
NO_ACTIVE_RANGE
   -> RANGE_CONFIRMED
   -> OTE_ACTIVE
   -> (same-direction BOS) -> new OTE (recalculated from the new range)
   -> (MSS)                -> OTE_TERMINATED / TRANSITION  (ActiveOTE = NONE)
```

## OTE Object (lifecycle / history fields)
```
OTE {
    id
    timeframe
    direction
    range_id

    anchor_high
    anchor_low
    eq_50_price
    ote_79_price

    creation_time
    confirmation_time

    active
    historical
    terminated_by_event_id
}
```
An in-memory `active_ote_id` pointer may live in TimeframeState, but the OTE object itself is an append-only immutable historical record.

## Final Locked Definition (history addendum)
Historical OTE objects are immutable. The 0.50-0.79 geometry and the #21 -> #22 ownership boundary above are unchanged; this section adds only the owner-supplied lifecycle/history mechanics.
## Dependencies
Upstream: [[#21 Active Dealing Range]]. Downstream: [[#26 Confluence]], [[#28 Entry-Zone Selection]].

## Amendment Overrides
Precision per [[Amendment 002]] R3. Equilibrium alias per [[Amendment 004]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`OTE`).

## Tests
[[Primitive Test Matrix]] Â· [[Golden Scenarios]] (OTE geometry).

## Historical Source
[[Appendix A â€” Recovered Historical Transcript]]

