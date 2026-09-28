---
primitive_id: "#28"
title: Exact Mechanical Entry-Zone Selection
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["002-R3", "005A", "003"]
upstream: ["#27 (eligible state)", "#25 FVG/IFVG", "#11 (reversal)"]
downstream: ["#13 Stop-Loss Selection", "#29.1 Entry Execution"]
historical_source_preserved: true
implementation_ready: true
---

# #28 — Exact Mechanical Entry-Zone Selection

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns the candidate entry-zone universe, exact eligible-zone selection, FVG/IFVG selection priority, EQ computation, and zone freezing. Invoked at the entry-zone-selection-eligible state (**not** `ARMED`). Returns the selected zone to [[#27 Setup Qualification]] for final ≥2R revalidation.

## Canonical Definition
- **Invocation:** Continuation → `ContinuationSetupState = CANDIDATE` + mandatory pre-zone prerequisites; Reversal #1 → `ReversalSetupState = MSS_CONFIRMED` + required 1M candidate-zone prerequisites (post-[[#11 CISD — 1M Confirmation]]).
- Build candidate universe → select exactly one eligible zone → compute EQ → **freeze** selection → return to #27.
- **Selection priority:** IFVG > FVG; then newest; then deepest; final tie-break = immutable object ID. Original-candidate fallback only. **No future-zone rescue** (frozen candidate set cannot be retroactively rescued by later-created zones).
- **EQ (Amendment 002 R3):** `EQ_raw = (ZoneHigh + ZoneLow) / 2`, normalized to `minimum_tick` via **ROUND HALF UP** (not generic nearest-tick). This entry-zone EQ is a **distinct** midpoint object from the [[#22 OTE]] 0.50 (different source geometry); the two are not merged.

## State / Lifecycle
`EntryZoneSelectionState` per Amendment 003. Selected zone is frozen (immutable) once chosen.

## Hard Invariants
- runs at entry-zone-selection-eligible state, not `ARMED`
- selects exactly one zone; IFVG > FVG > newest > deepest > immutable-ID tie-break
- freezes candidate set; no future-zone rescue; no look-ahead (only FVG/IFVG confirmed at the eligible instant)
- `EQ = (ZoneHigh + ZoneLow)/2` ROUND HALF UP to `minimum_tick`
- returns to #27 for authoritative ≥2R

## Dependencies
Upstream: [[#27 Setup Qualification]] (eligible state), [[#25 FVG — IFVG]], [[#11 CISD — 1M Confirmation]] (reversal). Downstream: [[#13 Stop-Loss Selection]], [[#29.1 Entry Execution]].

## Amendment Overrides
EQ normalization per [[Amendment 002]] R3; invocation/boundary per [[Amendment 005A]]; enums per [[Amendment 003]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`EntryZoneSelection`) · [[Canonical Enum Registry]] (`EntryZoneType`, `EntryZoneSelectionState`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (selected-zone invalid fallback; no future zone rescue; EQ fill/no-fill).

## Historical Source
[[Appendix A — Recovered Historical Transcript]]
