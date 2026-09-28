---
title: Amendment 006
status: ACTIVE
precedence: OWNER_RESOLUTION
appendix_modified: false
resolves: ["#20 classification/init/protected-swing/BOS-association"]
scope: "#20 only (+ #20/#16 interface)"
---

# Owner Resolution Amendment 006 — #20 Structural Classification / Initialization / Protected-Swing / BOS-Association

Precedence tier 1. Appendix A unchanged. Applies only to the #20 structural layer and its interface with [[#16 Conflict Resolution — State Priority]]. Does not change #19, redefine #16, or authorize any other primitive.

## Part I — Frozen enums (already Amendment 003; confirmed authoritative)
```
StructuralClassification { HH, LH, HL, LL, EQUAL_HIGH, EQUAL_LOW, UNCLASSIFIED }
StructuralRegime         { INITIALIZING, BULLISH, BEARISH, TRANSITION }   (CONFLICTED/NEUTRAL not persisted)
```
Same-type exact Decimal comparison (no epsilon/tolerance/display-rounding):
- High: `new > prior → HH`; `new < prior → LH`; `new == prior → EQUAL_HIGH`.
- Low: `new > prior → HL`; `new < prior → LL`; `new == prior → EQUAL_LOW`.
- No valid same-type predecessor → `UNCLASSIFIED`.

## Part II — #20 input contract
Consumes confirmed #19 `MechanicalSwing` records **plus closed candle data only** where required to evaluate the body-close structural-break/BOS-association rule (auxiliary break input, not a second swing detector). Raw candles may not bypass #19 to create structural swings. No look-ahead: at T, only swings confirmed ≤ T and closed candles ≤ T.

## Part III — Initial structural baseline
Engine begins `INITIALIZING`. First confirmed structural high + first confirmed structural low establish the baseline (both `UNCLASSIFIED`); this **does not** create directional regime. From `INITIALIZING`: a qualifying body-close **strictly above** the governing baseline high → candidate BULLISH BOS → (if accepted by #16) `BULLISH`, and the associated governing low becomes the initial protected low; symmetric for `BEARISH`. Wick-only initial break does not establish regime.

## Part IV — Protected-swing promotion
A protected swing is not "newest HL/LH". Bullish: a structural `HL` becomes a **candidate** protected low; it is promoted to protected low **only after** a subsequent **accepted** bullish continuation BOS (previous protected low → historical). Symmetric bearish (`LH` candidate protected high). No premature transfer: a bare HL/LH, a wick-only break, an internal swing, or a #16-suppressed candidate never transfers protection. Accepted opposing MSS → old regime terminates, protection ceases, regime → `TRANSITION`.

## Part V — BOS association / #16 boundary
#20 **owns candidate qualification** (governing reference + closed-candle body + required structural-break conditions → BOS/MSS **candidate**), including the body-close rule (strict close beyond reference; wick/equality never qualify). #16 **owns arbitration** (BOS-vs-MSS, MSS>same-direction-BOS, accepted vs suppressed, ConflictResolution). #20 must never independently suppress a candidate. Interface: `#20 qualify candidate → #16 resolve → accepted event → #20 commit state → #21`.

## Part VI — Same-pivot #19 H+L
The #19 dual-swing ruling stands: #20 consumes both records independently — the H feeds the structural-high sequence, the L the structural-low sequence; no H-vs-L priority from a shared pivot/time/candle.

## Part VII — Survival
Before the opposite governing structural side is established, the **highest** qualifying high survives (symmetric: lowest low). Equal competing candidates classify EQUAL_HIGH/EQUAL_LOW where a finalized same-type predecessor exists; for two mechanically-distinct same-price candidates competing for one unfinalized governing role with no other canonical distinction, use **chronological first-confirmed** as governing identity (deterministic identity tie-break at equal price; does not change the structural price), preserving the later equal-price observation historically.

## Part VIII–X — Commit boundary / immutability / non-errors
Only an **accepted** structural event may change persisted regime, finalize/terminate protection, or drive #21. Non-conflict single candidates may be passed through by #16's locked resolver. Finalized `StructuralSwing` records are immutable; state evolves via new snapshots. `UNCLASSIFIED` (no predecessor), `INITIALIZING` (no baseline), wick-only-no-candidate, and #16-suppressed candidates are valid non-error outcomes.

## Sync
[[#20 Structural Classification]] (Amendment 006 Governing Clarifications section) · [[Canonical Enum Registry]] (`StructuralClassification`). Final Locked Definition recorded in the #20 note.
