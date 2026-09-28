# V2 Phase 6 Rollover and Funding Implementation

Phase 6 coordinates immutable futures rollover legs and verified BTC linear-perpetual funding
boundaries. It creates no fill, provider request, exchange order, credential access, or strategy
decision.

## Supported

- ES/NQ long and short rolls with exact outgoing/incoming contracts and verified sessions.
- Distinct outgoing-close and incoming-open instructions/events with participation flooring.
- Partial close/open state, explicit temporary flat exposure, and incomplete/failed gates.
- Later finalized eligible bars only; same-bar and look-ahead inputs reject.
- Capability-gated BTC linear-perpetual funding with exact mark, oracle, rate, timestamp, multiplier,
  basis, versions, expected payment, and Phase 4 accounting-event lineage.
- Deterministic settlement → funding → outgoing roll → incoming roll collision order.
- Immutable replay ledger, checkpoint/tamper checks, residual gates, and cross-ledger reconciliation.

## Unsupported / fail closed

No synthetic continuous contract, price adjustment, transfer fill, inferred price, assumed zero
funding, provider lookup, spot/futures funding, rollover order creation, live/paper execution, or
automatic resolution. Missing incoming data leaves the account flat and incomplete. Missing
authoritative funding blocks a held perpetual across its boundary.

## Remaining authoritative inputs

Historical execution requires effective-dated owner-approved roll specifications, exact contract
and session evidence, participation limits and bar volume. BTC perpetual replay additionally needs
synchronized point-in-time mark/oracle/rate facts, funding schedules, contract basis/multiplier,
instrument identity, and capability/version evidence. The retained BTC candle archive does not
supply these facts.

## Reconciliation correction

Equal-time/equal-priority ledger events are classified as `PRIORITY_AMBIGUITY`
before lexical event-id ordering. This makes the public reason stable for both
hash orders without changing valid event ordering.
