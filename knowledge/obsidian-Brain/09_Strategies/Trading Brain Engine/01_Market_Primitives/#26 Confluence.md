---
primitive_id: "#26"
title: Exact Mechanical Confluence Definition
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["003"]
upstream: ["#22", "#23", "#24", "#25", "MSS"]
downstream: ["#27 Setup Qualification"]
historical_source_preserved: true
implementation_ready: true
---

# #26 â€” Exact Mechanical Confluence Definition

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
**Facts / relationships layer only.** `#26 = FACTS/RELATIONSHIPS`, `#27 = SETUP DECISIONS`. #26 may **never** arm, reject, trigger, or execute a setup. [[#27 Setup Qualification]] consumes #26 outputs.

## Canonical Definition
Emits Boolean relationships between confirmed structural/imbalance facts:
```
OTE_FVG          OTE_IFVG
LRL_FVG          LRL_IFVG
SWEEP_FVG        SWEEP_IFVG
DISPLACEMENT_FVG DISPLACEMENT_IFVG
MSS_FVG          MSS_IFVG
```
Each is a fact about whether the two referenced objects overlap/coincide under their own primitive rules. #26 does not create or modify the underlying FVG/IFVG/OTE/LRL/sweep/MSS objects.

## Inputs / Outputs
Inputs: confirmed objects from [[#22 OTE]], [[#23 Liquidity â€” Sweeps]], [[#24 LRL Selection]], [[#25 FVG â€” IFVG]], and MSS. Outputs: the Boolean relationship set consumed by #27.

## Hard Invariants
- #26 produces relationships only; never arms/rejects/triggers/executes
- does not modify any underlying primitive object
- `ConfluenceType / ConfluenceCategory / ConfluenceResult` enums per [[Amendment 003]]

## Confluence Persistence — Active vs Historical (owner-supplied recovered source)
Confluence is dynamic, not permanent.
```
OTE + FVG            -> CONFLUENCE = TRUE
then FVG fully mitigated -> CONFLUENCE = FALSE
```
The historical confluence event may remain recorded, but it is no longer active. The engine maintains **Historical Confluence** and **Active Confluence** as separate concepts.

## Termination Rules
- OTE + FVG terminates if: OTE terminates; FVG terminates; positive overlap disappears.
- OTE + IFVG terminates if: OTE terminates; IFVG terminates; overlap disappears.
- LRL + FVG terminates if: LRL is consumed/terminated; FVG terminates; FVG is no longer positioned between price and the LRL.

## Confluence Object (owner-supplied)
```
Confluence {
    id
    type

    primary_object_id
    secondary_object_id

    primary_type
    secondary_type

    primary_timeframe
    secondary_timeframe

    overlap_low
    overlap_high
    overlap_width

    directional_compatibility

    temporal_relationship
    positional_relationship
    causal_relationship

    created_time
    terminated_time

    active
    historical
}
```
An ephemeral computed Boolean view (`ConfluenceEvaluation` / `ConfluenceResult`) is allowed internally for the current cycle, but it does not replace the recorded historical `Confluence` object where the canonical source records a relationship.

## Final Locked Definition (history addendum)
Only active and setup-eligible objects can produce active confluence; historical relationships may remain recorded. #26 remains facts/relationships only, Boolean at the primitive relationship level, and never arms/rejects/triggers/executes a setup.
## Dependencies
Upstream: [[#22 OTE]], [[#23 Liquidity â€” Sweeps]], [[#24 LRL Selection]], [[#25 FVG â€” IFVG]], MSS. Downstream: [[#27 Setup Qualification]].

## Amendment Overrides
Enums per [[Amendment 003]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`Confluence`) Â· [[Canonical Enum Registry]] (`ConfluenceType/Category/Result`).

## Tests
[[Primitive Test Matrix]] Â· [[Golden Scenarios]] (boundary touching not confluence).

## Historical Source
[[Appendix A â€” Recovered Historical Transcript]]

