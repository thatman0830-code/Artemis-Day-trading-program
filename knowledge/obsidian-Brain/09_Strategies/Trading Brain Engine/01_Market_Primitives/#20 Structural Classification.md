---
primitive_id: "#20"
title: Exact Mechanical Structural Swing Classification
status: LOCKED_AND_IMPLEMENTABLE
source_type: canonical-implementation-spec
governing_amendments: ["003"]
upstream: ["#19 Mechanical Swing Selection"]
downstream: ["#16", "#21", "#24", "#13"]
historical_source_preserved: true
implementation_ready: true
---

# #20 â€” Exact Mechanical Structural Swing Classification

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns structural swing promotion, HH/HL/LH/LL classification, BOS association, protected-swing rule, and structural-regime state. Consumes mechanical swings from [[#19 Mechanical Swing Selection]]. #20 alone owns structural/protected-swing promotion (see [[#16 Conflict Resolution â€” State Priority]] Â§A).

## Canonical Definition
- **Mechanical Structural Swing Selection:** if multiple mechanical highs occur before an opposite structural low is established, only the highest survives as the structural high (symmetric for lows).
- **Classification:** HH / HL / LH / LL by comparison to prior structural swings.
- **BOS Association:** structure holds until a candle **body closes beyond** the protected swing.
- **Protected Swing Rule:** the latest HL becomes candidate protected low once the subsequent HH is confirmed by bullish continuation/BOS (symmetric â€” latest LH â†’ protected high on subsequent LL confirmation).
- **Initialization:** first two opposite confirmed swings establish the initial structural range; initial swings are not auto-classified.

## State / Lifecycle
`StructuralRegime` persisted set: `INITIALIZING`, `BULLISH`, `BEARISH`, `TRANSITION` (Amendment 003). `CONFLICTED` / `NEUTRAL` are **not** persisted regime members (non-persisted diagnostic; see [[#16 Conflict Resolution â€” State Priority]] Â§22 â€” a timeframe never ends a timestamp in a contradictory regime).

## Outputs
`StructuralSwing { id, class(HH/HL/LH/LL), price, protected(bool), regime_ref }`; current protected high/low; current regime.

## Hard Invariants
- structure breaks only on a candle **body** close beyond the protected swing
- only the extreme mechanical swing survives as structural before an opposite structural point
- protected-swing promotion requires the confirming subsequent structural move

## Amendment 006 Governing Clarifications
See [[Amendment 006]] (authoritative). Summary:
- **Classification enum** (Amendment 003, confirmed): `StructuralClassification {HH, LH, HL, LL, EQUAL_HIGH, EQUAL_LOW, UNCLASSIFIED}`. High vs prior high -> HH/LH/EQUAL_HIGH; low vs prior low -> HL/LL/EQUAL_LOW; no same-type predecessor -> UNCLASSIFIED. Exact Decimal comparison.
- **Input**: confirmed #19 MechanicalSwing + closed candles only for the body-close break. No raw-candle swing invention. No look-ahead.
- **Initialization**: begins INITIALIZING; first structural high+low = baseline (both UNCLASSIFIED) but NOT directional regime. Qualifying body-close strictly beyond baseline high/low -> candidate BULLISH/BEARISH BOS -> (accepted by #16) BULLISH/BEARISH. Wick-only initial break does not establish regime.
- **Protected swing**: bullish HL / bearish LH become CANDIDATE protection; promoted only after an ACCEPTED subsequent same-direction continuation BOS. No premature transfer. Accepted opposing MSS -> TRANSITION, protection ceases.
- **BOS/#16 boundary**: #20 qualifies BOS/MSS candidates (strict body close beyond governing reference; wick/equality never qualify); #16 owns arbitration/acceptance. #20 never suppresses candidates.
- **Same-pivot H+L**: consumed independently into their own same-type sequences (no priority).
- **Survival**: highest high / lowest low survives before the opposite side; equal-price identity tie-break = chronological first-confirmed.
- Finalized structural records immutable; timeframe-isolated.

### Final Locked Definition (Amendment 006)
#20 consumes confirmed #19 MechanicalSwing records and converts them into governing structural highs/lows, same-type classifications (HH/LH/EQUAL_HIGH, HL/LL/EQUAL_LOW, UNCLASSIFIED), candidate protected swings, and BOS/MSS candidates - without redefining mechanical pivots or conflict arbitration. Highest-high/lowest-low survives before the opposite side. Engine begins INITIALIZING; the first high/low pair is the baseline but not a directional regime; a qualifying body-close break establishes BULLISH/BEARISH subject to #16 acceptance. Bullish HL / bearish LH are candidate protection, promoted only after an accepted same-direction continuation BOS. Wick-only penetration never creates BOS/MSS where a body close is required; protected-swing violation creates the opposing MSS candidate; #16 exclusively resolves same-timestamp conflicts. Point-in-time, immutable, timeframe-isolated; #20 never builds ranges or downstream objects.
## Dependencies
Upstream: [[#19 Mechanical Swing Selection]]. Downstream: [[#16 Conflict Resolution â€” State Priority]], [[#21 Active Dealing Range]], [[#24 LRL Selection]], [[#13 Stop-Loss Selection]].

## Amendment Overrides
`StructuralRegime` enum per [[Amendment 003]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`StructuralSwing`) Â· [[Canonical Enum Registry]] (`StructuralRegime`).

## Tests
[[Primitive Test Matrix]] Â· [[Golden Scenarios]] (protected-swing body-close break).

## Historical Source
[[Appendix A â€” Recovered Historical Transcript]] (transcript "#8 â€” Final Locked Definition").

