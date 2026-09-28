---
primitive_id: "#11"
title: Exact Mechanical CISD / 1M Confirmation
status: LOCKED_AND_IMPLEMENTABLE
source_type: owner-supplied-recovered-source
governing_amendments: ["003", "005A"]
upstream: ["#16 (MSS_CONFIRMED)", "#24 REVERSAL_SWEEP_REFERENCE"]
downstream: ["#28 Entry-Zone Selection (reversal)"]
historical_source_preserved: true
implementation_ready: true
timeframe: 1M
---

# #11 — Exact Mechanical CISD / 1M Confirmation

## Status
LOCKED_AND_IMPLEMENTABLE

## 1. Purpose
Answers exactly one question: after Reversal Entry #1 has reached `MSS_CONFIRMED`, what exact 1M event constitutes confirmation and permits the setup to proceed to entry-zone eligibility and #28?

```
LRL selected → LRL swept → counter-directional displacement → protected swing broken
→ MSS_CONFIRMED → #11 (1M CISD / CONFIRMATION) → CONFIRMATION_VALID
→ eligible post-confirmation 1M FVG/IFVG universe → #28 Entry-Zone Selection
```
#11 is a **confirmation primitive, not an entry primitive**.

## 2. Ownership
**OWNS:** 1M CISD detection; CISD direction; relevant delivery-candle selection; delivery-candle reference price; confirmation candle; confirmation timestamp; body-close qualification; same-candle MSS/CISD eligibility; temporal association with the current reversal setup; confirmation validity; confirmation expiration/invalidation; post-confirmation zone eligibility boundary; CISD state.

**DOES NOT OWN:** liquidity-pool construction; LRL selection; liquidity sweep detection; displacement qualification; protected-swing selection; MSS detection; FVG creation/mitigation; IFVG conversion; OTE; entry-zone selection; EQ calculation; stop selection; target selection; order placement; order fills; position sizing; execution.

## 3. CISD Definition
CISD — Change in State of Delivery — is confirmed when 1M price **body-closes through the OPEN** of the relevant immediately preceding opposing delivery candle.
- Bullish CISD: `1M Close > Relevant Bearish Delivery Candle Open`
- Bearish CISD: `1M Close < Relevant Bullish Delivery Candle Open`
- Comparison is **strict**. Equality does not qualify.

## 4. Delivery Candle Definition
A completed 1M candle of the direction **opposite** the intended reversal, belonging to the immediately preceding opposing directional delivery. Bullish confirmation → reference delivery = BEARISH; bearish confirmation → reference delivery = BULLISH. The CISD level is the delivery candle's **OPEN** (not high/low/close/midpoint/body-midpoint/FVG boundary).

## 5. Relevant Delivery Candle (deterministic selection)
For the current 1M reversal sequence, identify the immediately preceding opposing directional delivery leg that directly precedes the confirming directional reversal delivery. The CISD reference candle is **the candle that initiated that immediately preceding opposing directional delivery leg**.
- Bullish CISD: `RelevantDeliveryCandle = first candle of the immediately preceding bearish delivery leg`.
- Bearish CISD: `RelevantDeliveryCandle = first candle of the immediately preceding bullish delivery leg`.
- `CISDReferencePrice = RelevantDeliveryCandle.open`. This prevents choosing whichever opposing candle produces the easiest CISD.

## 6. Delivery-Leg Requirement
The referenced delivery candle must belong to the delivery sequence associated with the current reversal event. It cannot be selected from an unrelated historical delivery leg. Causal association preserved: current reversal sequence → immediately preceding opposing delivery → initiating delivery candle → CISDReferencePrice.

## 7–10. Bullish / Bearish CISD & Equality
- Bullish: `Close_t > RelevantBearishDeliveryCandle.open` → `BULLISH_CISD_CONFIRMED`. If `Close_t = ReferencePrice` → FALSE (strict).
- Bearish: `Close_t < RelevantBullishDeliveryCandle.open` → `BEARISH_CISD_CONFIRMED`. If `Close_t = ReferencePrice` → FALSE (strict).

## 11. Wick-Only Penetration
Wick through the reference price does not confirm. Bullish: `High > ref` but `Close <= ref` → FALSE. Bearish: `Low < ref` but `Close >= ref` → FALSE. **CISD is body-close confirmed.**

## 12. Candle Color
Determined by close through reference price, **not** candle color. Do not replace the test with `Close > Open` / `Close < Open` alone.

## 13. CISD Does Not Require Qualifying Displacement
`CISD ≠ Displacement`. `QualifyingDisplacement = TRUE` is not an additional requirement inside #11 (the reversal architecture already requires qualifying counter-directional displacement upstream for MSS).

## 14. Displacement May Coincide With CISD
A CISD confirmation candle may independently qualify as displacement, producing both `DISPLACEMENT` + `BULLISH_CISD` as **separate event objects**. Neither is inferred automatically from the other.

## 15. CISD ≠ MSS
Absolute. MSS = structural event involving protected structure; CISD = delivery-state confirmation involving the relevant opposing delivery candle OPEN. Valid MSS does not imply CISD; valid CISD does not create MSS.

## 16. MSS Is Upstream for Reversal Entry #1
`MSS_CONFIRMED` must exist before #11 can advance the setup. A valid 1M CISD without the required setup MSS cannot arm Reversal #1 (remains, at most, a historical CISD observation).

## 17. Temporal Order
```
LRL_SELECTED → LRL_SWEPT → COUNTER_DIRECTIONAL_DISPLACEMENT → PROTECTED_SWING_BREAK
→ MSS_CONFIRMED → 1M_CISD_CONFIRMED → ENTRY_ZONE_SELECTION_ELIGIBLE → #28
```
Every confirmation must belong to that same setup sequence.

## 18. Same-Candle MSS + CISD
Permitted. Required relationship: `CISDConfirmationTime >= MSSConfirmationTime` at available data resolution. A separate later candle is not mandatory.

## 19. Same-Candle Evaluation Uses Frozen Pre-State
Evaluate against references that existed before the candle: `ProtectedSwingBefore(t)`, `CISDReferenceBefore(t)`. The candle cannot create a new delivery reference, break it, and claim CISD retroactively on itself. (Consistent with [[#16 Conflict Resolution — State Priority]].)

## 20. CISD Before MSS
`CISD time < MSS confirmation time` → cannot satisfy #11 for that reversal setup. Pre-MSS CISD = historical observation, NOT setup confirmation. Cannot reuse the earlier confirmation post-MSS.

## 21. Pre-Sweep CISD
A CISD before the qualifying LRL sweep is further removed; `OLD_CISD_INELIGIBLE` for the new reversal setup.

## 22. Setup-Specific Confirmation
Every accepted confirmation references `setup_id` (or the reversal-candidate ID). `CISDConfirmation_A` cannot automatically confirm `ReversalSequence_B` even if direction/price identical.

## 23. Confirmation Timestamp
`confirmation_time = Confirming1MCandle.close_time`. Known only at candle close (no look-ahead). No intrabar wick/temporary trade creates confirmed CISD.

## 24. Confirmation Price
Record `reference_price = RelevantDeliveryCandle.open` and `confirmation_close = ConfirmingCandle.close`. Must prove bullish `confirmation_close > reference_price` / bearish `confirmation_close < reference_price`.

## 25. Confirmation Direction
Must match the intended reversal setup. Bullish Reversal #1 → BULLISH CISD; bearish → BEARISH CISD. An opposing CISD cannot confirm.

## 26. Confirmation Does Not Select an Entry Zone
`CISD_CONFIRMED → ENTRY_ZONE_SELECTION_ELIGIBLE`. CONFIRMATION ≠ ENTRY ZONE ≠ ENTRY PRICE.

## 27–32. Relationship to FVG / IFVG (temporal eligibility boundary only)
#11 does not create/convert FVG/IFVG; it establishes the temporal eligibility boundary. Canonical rule: a 1M FVG/IFVG is eligible only if it exists as an eligible directionally compatible zone **at or after** the accepted confirmation event and is causally associated with the confirmation/reversal delivery (`ZoneEligibleTime >= CISDConfirmationTime`, subject to same-candle creation). An FVG created by the confirmation candle may be eligible once its third candle closes. A historical FVG existing **before** the accepted CISD does not automatically become the entry zone (no backward search for favorable entries). IFVG eligibility requires `IFVG.direction = setup.direction`; **#11 does not give IFVG priority over FVG — that priority belongs to #28**. Same-timestamp zone creation is allowed only if both events are independently confirmed from finalized information (no look-ahead / no circular dependency).

## 33–36. Persistence, Invalidation, Expiration, Opposing CISD
Once accepted, CISD is not reconfirmed every candle; it is a historical fact for that setup; setup remains `ENTRY_ZONE_SELECTION_ELIGIBLE` until a defined event invalidates/expires it. CISD is never retroactively erased; instead `SetupConfirmationStatus = TERMINATED` on upstream invalidation. #11 invents no independent N-candle/N-minute/ATR expiration timer. An opposing later CISD does not delete the accepted confirmation.

## 37. Delivery Reference Immutability
Once confirmed, `delivery_candle_id`, `reference_price`, `confirmation_candle_id`, `confirmation_close`, `confirmation_time`, `direction` are immutable. No later candle can re-select a "better" historical delivery candle.

## 38–39. Missing / Invalid Reference
Cannot identify the relevant opposing delivery candle → `RelevantDeliveryCandle = NONE`, `CISDReferencePrice = NONE`, `CISD = NOT_CONFIRMABLE` (no arbitrary older candle). Reference not opposing the required direction → `INVALID_CISD_REFERENCE`.

## 40. CISDConfirmation Object
```
CISDConfirmation {
  id; setup_candidate_id; timeframe (=1M); direction;
  delivery_leg_id; delivery_candle_id; delivery_candle_direction; reference_price;
  confirmation_candle_id; confirmation_close; confirmation_time; body_close_confirmed;
  associated_mss_id; associated_sweep_id; same_candle_as_mss;
  valid; active_for_setup; invalidation_time; invalidation_reason; historical; immutable
}
```

## 41–42. Bullish / Bearish Algorithm (summary)
Require valid associated MSS belonging to the current reversal sequence → identify the immediately preceding opposing (bearish/bullish) delivery leg → select its initiating candle → require correct direction → `CISDReferencePrice = candle.open` → for each eligible completed 1M candle at/after MSS confirmation, if `Close >/< CISDReferencePrice` → `CISD_CONFIRMED` (wick-only ignored, equality does not qualify) → store immutable confirmation → transition candidate to `ENTRY_ZONE_SELECTION_ELIGIBLE` → pass control downstream.

## 43. State Machine
```
MSS_CONFIRMED → WAITING_FOR_1M_CONFIRMATION → CISD_REFERENCE_IDENTIFIED
→ WAITING_FOR_BODY_CLOSE → CISD_CONFIRMED → ENTRY_ZONE_SELECTION_ELIGIBLE → #28
Failure: MSS_CONFIRMED → WAITING_FOR_1M_CONFIRMATION → SETUP INVALIDATED/EXPIRED → CONFIRMATION_TERMINATED
```
No entry is created by either path.

## 44. Hard Invariants
Timeframe = 1M · bullish CISD iff `1M Close > relevant bearish delivery Open` · bearish iff `1M Close < relevant bullish delivery Open` · equality → NO CISD · wick-only → NO CISD · `CISD ≠ MSS` · `CISD ≠ qualifying displacement` and #11 does not independently require displacement · pre-MSS / pre-sweep CISD cannot confirm · same-candle MSS+CISD permitted when both independently qualify · CISD opens zone-selection stage but `CISD ≠ FVG ≠ IFVG ≠ selected entry zone` · #11 cannot select FVG/IFVG/EQ/stop/target, calculate R, size, place, or fill.

## 45. Final Locked Definition
#11 is the 1M confirmation primitive used after the Reversal Entry #1 sequence has reached `MSS_CONFIRMED`. Bullish CISD is confirmed only when a completed 1M candle closes **strictly above** the OPEN of the mechanically selected relevant bearish delivery candle; bearish CISD only when a completed 1M candle closes **strictly below** the OPEN of the corresponding relevant bullish delivery candle. The reference candle is the candle initiating the immediately preceding opposing directional delivery associated with the current reversal sequence. Wick-only penetration and equality do not qualify. CISD is independent from displacement and MSS. For Reversal #1 the required MSS must already exist logically, though MSS and CISD may confirm on the same finalized 1M candle when both independently qualify. Historical CISDs before the qualifying sweep/MSS sequence cannot be reused. Once accepted, CISD makes the current reversal sequence eligible to proceed toward the post-confirmation 1M FVG/IFVG universe and #28; #11 never selects the zone, calculates EQ, chooses SL/TP, sizes, or executes.

## Dependencies
Upstream: [[#16 Conflict Resolution — State Priority]] (accepted MSS), [[#24 LRL Selection]] (REVERSAL_SWEEP_REFERENCE). Downstream: [[#28 Entry-Zone Selection]].

## Amendment Overrides
Consistent with [[Amendment 005A]] (fills the "required 1M confirmation" between `MSS_CONFIRMED` and #28). Enums/outcomes registered per [[Amendment 003]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`CISDConfirmation`) · [[Canonical Enum Registry]] · [[Canonical Error Registry]] (`NOT_CONFIRMABLE`, `INVALID_CISD_REFERENCE` are non-confirmation outcomes, not infrastructure errors).

## Tests
See [[Primitive Test Matrix]] and [[Golden Scenarios]] (#11 rows).

## Historical Source
[[Appendix A — Recovered Historical Transcript]]
