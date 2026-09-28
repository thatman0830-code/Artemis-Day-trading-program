---
title: Runtime Configuration Registry
type: configuration
---

# Runtime Configuration Registry

These are **CONFIGURABLE RUNTIME VALUES**, not missing trading logic. See [[Configuration vs Logic Boundary]]. Do not select runtime numbers that were never locked in source.

## Account / Time
- `AccountTimezone` — mandatory ([[Time — Period Policy]])
- session calendar — if used (sessions are not accounting boundaries)

## Instrument
- `minimum_tick`
- `tick_value`
- `contract_multiplier`
- `minimum_quantity`
- `quantity_increment`

## Risk
- `RiskPercent` — consumed by [[#29.2 Position Sizing]]

## Costs ([[#29.5 Execution Costs]])
- `CommissionModel` + values
- `TransactionFeeModel` + values
- `SpreadModel` + values
- `SlippageModel` + values

The same versioned spread/slippage/fee models feed the pre-trade estimate in [[#29.0 Execution Eligibility]] and realized costs in #29.5. Estimated and realized values remain distinct; a cost embedded in price is never charged again as cash.

## Execution Eligibility ([[#29.0 Execution Eligibility]])
- mandatory execution-input policy (which fields may be `ESTIMATED` versus fail-closed `NOT_MEASURED`)
- available-liquidity/size model — only when supported by observed data
- material-change thresholds requiring re-evaluation before submission
- minimum executable R = `2.0` unless an existing stricter rule applies

## Statistics
- `annualization = 252`
- `risk_free = 0%`
- covariance calculation mode ([[#29.7.2.20 Strategy Return Covariance]])
- rolling window — where applicable

## Structure / Liquidity (canonical constants; configurable only where source permits)
- swing = `2L / 2R` ([[#19 Mechanical Swing Selection]])
- liquidity equality tolerance = `1 tick` ([[#23 Liquidity — Sweeps]])
- approaching-LRL band = `0.25 × ATR(14)` — if still canonical/configured
- displacement: `DISPLACEMENT_THRESHOLD`, `DISPLACEMENT_METHOD` — status `CONFIGURABLE / PENDING VALIDATION` if that remains authoritative

## Strategy / Portfolio
- strategy `starting_equity`; portfolio `starting_equity` (explicit; never inferred — else `PORTFOLIO_STARTING_EQUITY_MISSING`)

Classification for all of the above: **CONFIGURATION_REQUIRED_BEFORE_RUNTIME** (not `MISSING_TRADING_LOGIC`).
