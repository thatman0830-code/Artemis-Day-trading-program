---
title: Amendment 003
status: ACTIVE
precedence: OWNER_RESOLUTION
appendix_modified: false
resolves: [R4]
---

# Owner Resolution Amendment 003 — Global Enum / Error Taxonomy

Resolves R4. Precedence tier 1. Appendix A unmodified. See [[Canonical Enum Registry]], [[Canonical Error Registry]], [[Error Precedence — Fail Closed]].

## Principles
- Use canonical **closed** enums. Do not invent `UNKNOWN` / `OTHER` / `GENERIC_ERROR`.
- `DATA_INTEGRITY_ERROR` has **absolute precedence** for ambiguous canonical datasets.
- Error records are **immutable**. No error may rewrite history.
- "No qualifying analytical observation" is **not** automatically an error.
- "No trade / no fill" is **not** an error.

## Frozen enum families (representative)
`record_kind`, `confirmation_status`, `execution_state`, `StructuralRegime {INITIALIZING, BULLISH, BEARISH, TRANSITION}`, `LiquidityState {ACTIVE, VIOLATED, SWEPT, BROKEN, CONSUMED}`, `LiquiditySide {BSL, LSL}`, `LRLRole {CONTINUATION_TARGET, REVERSAL_SWEEP_REFERENCE}`, `FVGState`, `SetupModel {CONTINUATION, REVERSAL_1}`, `ContinuationSetupState`, `ReversalSetupState`, `EntryZoneType {FVG, IFVG}`, `EntryZoneSelectionState`, `OrderType`, `OrderSide`, `OrderState`, `ExitReason {STOP_LOSS, TARGET, STOP_LOSS_GAP, OHLC_AMBIGUOUS_STOP_PRIORITY}`, `ConfluenceType/Category/Result`, `PeriodType {DAILY, WEEKLY, MONTHLY, FULL_HISTORY}`, `CalculationMode`, correlation/covariance/expectancy/profit-factor/streak status enums.

## Error taxonomy (severity-tagged, precedence-ordered, fail-closed)
`DATA_INTEGRITY_ERROR` (absolute), `ACCOUNTING_ERROR`, `POSITION_SIZE_INVALID`, `PROTECTIVE_ORDER_INVALID`, `TARGET_ORDER_INVALID`, `EXECUTION_COST_INVALID`, plus `ErrorRecord` structure and error precedence.

## Notes
- Amendment 003 does **not** invent emergency position-close behavior (deferred to execution primitives).
- Setup-state enums are frozen; their transition **rules** are owned by the setup primitives (#27/#28) and #11.

Later owner-authorized additive additions (housekeeping, non-conflicting): `STOP_SELECTION_INVALID` (#13), `ACTIVE_RANGE_INVALID` (#21), `PORTFOLIO_STARTING_EQUITY_MISSING` (#29.7.2.16); #11 non-confirmation outcomes `NOT_CONFIRMABLE` / `INVALID_CISD_REFERENCE`; #16 `CandidateEvent`, `ConflictResolution`, `SuppressionReason`, `ConflictType`, `ResolutionRule`.
