---
primitive_id: "#24"
title: Exact Mechanical LRL Selection
status: LOCKED_AND_IMPLEMENTABLE
source_type: canonical-implementation-spec
governing_amendments: ["005A"]
upstream: ["#23 Liquidity", "#21 Active Dealing Range", "#20"]
downstream: ["#27 Setup Qualification (target)", "#11 (reversal sweep reference)"]
historical_source_preserved: true
implementation_ready: true
---

# #24 — Exact Mechanical LRL Selection

## Status
LOCKED_AND_IMPLEMENTABLE

## Ownership
Owns selection of the single active LRL from unconsumed liquidity, its lifecycle role, and the ≥2R target gate handoff. Consumes liquidity from [[#23 Liquidity — Sweeps]] and the active range from [[#21 Active Dealing Range]].

## Canonical Definition
`LRL = the single active liquidity pool selected from all unconsumed liquidity` per the setup's required side, current price position, active dealing range, and deterministic priority.
- **External > Internal (absolute).** If no external, nearest eligible internal (no external ≠ LRL NONE).
- `CONSUMED = ineligible`. Directional eligibility by regime.
- `TRANSITION` terminates the old-range LRL (no inheritance).
- **Persistence:** once selected, fixed — no per-candle reselection — until consumed / setup invalidated / MSS / range replacement.
- **≥2R gate:** if the nearest structural target cannot yield ≥2R, return No-Target → No-Trade (never select a farther target to manufacture ≥2R). *Authoritative ≥2R decision belongs to [[#27 Setup Qualification]] once entry/stop exist.*

## LRL Roles (Amendment 005A)
- `CONTINUATION_TARGET`: bullish → BSL; bearish → LSL.
- `REVERSAL_SWEEP_REFERENCE`: bearish→bullish → **LSL**; bullish→bearish → **BSL**.
- These are distinct lifecycle roles. The post-MSS reversal **target** is reselected using the new regime's continuation-direction target logic. Supersedes the historical `bearish→BSL / bullish→LSL` reversal mapping.

## Hard Invariants
- External > Internal (absolute); `CONSUMED` ineligible
- no per-candle reselect; `TRANSITION` terminates old LRL
- ≥2R gate — never select a farther target to manufacture ≥2R
- LRL selection ≠ LRL sweep (distinct state transitions)

## Dependencies
Upstream: [[#23 Liquidity — Sweeps]], [[#21 Active Dealing Range]], [[#20 Structural Classification]]. Downstream: [[#27 Setup Qualification]] (target), [[#11 CISD — 1M Confirmation]] (reversal sweep reference), [[#29.3 Protective Orders]] (target price).

## Amendment Overrides
`REVERSAL_SWEEP_REFERENCE` mapping per [[Amendment 005A]].

## Canonical Objects / Enums / Errors
[[Canonical Object Registry]] (`LRL`) · [[Canonical Enum Registry]] (`LRLRole`).

## Tests
[[Primitive Test Matrix]] · [[Golden Scenarios]] (2R rejection; external>internal).

## Historical Source
[[Appendix A — Recovered Historical Transcript]] (transcript "31. Final locked definition").
