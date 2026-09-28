---
title: Amendment 005A
status: ACTIVE
precedence: OWNER_RESOLUTION
appendix_modified: false
resolves: [reversal-liquidity-side, "27-28-state-boundary"]
---

# Owner Resolution Amendment 005A — Reversal Liquidity Side + #27/#28 State Boundary

Internal-consistency resolution. Precedence tier 1. Appendix A unmodified. Selects the canonical rule where two recovered statements conflict; clarifies #27/#28 ownership. Does not redesign the strategy.

## 1. Reversal Entry #1 — Canonical Liquidity Side
Reversal Entry #1 sweeps liquidity in the direction of the **existing regime's extension**, then reverses via counter-directional MSS.

```
Bearish regime → REVERSAL_SWEEP_REFERENCE = LSL → bullish displacement → protected-high break → bullish MSS
Bullish regime → REVERSAL_SWEEP_REFERENCE = BSL → bearish displacement → protected-low break → bearish MSS
```

**Supersedes** the historical transcript "Reversal-specific LRL" block (~lines 3439–3467) which stated *bearish→BSL / bullish→LSL* — for `REVERSAL_SWEEP_REFERENCE` selection only. Continuation target rules are **unchanged**: bullish continuation → BSL target; bearish continuation → LSL target.

`LRLRole`: `CONTINUATION_TARGET {bullish→BSL, bearish→LSL}` and `REVERSAL_SWEEP_REFERENCE {bearish→bullish→LSL, bullish→bearish→BSL}` are **distinct lifecycle roles**. The post-MSS reversal target is reselected using the new regime's continuation-direction target logic.

## 2. #27 / #28 Circular Dependency — Resolved
Canonical ownership sequence:

```
#27 structural/sequence qualification
  → entry-zone-selection-eligible state
  → #28 select exactly one eligible zone, compute/freeze EQ
  → #27 final executability revalidation (Entry + Stop + Target + ≥2R)
  → executable armed state
```

**#28 does not require `ARMED`.** It requires the owning model's entry-zone-selection-eligible state:
- **Continuation:** `ContinuationSetupState = CANDIDATE` + mandatory pre-zone prerequisites. Post-#28: valid → `ARMED`; `R<2` → `REJECTED`; no eligible zone → remain `CANDIDATE`.
- **Reversal #1:** `ReversalSetupState = MSS_CONFIRMED` + required 1M-confirmation prerequisites. Post-#28 + #27 confirm: `MSS_CONFIRMED → ENTRY_ZONE_ARMED`.

No new persisted enum member introduced. The historical `IF Setup.state != ARMED: #28 does nothing` is **superseded**; do not restore it.

## 3. ≥2R Ownership
Authoritative final ≥2R decision belongs to **#27** after one zone is selected; #28 may only pre-filter obviously non-viable zones. `Risk = abs(Entry − Stop)`, `Reward = abs(Target − Entry)`, `R = Reward/Risk`; `R ≥ 2` → may arm, `R < 2` → REJECTED. No farther target may be chosen to manufacture ≥2R.

Affected: [[#24 LRL Selection]], [[#27 Setup Qualification]], [[#28 Entry-Zone Selection]], [[#13 Stop-Loss Selection]], [[#11 CISD — 1M Confirmation]].
