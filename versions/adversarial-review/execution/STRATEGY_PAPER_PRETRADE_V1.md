# Pre-fill strategy sizing and V2 risk integration

Status: offline, caller-driven, advisory only. No session launch, gateway submission,
fill creation, protective-order installation, or operational configuration change.

The planner consumes verified paper performance and gateway snapshots, a supplied
portfolio risk context, V2 limits/session, an explicit sizing policy and the frozen
inputs accepted by the strategy-intent compiler. It computes quantity before any
fill and then calls the existing V2 pretrade evaluator. It does not repurpose the
strategy #29.2 post-fill sizing record as pre-order authorization.

## Sizing

Sizing policy has no operational defaults: effective interval, equity risk fraction,
maximum planned loss, fixed cost allowance, per-unit cost allowance and source
evidence hash are mandatory. Zero cost allowance is permitted only as an explicit
input; supplying it does not establish that costs are actually zero or approved.

For a long spot entry, planned per-unit risk is entry-minus-stop times multiplier,
plus the supplied per-unit cost allowance. The fixed allowance is subtracted from
the smaller of equity-times-risk-fraction and maximum planned loss. Quantity is
also capped by cash affordability including allowances, the existing bounded
100-quote-currency order-notional cap, and the configured position-quantity limit.
The smallest capacity is rounded down to whole quantity steps using exact rational
arithmetic. Sub-step budgets reject, never round upward to force a trade.

`planned_stop_loss_with_allowances` is a model, not a guaranteed maximum loss:
gaps, unavailable execution and actual fees can exceed the supplied assumptions.
`reserved_cash` is a calculated amount, not a durable reservation or deducted cash.

## Reconciliation and gates

- Accounting integrity is verified; the performance checkpoint must already bind
  the exact current gateway snapshot and reconcile all retained fill quantities.
- Gateway must be connected without kill-switch/reconciliation requirements.
  Outstanding orders reject rather than assume zero reserved exposure.
- Initial supported scope is one flat BTC spot account, with matching equity,
  zero gross/net exposure and exactly the current accounting snapshot as context
  source. Accounting and portfolio observations must be no more than five seconds
  old. Position-availability time must match accounting time.
- Session-loss/drawdown thresholds and existing margin breach block new proposals.
  Policy, margin and session/flatten-buffer coverage must extend through intent
  expiry. Existing V2 checks retain exposure, concentration, leverage and margin
  rejection reasons. A rejection is never converted to ALLOW.
- The qualified strategy is recompiled using the computed quantity. Policy,
  context, validated session identity, source bar identity, source snapshot hash,
  versions and computed economics are bound into the result identity.

`risk_eligible` reports only the V2 risk decision. `submission_authorized` and
`trading_authority` always remain false, including for eligible results. The planner
does not bypass launch, clock, source-data, protective-lifecycle or owner gates.

## Trust and remaining integration

Typed caller inputs are not an authenticated external evidence boundary. Session
reference/peak equity must come from retained verified history, not be reset by the
caller. Sizing-policy evidence must be reviewed for deployment. A hash does not
prove owner approval, provider facts, or source-to-strategy reconstruction.

The planner does not read current runtime, install a durable authorization/reservation
record, deduplicate strategy setups, or serialize a trustworthy executable permit.
Consumers must revalidate against current state before any submission. In-memory
outputs must not be accepted as authenticated records merely because they are frozen.

Tests cover the real strategy compiler and V2 risk evaluator using synthetic
fixtures: exact sizing/grid boundaries, cash including costs, deterministic identity,
V2 rejections, stale/conflicting context, policy coverage, outstanding orders and
disconnected gateways. No real market signal, fill, cost or profitability is claimed.

Next: durable paper submission/reservation binding and protective lifecycle, then
V2 execution-fill and cost integration. Real source acquisition and a supervised
runtime demonstration remain required. Local tests are not a Hermes audit.
