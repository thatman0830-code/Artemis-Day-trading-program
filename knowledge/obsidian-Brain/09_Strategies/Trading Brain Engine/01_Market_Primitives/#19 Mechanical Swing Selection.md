---
primitive_id: "#19"
title: Exact Mechanical Swing Selection
status: LOCKED_AND_IMPLEMENTABLE
source_type: canonical-implementation-spec
governing_amendments: []
upstream: ["Market data"]
downstream: ["#20 Structural Classification"]
historical_source_preserved: true
implementation_ready: true
---

# #19 â€” Exact Mechanical Swing Selection

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns detection of raw mechanical swing highs/lows. Does not classify structure (that is [[#20 Structural Classification]]).

## Canonical Definition
2-left / 2-right mechanical fractal.
- **Mechanical Swing High** = a *closed* candle whose high is **strictly greater** than the highs of the 2 preceding and 2 following closed candles.
- **Mechanical Swing Low** = a *closed* candle whose low is **strictly less** than the lows of the 2 preceding and 2 following closed candles.
- Equal highs/lows are **not** swings.
- Requires 2 confirming candles after the pivot.
- Timeframe-independent; output feeds all structural/bias calculations.

## Inputs
Closed OHLC candles for the working timeframe.

## Outputs
`MechanicalSwing { id, timeframe, type(H/L), price, pivot_time, confirmed }`.

## Hard Invariants
- strict `>` (highs) / `<` (lows); equal extremes excluded
- 2 candles of confirmation required after the pivot
- timeframe-independent
- no look-ahead: a swing is confirmed only after its right-side candles close

## Owner Ruling - Dual Mechanical Swing Candle (additive clarification)

A single completed candle MAY qualify simultaneously as `MECHANICAL_SWING_HIGH` and `MECHANICAL_SWING_LOW`, provided each condition independently satisfies the strict 2-left/2-right rule. The two predicates are evaluated independently; there is NO #19 mutual-exclusivity rule.

```
SwingHigh(i) = High[i] > High[i-1] and High[i] > High[i-2] and High[i] > High[i+1] and High[i] > High[i+2]
SwingLow(i)  = Low[i]  < Low[i-1]  and Low[i]  < Low[i-2]  and Low[i]  < Low[i+1]  and Low[i]  < Low[i+2]
```

`SwingHigh(i) = TRUE and SwingLow(i) = TRUE` is a legal #19 result. #19 must NOT use candle color, body direction, range magnitude, distance from neighboring pivots, high-vs-low priority, first/later-event priority, structural regime, protected structure, BOS/MSS, or liquidity to choose one over the other. If both qualify, create two distinct immutable `MechanicalSwing` records for the same pivot candle/timeframe (one `type=H`, one `type=L`), each with its own deterministic identity. This ruling governs #19 mechanical observation only; [[#20 Structural Classification]] remains independently governed. Test: `TB_19_DUAL_001`.
## Dependencies
Upstream: Market data. Downstream: [[#20 Structural Classification]].

## Amendment Overrides
NONE

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`MechanicalSwing`).

## Tests
[[Primitive Test Matrix]] Â· [[Golden Scenarios]] (strict mechanical swing comparison; equal-high/equal-low exclusion).

## Historical Source
[[Appendix A â€” Recovered Historical Transcript]] (transcript "#7 â€” LOCKED").

