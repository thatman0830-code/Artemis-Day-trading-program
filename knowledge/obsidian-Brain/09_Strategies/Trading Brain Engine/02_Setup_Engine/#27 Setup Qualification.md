---
primitive_id: "#27"
title: Exact Mechanical Setup Qualification
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["005A", "003"]
upstream: ["#26 Confluence", "#24 LRL", "#11 (reversal)"]
downstream: ["#28 Entry-Zone Selection", "arm"]
historical_source_preserved: true
implementation_ready: true
---

# #27 — Exact Mechanical Setup Qualification

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns setup **decisions**: structural/sequence qualification, entry-zone-selection-eligibility gating, final executability revalidation, and the authoritative **≥2R** decision. Consumes Boolean facts from [[#26 Confluence]]. `#26 = FACTS`, `#27 = DECISIONS`. Does not select the entry zone or compute EQ (that is [[#28 Entry-Zone Selection]]).

## Canonical Ownership Sequence (Amendment 005A)
```
#27 structural/sequence qualification
  → entry-zone-selection-eligible state
  → #28 select exactly one eligible zone, compute/freeze EQ
  → #27 final executability revalidation (Entry + Stop + Target + ≥2R)
  → executable armed state
```
**#28 does not require `ARMED`.** The historical `IF Setup.state != ARMED: #28 does nothing` circular wording is superseded and must not be restored.

## State Machines
- **Continuation:** `ContinuationSetupState = CANDIDATE` + mandatory pre-zone prerequisites → #28. Post-#28: valid → `ARMED`; `R<2` → `REJECTED`; no eligible zone → remain `CANDIDATE`.
- **Reversal #1:** `ReversalSetupState = MSS_CONFIRMED` + required 1M-confirmation prerequisites (see [[#11 CISD — 1M Confirmation]]) → #28. Post-#28 + #27 confirm target+stop+≥2R → `ENTRY_ZONE_ARMED`.

## ≥2R Ownership
Authoritative final ≥2R decision belongs to #27 after one zone is selected. `Entry = #28 selected EQ`, `Stop = #13`, `Target = #24 LRL`. `Risk = abs(Entry − Stop)`, `Reward = abs(Target − Entry)`, `R = Reward/Risk`; `R ≥ 2` → may arm; `R < 2` → `REJECTED`. No farther target may be chosen to manufacture ≥2R.

## Hard Invariants
- #27 consumes #26 facts; never mutates underlying objects
- #28 invoked at entry-zone-selection-eligible state, not `ARMED`
- authoritative ≥2R owned by #27
- consumes deterministic Stop from [[#13 Stop-Loss Selection]] and Target from [[#24 LRL Selection]]

## Dependencies
Upstream: [[#26 Confluence]], [[#24 LRL Selection]], [[#11 CISD — 1M Confirmation]] (reversal), [[#13 Stop-Loss Selection]]. Downstream: [[#28 Entry-Zone Selection]].

## Amendment Overrides
Sequence & ≥2R per [[Amendment 005A]]; setup-state enums per [[Amendment 003]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`Setup`) · [[Canonical Enum Registry]] (`SetupModel`, `ContinuationSetupState`, `ReversalSetupState`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (2R rejection; selected-zone invalid fallback).

## Historical Source
[[Appendix A — Recovered Historical Transcript]]
