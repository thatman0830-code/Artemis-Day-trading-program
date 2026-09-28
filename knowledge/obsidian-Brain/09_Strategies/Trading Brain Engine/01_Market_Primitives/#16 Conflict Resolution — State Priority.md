---
primitive_id: "#16"
title: Exact Mechanical Conflict Resolution / State Priority
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["001-C2", "003", "005A"]
upstream: ["#19", "#20", "#23 candidate events"]
downstream: ["#21 Active Dealing Range", "setup layer"]
historical_source_preserved: true
implementation_ready: true
---

# #16 â€” Exact Mechanical Conflict Resolution / State Priority

## Status
LOCKED_AND_IMPLEMENTABLE

## 1. Ownership (arbitration layer only)
Consumes candidate facts/events already qualified by their owning primitives and determines: event precedence; state-transition precedence; same-candle/same-timestamp conflict resolution; accepted vs suppressed structural events; deterministic post-event structural state. **Must never redefine the primitive qualification rules themselves.**

## 2. Frozen Pre-State (hard no-look-ahead invariant)
For every timeframe and finalized processing candle/timestamp: (1) freeze `StateBefore(t)`; (2) detect observations; (3) qualify candidates against `StateBefore(t)`; (4) resolve collisions with #16; (5) commit accepted events; (6) apply structural mutations; (7) build downstream objects; (8) freeze `StateAfter(t)`. No partially-mutated same-candle state may create another candidate event unless an explicit primitive separately authorizes it.

## 3. Canonical Dependency Order
`DATA VALIDATION â†’ RAW PRICE/SWING â†’ LIQUIDITY/SWEEP â†’ DISPLACEMENT â†’ STRUCTURAL BREAK EVAL â†’ MSS/BOS RESOLUTION â†’ PROTECTED-SWING UPDATE â†’ STRUCTURAL REGIME UPDATE â†’ ACTIVE DEALING RANGE UPDATE â†’ FVG/IFVG STATE â†’ OTE/CONFLUENCE â†’ SETUP STATE â†’ ENTRY/EXECUTION`. Dependency sequencing, not subjective importance.

## 4. BOS vs MSS (from StateBefore(t))
- `StateBefore.regime = BULLISH`: same-direction break above governing continuation reference â†’ candidate BULLISH BOS; break below `ProtectedLowBefore(t)` â†’ candidate BEARISH MSS.
- `StateBefore.regime = BEARISH`: same-direction break below governing continuation reference â†’ candidate BEARISH BOS; break above `ProtectedHighBefore(t)` â†’ candidate BULLISH MSS.

## 5. Primary Structural Priority
Same-direction BOS and opposing MSS qualifying against the SAME frozen pre-event regime â†’ **OPPOSING MSS > SAME-DIRECTION BOS** for structural-state ownership. Accept MSS; suppress BOS from structural-state mutation; retain suppressed BOS diagnostically. Suppressed BOS may NOT extend old regime, create same-direction protection transfer, create new same-direction active range, arm continuation, or alter `StateAfter(t)`.

## 6. MSS Is Not First Opposing BOS
Accepted MSS: old regime TERMINATED; old protected swing removed/historical; old active range terminated; new regime state = TRANSITION. MSS must not simultaneously be counted as the first BOS of the opposing regime; opposing BOS requires its own subsequently valid structural confirmation.

## 7. Protected-Swing Same-Candle Rule
Candidate MSS uses `ProtectedSwingBefore(t)` only. Forbidden: same-candle BOS creates new protected swing â†’ same candle breaks new protection â†’ MSS (state-order contamination). If BOS survives â†’ structural update + protection transfer. If MSS wins â†’ old protection removed, NO same-direction protection transfer.

## 8. Multiple Structural References (priority)
1. protected swing whose violation creates MSS; 2. governing primary/external BOS reference; 3. other structural references; 4. internal structural references; 5. raw mechanical swings. Lower-ranked broken levels recorded diagnostically only. Multiple same-direction levels crossed do not create repeated primary BOS transitions; primary BOS attaches only to the governing BOS reference owned by the BOS primitive.

## 9. Independent Same-Candle Events
Liquidity Sweep, Qualifying Displacement, FVG creation, IFVG conversion, BOS/MSS are NOT mutually exclusive. A single candle may legally produce LRL Sweep + Qualifying Displacement + Protected Swing Break + MSS + FVG when each independently qualifies. No one-event-per-candle behavior.

## 10. Sweep / Reversal Order
For Reversal Entry #1, `SweepTime <= MSSTime` is permitted (strict `<` not required). Same-candle sweep â†’ displacement â†’ protected-break â†’ MSS is valid when geometry/chronology supports all required facts. `Sweep â‰  MSS`, `Sweep â‰  BOS`.

## 11. Displacement Association
A structural break may associate only with the qualifying displacement leg containing the confirming structural close: `StructuralBreak.confirmation_candle âˆˆ AssociatedDisplacementLeg`. Body close beyond level but `QualifyingDisplacement = FALSE` â†’ BOS/MSS FALSE. Qualifying displacement TRUE but no required body close through governing structural reference â†’ BOS/MSS FALSE.

## 12. Wick-Only Break
Where BOS/MSS require body close, a wick-only violation â†’ NO BOS / NO MSS. The same wick may still independently qualify as a #23 liquidity sweep (`Sweep = TRUE, MSS = FALSE`).

## 13. LRL Pre-Event Ownership
`ReversalSweepReference = LRL valid before the structural mutation being resolved`. Do not retroactively select liquidity after a same-candle regime mutation to satisfy that candle's reversal sweep requirement.

## 14. Timeframe Isolation
Conflict resolution operates independently per timeframe. Do not suppress a valid LTF event because an HTF disagrees (`15M BULLISH / 5M TRANSITION / 1M BEARISH` is valid multi-timeframe structure, not a #16 conflict). `1M MSS` cannot mutate 5M state; `5M MSS` cannot mutate 15M. HTF context may affect #27 eligibility later but cannot rewrite LTF event truth.

## 15. Structure Before Downstream Objects
`Candidate BOS/MSS â†’ #16 â†’ Accepted structural event â†’ Protection/Regime update â†’ #21 Active Dealing Range`. Never update #21 from a candidate BOS before resolution. #22 consumes only the resulting valid active range; no same-cycle OTE from a range terminated by the accepted event. #26/#27/#28 consume only resolved/finalized upstream state.

## 16. Setup / Entry Priority
Setup qualification is downstream of #16. A setup cannot arm from a suppressed structural candidate. If a pending unfilled setup is invalidated by a higher-priority accepted structural event: `setup invalidation > pending entry`, subject to actual chronology. If higher-resolution chronology proves the entry fill happened first, execution owns the resulting OPEN position; once `ENTRY_FILLED â†’ POSITION_OPEN`, a later MSS/BOS conflict cannot retroactively erase the trade (governed by [[#29.3 Protective Orders]] / [[#29.4 Exit Resolution]]).

## 17. Chronology
Resolution hierarchy: Tick/trade-level â†’ Sub-1M â†’ 1M â†’ Higher-timeframe OHLC. Known chronology overrides assumed. #16 does not reorder known events. Where mutually exclusive structural candidates arise from unresolved OHLC chronology, use frozen pre-state + the #16 priority hierarchy (no invented intrabar path). **Execution ambiguity remains owned by [[#29.4 Exit Resolution]]** (`OHLC_AMBIGUOUS_STOP_PRIORITY`).

## 18. Data Integrity
`DATA_INTEGRITY_ERROR` has **absolute priority** over market-state interpretation. If required source data is structurally invalid/ambiguous under the global data-integrity contract, do not fabricate BOS/MSS/Sweep/Displacement/Range/Setup; no affected finalized downstream structural snapshot may be created.

## 19â€“20. Suppressed Event & ConflictResolution Objects
Suppression preserves evidence: `CandidateEvent { qualified_conditions; accepted; suppression_reason; suppressing_event_id }` (e.g. suppression_reason = `OPPOSING_MSS_STATE_PRIORITY`). Suppressed events immutable, may not mutate state. `ConflictResolution { id; timeframe; processing_timestamp; pre_state_id; post_state_id; candidate_event_ids[]; accepted_event_ids[]; suppressed_event_ids[]; primary_structural_event_id; conflict_type; resolution_rule; chronology_source; chronology_resolution; created_time; immutable }`.

## 21. Structural Priority Table
Invalid data > market-state interpretation Â· Sweep/Displacement/FVG/IFVG vs BOS/MSS â†’ may coexist Â· same-direction BOS vs opposing MSS â†’ MSS Â· internal vs primary/external â†’ primary/external Â· raw swing vs structural swing â†’ structural Â· old protection vs newly proposed same-candle protection â†’ pre-event protected swing Â· candidate vs accepted â†’ accepted Â· known vs inferred chronology â†’ known Â· structural resolution vs downstream range/OTE/setup â†’ structural first.

## 22. Hard Invariants
Candidate evaluation uses frozen `StateBefore(t)`. One timeframe cannot end one timestamp in contradictory regimes. Opposing MSS > same-direction BOS only vs the same frozen pre-event regime. MSS cannot become the first opposing BOS. Same-candle BOS cannot create protection then have it retroactively broken by the same candle. `Sweep â‰  MSS/BOS`, `Displacement â‰  MSS/BOS`. FVG/IFVG cannot create structure. Internal structure cannot override primary/external for regime ownership. Timeframes isolated. Known chronology beats assumed. Suppressed events cannot mutate state. No look-ahead. Historical accepted/suppressed records immutable.

## 39. Exact Structural Resolution Algorithm

```
INPUT:
    finalized candle t
    timeframe TF
    StateBefore(t)

1.  Validate source data.
2.  Freeze StateBefore(t).
3.  Detect raw observations:
        swing interactions
        liquidity interactions
        FVG/IFVG conditions
        structural-level interactions
4.  Determine qualifying liquidity events.
5.  Determine qualifying displacement events.
6.  Evaluate BOS candidates using:
        StateBefore(t)
7.  Evaluate MSS candidates using:
        StateBefore(t)
        ProtectedSwingBefore(t)
8.  If no BOS/MSS candidate qualifies:
        structural state unchanged.
9.  If only BOS qualifies:
        accept BOS.
10. If only MSS qualifies:
        accept MSS.
11. If both same-direction BOS and opposing MSS qualify:
        accept MSS; suppress BOS for structural-state purposes.
12. If multiple structural references break:
        protected/regime-changing reference first;
        governing external reference second;
        internal references afterward.
13. Commit accepted structural event.
14. Update protected-swing state.
15. Update structural regime.
16. Update active dealing range.
17. Process downstream FVG/IFVG lifecycle, OTE/confluence and setup state.
18. Freeze StateAfter(t).
19. Store immutable ConflictResolution record.
```

> Note: canonical §40 Hard Invariants are preserved above as "## 22. Hard Invariants" of this note (consolidated during persistence; not renumbered, per the source-completion requirement).

## 41. Final Locked Definition

#16 — Exact Mechanical Conflict Resolution / State Priority is the deterministic arbitration layer that resolves simultaneous or competing mechanical events without redefining the primitives that generated them. Every processing cycle evaluates candidate events against a frozen pre-event state, resolves conflicts before mutating structure, and produces exactly one coherent post-event structural state per timeframe. Independent events such as liquidity sweeps, displacement, FVG/IFVG creation, and structural breaks may coexist on the same candle. When a valid same-direction BOS and an opposing MSS compete for ownership of the same pre-existing structural regime, MSS has priority because violation of the protected swing terminates that regime; the competing BOS is retained diagnostically but suppressed from structural-state mutation. Protected-swing references are those that existed before the event, preventing same-candle state mutation from generating retroactive structural signals. Primary/external structural events outrank internal events for regime ownership, timeframes remain isolated, known intrabar chronology overrides inferred chronology, and all downstream range, OTE, confluence, setup, and execution processing occurs only after structural conflict resolution has finalized the applicable state.

The core engine order is therefore:

```
FROZEN PRE-STATE
        ↓
OBSERVATIONS
        ↓
LIQUIDITY / SWEEP
        ↓
DISPLACEMENT
        ↓
BOS + MSS CANDIDATES
        ↓
#16 CONFLICT RESOLUTION
        ↓
ACCEPTED STRUCTURAL EVENT
        ↓
PROTECTION / REGIME
        ↓
#21 ACTIVE DEALING RANGE
        ↓
#22 OTE
        ↓
FVG / IFVG / CONFLUENCE
        ↓
SETUP
        ↓
EXECUTION
        ↓
IMMUTABLE POST-STATE
```

And the central priority invariant is:

**Opposing MSS > Same-Direction BOS** — only when both compete for structural-state ownership against the same frozen pre-event regime.
## Dependencies
Upstream: [[#19 Mechanical Swing Selection]], [[#20 Structural Classification]], [[#23 Liquidity â€” Sweeps]] (candidate events). Downstream: [[#21 Active Dealing Range]], setup layer, [[#11 CISD â€” 1M Confirmation]] (MSS_CONFIRMED).

## Amendment Overrides
`DATA_INTEGRITY_ERROR` precedence per [[Amendment 001]] C2 / [[Amendment 003]]. New objects/enums (`CandidateEvent`, `ConflictResolution`, `SuppressionReason`, `ConflictType`, `ResolutionRule`) registered as additive â€” [[Canonical Object Registry]], [[Canonical Enum Registry]].

## Tests
[[Primitive Test Matrix]] Â· [[Golden Scenarios]] (MSS vs BOS priority; same-candle sweep+displacement+MSS).

## Historical Source
[[Appendix A â€” Recovered Historical Transcript]]

