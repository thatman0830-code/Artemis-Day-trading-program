---
primitive_id: "#23"
title: Exact Mechanical Liquidity Pools / Sweeps
status: LOCKED_AND_IMPLEMENTABLE
source_type: canonical-implementation-spec
governing_amendments: []
upstream: ["#19", "#20", "#21"]
downstream: ["#24 LRL Selection", "#16"]
historical_source_preserved: true
implementation_ready: true
---

# #23 — Exact Mechanical Liquidity Pools / Sweeps

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns liquidity pool/level construction, sweep/break state, and internal/external classification relative to the active dealing range. Consumes the active range from [[#21 Active Dealing Range]] (positional classification only; never modifies the range).

## Canonical Definition
- **Pool** = 2+ equal qualifying swings; a single qualifying swing = a liquidity **level/reference**, not a pool. `tolerance_ticks = 1`.
- **Sweep** = penetration strictly beyond the level **+ close back across** → `SWEPT → CONSUMED`.
- Penetration **+ close beyond** → `BROKEN → CONSUMED`.
- **Touch** (extreme equals/approaches the level without strict penetration) is **not** a sweep and does not consume.
- No maximum penetration distance; no ATR-based threshold; deepest penetration recorded.
- Sides: BSL / LSL.
- **Internal** = inside the current active dealing range; **External** = outside, or a major reference (PDH/PDL, PWH/PWL, session extreme, major structural extreme).
- An internal-liquidity sweep does not alter dealing range, protected swing, regime, or bias.

## State / Lifecycle
`LiquidityState { ACTIVE, VIOLATED, SWEPT, BROKEN, CONSUMED }`. `ACTIVE → (penetration) → VIOLATED → (close back across) → SWEPT → CONSUMED`; or `VIOLATED → (close beyond) → BROKEN → CONSUMED`. Touch keeps `ACTIVE`.

## Object
```
LiquidityPool { id; timeframe; side(BSL/LSL); component_reference_ids[]; component_prices[];
  consolidated_level; tolerance_ticks = 1; touch_count; state }
```

## Hard Invariants
- sweep ⇔ penetration **+ close back across**; touch ≠ sweep
- no ATR / max-distance threshold; deepest penetration recorded
- internal-liquidity sweep never mutates range / protected / regime / bias
- pool requires ≥2 equal qualifying swings (single = level/reference)

## Dependencies
Upstream: [[#19 Mechanical Swing Selection]], [[#20 Structural Classification]], [[#21 Active Dealing Range]]. Downstream: [[#24 LRL Selection]], [[#16 Conflict Resolution — State Priority]].

## Amendment Overrides
NONE (`LiquidityState` per [[Amendment 003]]).

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`LiquidityPool`, `LiquiditySweep`) · [[Canonical Enum Registry]] (`LiquidityState`, `LiquiditySide`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (liquidity sweep vs touch).

## Historical Source
[[Appendix A — Recovered Historical Transcript]] (transcript "50. Final locked definition").
