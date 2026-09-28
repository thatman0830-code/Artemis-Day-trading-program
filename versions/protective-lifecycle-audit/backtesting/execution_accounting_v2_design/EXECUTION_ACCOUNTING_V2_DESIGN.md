# Backtesting Execution and Accounting v2 Design

Design version: `execution-accounting-v2-design-1`  
Status: design only; no executable v2 engine exists.

V2 is a separate provider-neutral simulation contract. It consumes immutable, point-in-time market,
session, rollover, funding, mark, instrument, cost, and strategy-action facts and emits immutable
simulation ledgers. It has no provider, recorder, broker, wallet, signing, paper-trading, or live-order
path. Core v1 remains independently runnable and its results are never reinterpreted as v2.
Every boundary enforces strict no-look-ahead: a fact is eligible only at or after its immutable
availability timestamp, never merely at its economic occurrence timestamp.

## 1. Order model

Order types are `MARKET`, `LIMIT`, `STOP_MARKET`, and `STOP_LIMIT`. Time-in-force is `DAY`, `GTC`, or
`IOC`. Order intents additionally identify normal entry/exit, strategy reduction, risk flatten,
session flatten, end-of-data liquidation, and rollover outgoing/incoming legs.

Every `OrderIntentV2` is frozen and contains:

- deterministic ID = SHA-256 of schema version, run, strategy/action, market, exact instrument and
  contract, side, quantity, type, TIF, prices, submission/activation/expiry times, policy versions,
  parent/replacement/rollover identities, and source facts;
- UTC submission time, activation time, first eligible event identity, optional DAY expiry, exact
  Decimal quantity and prices, and immutable owner/configuration versions;
- parent/child and `replaces_order_id`/`replaced_by_order_id` lineage;
- initial quantity; remaining quantity is derived from immutable fills, never edited in place.

States are:

`CREATED -> SUBMITTED -> ACTIVE -> [TRIGGERED] -> PARTIALLY_FILLED -> FILLED`

Terminal alternatives are `REJECTED`, `CANCELLED`, `EXPIRED`, and `REPLACED`. `CANCEL_REQUESTED` is
non-terminal. A stop-limit moves from `ACTIVE` to `TRIGGERED`, then becomes fill-eligible only on a
later market bar. Forced liquidation and rollover use ordinary immutable orders with explicit intent
types; they are not magic position mutations.

Replacement creates a new child order. The original transitions to `REPLACED`; its history, fills,
fees, and remaining quantity remain auditable. Reuse of an order ID with different content is fatal.

| Current | Event | Next | Guard |
|---|---|---|---|
| CREATED | submit | SUBMITTED | pre-trade risk and capability pass |
| SUBMITTED | activation time reached | ACTIVE | valid session/data/instrument |
| ACTIVE | stop condition | TRIGGERED | stop order only; immutable trigger fact |
| ACTIVE/TRIGGERED | eligible execution | PARTIALLY_FILLED/FILLED | volume and price rules pass |
| PARTIALLY_FILLED | eligible execution | PARTIALLY_FILLED/FILLED | remaining quantity positive |
| SUBMITTED/ACTIVE/TRIGGERED/PARTIALLY_FILLED | cancel accepted | CANCELLED | preserves fills |
| ACTIVE/TRIGGERED/PARTIALLY_FILLED | DAY boundary | EXPIRED | residual remains unfilled |
| ACTIVE/TRIGGERED/PARTIALLY_FILLED | replace accepted | REPLACED | child identity recorded |
| any non-terminal | invalid prerequisite | REJECTED | only before any fill; otherwise cancel residual |

Terminal states cannot transition. IOC evaluates once on its first eligible bar and cancels residual.
DAY expires at the verified session expiry boundary. GTC carries only while the exact contract and
declared policy remain eligible.

## 2. Frozen one-minute execution policy

Default: `CONSERVATIVE_OHLC_1M_V1`.

- A decision using finalized bar t can create an order at t close; it cannot fill on t.
- The first possible fill uses a later eligible bar. Market orders use that bar's open plus adverse
  slippage: buy rounds upward, sell rounds downward to the tick grid.
- Buy limits fill at the limit or lower, but this model records the limit (no favorable improvement).
  Sell limits fill at the limit or higher, but records the limit.
- A buy limit does not fill if the next observable price is above the limit and the bar never reaches
  it. A sell limit is the inverse.
- Buy stop-market: if the next eligible open is at/above the stop, fill from open plus adverse
  slippage; otherwise a bar high at/above stop fills from stop plus adverse slippage. Sell is inverse.
- Stop-limit trigger and fill are separate immutable events. The trigger bar cannot also fill the
  limit. The triggered order first evaluates its limit on the next eligible bar.
- No order fills on a missing bar, data-quality halt, maintenance interval, closure, invalid session,
  wrong contract, stale datum, or after contract eligibility ends.
- A protective stop and favorable threshold both touched in one OHLC bar use the adverse stop path.
  If no adverse/favorable ownership is declared, emit `AMBIGUOUS_INTRABAR_REJECTED`.
- Every `FillV2` records `execution_rule_code`, trigger/market bar IDs, unrounded basis, tick-rounded
  price, slippage, volume allocation, and all policy versions.

Tick rounding uses exact Decimal division. Buy prices round toward positive infinity and sell prices
toward negative infinity whenever a modeled value is off grid. This is deliberately adverse.

Detailed truth tables are in `OHLC_FILL_TRUTH_TABLES.md`.

## 3. Liquidity and partial fills

Default: `BAR_VOLUME_PARTICIPATION_V1`.

For each exact instrument/contract/bar:

`available_quantity = floor_to_quantity_step(bar_volume * maximum_participation_rate)`

The volume budget is shared by all orders. Priority is deterministic:

1. risk/session/end liquidation;
2. rollover outgoing close;
3. ordinary position-reducing orders;
4. strategy exits;
5. entries and rollover incoming opens;
6. `(activation_time, submission_time, order_id)`.

Fills consume the budget once. Zero volume produces no fill. Missing volume rejects the run before
replay when partial fills are required. Quantity is rounded down to the configured step; contracts
are integer when the instrument specification says so. IOC residual cancels immediately, DAY
residual expires at session boundary, and GTC residual carries with unchanged identity. OHLCV cannot
model queue position, hidden liquidity, impact, or order-book priority; every result using this model
must carry `OHLCV_LIQUIDITY_LIMITATION=true`.

## 4. Session-flat policy

Default: `VERIFIED_SESSION_FLAT_V1`, optional per strategy/market but mandatory when declared.

- Owner configuration supplies an offset before the verified session close, with calendar version.
- At the first finalized decision event at/after the deadline, a `SESSION_POLICY_FLATTEN` market
  intent is created. It can fill only on a later eligible bar before close.
- Early-close calendars replace the ordinary close before replay; no date is inferred.
- Missing final eligible data leaves an explicit residual and fails the run with
  `SESSION_FLATNESS_UNPROVEN`.
- Maintenance and closure bars are ineligible. Partial residuals continue only until the last valid
  bar; they are never silently marked flat.
- Normal strategy exits, risk-forced flatten, session flatten, and `END_OF_DATA_ACCOUNTING_LIQUIDATION`
  retain distinct intent/reason codes.
- End-of-data liquidation is an accounting-only conservative terminal mechanism and must be enabled
  explicitly. It uses a declared adverse valuation, costs, and `LIQUIDATED_FOR_ACCOUNTING_ONLY`; it
  is never described as an executable fill. Default is to fail if flatness cannot be proven.

## 5. Futures rollover

Default: `CLOSE_THEN_OPEN_ROLLOVER_V1` using exact frozen ES/NQ contract IDs and effective timestamps.

- At effective rollover, create separate outgoing `ROLLOVER_CLOSE` and incoming `ROLLOVER_OPEN`
  intents. Prices are never transferred or adjusted.
- Default sequencing is close-first: no incoming order activates until the outgoing position is
  completely filled and accounted. Temporary flat exposure is expected and conservative.
- Each leg has its own bars, quantity allocation, fills, fees, slippage, margin, and attribution.
- Missing/invalid outgoing data fails closed. Missing incoming data leaves the account flat and marks
  rollover incomplete; it never restores the outgoing position after its allowed window.
- Partial outgoing fills prohibit a larger incoming position. Alternative proportional overlap is
  rejected for the default version.
- The intent is logically paired but market execution is non-atomic. Ledgers record pair, leg,
  decision, effective time, temporary exposure, and completion status.
- Participation has an owner-configured rollover cap no greater than the normal bar cap.
- A strategy holding an outgoing contract beyond its active window without a declared compatible
  rollover/mandatory-close policy is rejected before replay.

## 6. Futures accounting and margin

All economic inputs are versioned owner facts. Missing tick size, point value, currency, quantity
step, multiplier convention, margin, commission, exchange/regulatory fee, or effective date rejects
the run. Fixture values are not current broker/exchange claims.

For signed quantity `q`, price `P`, average/settlement reference `A`, point value `V`:

- `unrealized = q * (P - A) * V`
- reduction realized P&L = `closed_abs_qty * (fill - A) * V * sign(q_before)`
- fill notional for fee basis = `abs(fill * quantity * multiplier)` only when the cost specification
  explicitly declares notional basis;
- equity = cash + realized_unsettled + unrealized - accrued_costs + funding/credits;
- initial margin reserved = sum `abs(q) * initial_margin_per_contract`;
- maintenance requirement = sum `abs(q) * maintenance_margin_per_contract`.

Adds use quantity-weighted average price on the same side. Reductions retain the prior average.
Cross-zero reversal realizes the closed side and starts the residual at the fill. Flat positions have
zero quantity, average, unrealized P&L, exposure, and reserved margin.

At a verified variation-settlement event, unrealized P&L transfers exactly once to cash, cumulative
realized attribution is preserved, and the settlement price becomes the new reference. No economic
P&L is created. A margin call occurs when eligible equity is below maintenance requirement. Forced
reduction/liquidation uses normal future eligible bars and costs; absent data leaves an unresolved
breach and fails closed.

Every accounting snapshot must satisfy the formulas in `ACCOUNTING_INVARIANTS.md` and reconcile by
portfolio, market, contract, strategy, session, and cost category.

## 7. BTC boundary

Profiles are mutually exclusive:

- `BTC_SPOT_V1`: base-asset quantity, quote cash exchanged at fills, versioned fees, no funding,
  no futures multiplier or CME session/rollover.
- `BTC_LINEAR_PERPETUAL_V1`: exact notional/contract convention, verified mark series, funding event
  timestamps/rates, margin mode, leverage, maintenance/liquidation rules, and fees are mandatory.
- `BTC_UNKNOWN_UNSUPPORTED`: default for an archive that does not prove economics.

Spot cash change for buy is `-(quantity * price) - costs`; sell is the inverse. Spot equity is quote
cash plus base quantity times verified valuation price. A linear perpetual uses its owner-specified
multiplier and derivative P&L convention. Funding cash flow is versioned but follows the declared
canonical sign, e.g. `-signed_position_notional * funding_rate` only if the instrument specification
defines that basis.

Without verified mark, funding, and instrument metadata, perpetual claims are rejected. A mechanical
test may be allowed only when explicitly flat before every possible funding boundary. The current
partial BTC archive is smoke-only and never eligible for final OOS acceptance.

## 8. Risk v2 and event priority

Pre-trade controls run after an action but before order submission. Post-event controls run after
fills and accounting. Same-timestamp order is:

1. data-quality/session/closure state;
2. rollover/funding/variation-settlement facts;
3. finalized market data;
4. strategy evaluation and actions;
5. pre-trade risk and order submission/activation;
6. trigger and fill allocation;
7. fees, cash, position, margin, and mark-to-market accounting;
8. post-event risk and forced-action intents (eligible only later);
9. reporting.

Data-quality halt wins over all strategy actions. Risk checks cover maximum position, gross/net
exposure, initial/maintenance margin, session loss, drawdown, stale/missing data, order rate,
participation, session flatness, rollover failure, and end residuals. Codes are frozen in
`RISK_REASON_CODES.json`.

## 9. Session and attribution accounting

ES/NQ use verified exchange-session IDs with both UTC and America/Chicago labels. Early closes come
only from the frozen calendar. BTC uses an owner-declared UTC-day or continuous policy and never
inherits CME boundaries.

Snapshots preserve realized, unrealized, fees, funding, margin, exposure, drawdown, and variation
settlement by portfolio, market, exact contract, strategy, setup, session, and source version.
Summed child attribution must equal its parent and portfolio equity exactly; rounding residuals are
not silently assigned.

## 10–11. Capabilities, versioning, coexistence

The complete matrix is in `CAPABILITY_MATRIX.md`. Unsupported combinations reject before replay.

Schema namespace is `backtesting.execution_accounting.v2`; schemas use `*-v2-1`. A v2 run identity
includes all data, strategy, engine, execution, liquidity, instrument, cost, margin, risk, calendar,
rollover, funding, mark, split, seed, schema, and decision-register fingerprints.

Readers dispatch strictly by result schema. A v1 reader cannot read v2; a v2 reader may display v1
only through an explicit read-only legacy view labeled `V1_LEGACY_UNMIGRATED`. It cannot convert or
combine ledgers. Mixed v1/v2 source IDs reject with `MIXED_LEDGER_VERSION`. Re-running v1 under v2
creates a new result and is never a migration.

## 12–13. Tests, decisions, phases

See `ADVERSARIAL_TEST_PLAN.md`, `DECISION_REGISTER.md`, and `IMPLEMENTATION_PHASES.md`. No v2
implementation, strategy replay, provider access, or performance analysis was performed in this task.
