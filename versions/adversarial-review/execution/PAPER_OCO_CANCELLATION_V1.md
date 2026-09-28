# Verified protective cancellation acknowledgement

The protective coordinator, journal and disk-backed action evidence now accept
`CANCEL_ACK` after accounting acknowledgement. It validates supplied V2 lifecycle
events; it does not send requests or assert a gateway received them.

## Required evidence

- Accounting must exactly match the ledger acknowledged for the protective fill.
- Supply one to four explicit V2 CANCEL_REQUEST/CANCEL events as a tuple.
- Events bind the pending protective result ID via source_event_id.
- Events occur strictly after the fill and no earlier than the accounting snapshot.
- V2 ledger checks enforce identity, versions, sequence, chronology and legal
  transitions. Duplicate IDs and attached fills or replacement intents reject.
- Every old order ends FILLED or CANCELLED. Requests alone are insufficient.

A full exit with its sibling cancelled reaches `CLOSED_FLAT`. A partial exit needs
both old orders cancelled and reaches `CANCELLED_REQUIRES_REARM`. Neither state
permits further evaluation or automatic rearming. Invalid cancellation evidence
that reaches journal evaluation leaves IN_FLIGHT and blocks reload; pre-write
schema failures leave the previous checkpoint unchanged.

The bounded event tuple uses an exact field schema and explicit event-kind decoder,
without widening the accounting codec registry. Restart replays evaluation,
accounting and cancellations through the same coordinator. Hashes establish
consistency, not authentic origin: runtime integration must obtain and reconcile
trusted gateway evidence. Existing filesystem and crash-durability limits apply.

## Validation scope

Synthetic tests cover full/partial exits, disk replay, requests alone, one-order-only
cancellation, foreign binding, stale versions, duplicates, same-time events,
changed accounting and non-cancellation events. Existing protective execution,
checkpoint and evidence tests also run. This is not an independent audit or a
real operational cancellation drill.

Replacement generation validation/authorization, durable initial configuration,
trusted gateway coordination and supervised runtime launch remain outstanding.
No recorders, tasks, providers, credentials, wallets or submission systems are used.
