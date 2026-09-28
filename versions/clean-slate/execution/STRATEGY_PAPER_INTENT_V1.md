# Qualified strategy to V2 paper intent

`compile_strategy_paper_intent` reuses the existing #29.1 entry-order creation
engine and V2 instrument/order validator. It accepts frozen qualification,
entry-zone selection, context, flat-position observation, instrument specification,
proposed quantity and explicit source/quantity evidence identities.

The result is an immutable, content-addressed **advisory intent**, not an authorized
submission, simulated fill, position-sizing approval, or installed protective order.
No runtime systems or strategy modules are modified by this bridge.

## Preserved semantics

- The selected entry remains a LIMIT/GTC order at its frozen price, not an immediate
  MARKET fill. Explicit expiry is required and capped at five minutes.
- Stop and target survive as separate fields. They are not misencoded as an entry
  stop-limit order. `protective_orders_created` is always false.
- Source availability must precede qualification; future or stale inputs reject.
  Strategy integers are interpreted explicitly as Unix epoch milliseconds,
  consistent with the existing structural producers. No seconds/ms guessing occurs.
- The initial scope supports bullish BTC spot entries only with a confirmed flat
  observation, not bearish short entries, derivatives, or testnet execution.
- Proposed quantity must be exact positive Decimal and on the instrument grid.
  Entry, stop and target grids, effective dates, geometry, supplied risk/reward,
  configured minimum reward/risk, and existing bounded order-notional cap are checked.
- The full supplied records, source hashes, versions, quantity, and chronology are
  bound into identity. Changing input economics cannot retain the V2 identity.

## Trust and operational limitations

The caller supplies trusted in-memory records. Hashes establish identity, not
provider authenticity, approval, or proof that qualification was computed from
those exact source bytes. There is no external manifest decoder in this bridge.
The flat-position observation must eventually come from verified current paper
state. It is not itself read from the live session here.

The supplied quantity is only a proposal. Existing #29.2 sizing consumes an
EntryFill and is not silently treated as pre-order authorization. The runtime still
needs a pre-submission sizing/risk boundary without fabricating an earlier fill.

Repeated identical compilation is deterministic. This pure function has no durable
duplicate registry; runtime duplicate prevention must key on the retained strategy
order/setup identity as well as the V2 request identity. Changes to a proposal do
not authorize multiple entries for the same setup.

The existing #29.1 EntryFill is not imported as a V2 ExecutionFill: one-minute bar
eligibility, participation, instrument lineage, and explicit fee/cost evidence
must be validated by the execution/accounting path. No fee defaults are invented.

## Local verification

Tests exercise the actual strategy order-creation engine through V2 intent
validation, determinism, identity changes, stop/target preservation, non-authority,
type/grid/geometry failures, chronology, expired instrument coverage, and unsupported
markets/modes. Fixtures are synthetic; no actual strategy signal or trade is claimed.

Remaining integration: real candle-to-qualification orchestration, pre-order sizing
and authorization, protective lifecycle, V2 fill/cost generation, durable submission
and reconciliation, and supervised runtime evidence. This is not an independent
Hermes audit or authorization to launch a session.
