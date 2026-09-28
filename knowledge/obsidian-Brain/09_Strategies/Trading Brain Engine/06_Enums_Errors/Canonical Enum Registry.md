---
title: Canonical Enum Registry
governing_amendments: ["003"]
---

# Canonical Enum Registry (Amendment 003)

Closed enums. Do not invent `UNKNOWN` / `OTHER` / `GENERIC_ERROR` / generic states.

## Structural / Market
- `StructuralRegime { INITIALIZING, BULLISH, BEARISH, TRANSITION }` â€” **persisted set**. `CONFLICTED` / `NEUTRAL` are **not** persisted members (non-persisted diagnostic; see [[#16 Conflict Resolution â€” State Priority]] Â§22, [[#20 Structural Classification]]).
- `LiquidityState { ACTIVE, VIOLATED, SWEPT, BROKEN, CONSUMED }` Â· `LiquiditySide { BSL, LSL }`
- `LRLRole { CONTINUATION_TARGET, REVERSAL_SWEEP_REFERENCE }`
- `StructuralClassification { HH, LH, HL, LL, EQUAL_HIGH, EQUAL_LOW, UNCLASSIFIED }` (Amendment 003, confirmed by [[Amendment 006]]) - #20 same-type structural classification.
- `FVGState { ACTIVE, MITIGATED, VIOLATED, INVERTED }`

## Setup / Entry / Execution
- `SetupModel { CONTINUATION, REVERSAL_1 }`
- `ContinuationSetupState { CANDIDATE, ARMED, REJECTED, ... }`
- `ReversalSetupState { MSS_CONFIRMED, ENTRY_ZONE_ARMED, ... }`
- `EntryZoneType { FVG, IFVG }` Â· `EntryZoneSelectionState`
- `OrderType`, `OrderSide`, `OrderState`
- `ExecutionEligibilityState { EXECUTION_EVALUATING, EXECUTION_ELIGIBLE, EXECUTION_INELIGIBLE, DATA_ERROR }`
- `TradeState { TRADE_AUTHORIZED, AUTHORIZATION_REVOKED, ORDER_PENDING, ORDER_WORKING, PARTIALLY_FILLED, FILLED, POSITION_OPEN, POSITION_MANAGING, EXIT_PENDING, CLOSED, UNFILLED, RECONCILIATION_REQUIRED }`
- `ExecutionDataQuality { OBSERVED, ESTIMATED, NOT_MEASURED }`
- `ExitReason { STOP_LOSS, TARGET, STOP_LOSS_GAP, OHLC_AMBIGUOUS_STOP_PRIORITY }`
- CISD state machine ([[#11 CISD â€” 1M Confirmation]]): `WAITING_FOR_1M_CONFIRMATION, CISD_REFERENCE_IDENTIFIED, WAITING_FOR_BODY_CLOSE, CISD_CONFIRMED, CONFIRMATION_TERMINATED`
- Position state ([[#29.6 Position Lifecycle]]): `NOT_OPEN, OPEN, CLOSED`

## Confluence / Analytics
- `ConfluenceType`, `ConfluenceCategory`, `ConfluenceResult`
- `PeriodType { DAILY, WEEKLY, MONTHLY, FULL_HISTORY }` Â· `CalculationMode`
- `ExpectancyStatus`, `ProfitFactorStatus`, `StreakDirection`, `StreakStatus`, correlation/covariance status enums

## #16 Diagnostic Enums (owner-authorized additive â€” LOCKED_PENDING_REGISTRY)
- `SuppressionReason { OPPOSING_MSS_STATE_PRIORITY, ... }` Â· `ConflictType` Â· `ResolutionRule`

See [[Amendment 003]], [[Canonical Error Registry]].

