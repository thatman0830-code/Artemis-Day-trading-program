---
primitive_id: "#25"
title: Exact Mechanical FVG / IFVG
status: LOCKED_AND_IMPLEMENTABLE
source_type: canonical-implementation-spec
governing_amendments: []
upstream: ["price / candle geometry"]
downstream: ["#26 Confluence", "#28 Entry-Zone Selection"]
historical_source_preserved: true
implementation_ready: true
---

# #25 — Exact Mechanical FVG / IFVG

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns FVG geometry, mitigation state, and one-time IFVG polarity inversion. Does not select the entry zone (that is [[#28 Entry-Zone Selection]]).

## Canonical Definition
- **FVG** = 3-candle imbalance with a minimum one-tick gap.
- **Mitigation** registered as price returns into the gap (no arbitrary 50% mitigation threshold; actual deepest penetration recorded).
- **IFVG** = a **one-time** polarity inversion after the FVG is violated (one conversion only).
- Timeframe isolation preserved.

## State / Lifecycle
`FVGState { ACTIVE, MITIGATED, VIOLATED, INVERTED(IFVG) }`. Conversion FVG→IFVG occurs once.

## Hard Invariants
- FVG requires a minimum one-tick gap (3-candle geometry)
- no arbitrary 50% mitigation threshold; deepest penetration recorded
- IFVG = one-time inversion (single conversion)
- timeframe isolation

## Dependencies
Upstream: price/candle geometry. Downstream: [[#26 Confluence]], [[#28 Entry-Zone Selection]].

## Amendment Overrides
NONE (`FVGState` per [[Amendment 003]]).

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`FVG`, `IFVG`) · [[Canonical Enum Registry]] (`FVGState`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (FVG geometry).

## Historical Source
[[Appendix A — Recovered Historical Transcript]] (transcript "Final locked definition").
