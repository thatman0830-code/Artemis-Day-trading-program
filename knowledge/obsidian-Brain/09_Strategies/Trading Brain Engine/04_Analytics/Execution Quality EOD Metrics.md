---
title: Execution Quality EOD Metrics
type: analytics-spec
status: LOCKED_CONFIGURATION_REQUIRED
governing_amendments: ["007"]
---

# Execution Quality EOD Metrics

## Purpose and Boundary

Measures execution quality separately from setup quality. This read-only layer consumes immutable [[Execution Entity Hierarchy|Setup, Trade, Order, and Fill]] records plus [[#29.0 Execution Eligibility]] evaluations, [[#29.5 Execution Costs]], [[#29.6 Position Lifecycle]], and finalized [[#29.7.1 Trade Accounting]]. It never changes upstream records or fabricates missing values.

## Per-Record Fields

- identity: `setup_id`, `trade_id`, `order_ids`, `fill_ids`, instrument, direction
- timestamps: setup, authorization, submission, first fill, final fill, exit
- price plan: theoretical entry, expected executable entry, actual average entry, planned stop, initial actual stop, planned target
- opportunity: theoretical setup R, expected executable R, actual initial R available after fill
- execution: entry/exit slippage, spread at evaluation/submission, fees/costs, requested/filled quantity, fill ratio, entry order/fill counts, time to first/complete fill
- outcome: cancellation/rejection/ineligibility reason, MFE/MAE when supported, realized R, realized P&L
- controls: setup-valid, execution-eligible, rule-compliance, data-quality/missing-data flags

Unknown values are `NOT_MEASURED`, not zero.

## Derived Metrics

```text
FillRatio = FilledQuantity / RequestedQuantity
ExecutionRDegradation = ExpectedExecutableR - ActualInitialRAvailable
```

Entry and exit slippage use a direction-aware convention: positive means adverse and negative means favorable.

```text
LongEntrySlippage  = ActualAverageEntry - ExpectedExecutableEntry
ShortEntrySlippage = ExpectedExecutableEntry - ActualAverageEntry
```

Equivalent direction-aware logic applies to exits. Price friction already embedded in economic prices is not recharged as a cash cost.

## EOD Aggregates

- valid setups that were execution-eligible
- authorized trades receiving any fill
- average adverse entry slippage and execution-R degradation
- cancellation, rejection, partial-fill, and rules-compliant execution rates
- realized R/P&L grouped by setup quality and execution quality

Denominators and missing-data populations must be disclosed. Valid no-trade outcomes remain visible and are not treated as errors.

## Links

Operational capture: [[_Trade Template]]. Dashboard: [[Trading Statistics]]. Supporting rationale: [[Polymarket Bot Execution and Inventory Management Analysis]].

