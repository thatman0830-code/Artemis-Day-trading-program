# Single-successor supervised paper rearm

`PaperOCOSuccessorV1` converts one gap-reviewed `PREPARED_ONLY` handoff into one
locally persisted protective paper generation. It creates V2 submit, accept and
activate lifecycle facts only in the offline ledger. It has no provider, network,
broker, exchange, signing or order-submission transport.

## Required authority boundary

The caller must supply the exact prepared-handoff identity, content-addressed
launch-evidence file, a current content-addressed owner confirmation, the matching
bounded launch policy and the activation time. The component rebuilds the owner
confirmation and reevaluates launch evidence instead of trusting a supplied
decision object. It requires:

- an eligible BTC-only supervised-paper decision;
- explicit current supervision and verified stop control;
- matching repository checkpoint and configured limits;
- no uncovered handoff tail and exact contemporaneous activation;
- order notional and marked gross exposure within the decision limits.

The successor ledger contains only the two replacement exits. Each instruction
is rebound to its new order and exact activation event with source-bar lineage.
Its accounting retains the verified entry and partial-exit history.

## Single-generation and crash behavior

The predecessor journal lock serializes creation. Before creating the successor
directory, a fixed binding is durably marked `IN_FLIGHT`. On success it becomes
`COMMITTED` and binds the handoff, launch decision and successor initial identity.
It also retains the content identities of the launch evidence and owner confirmation.
Exact retries return the same generation. A different generation, an unbound
directory, corrupt evidence or an interrupted `IN_FLIGHT` record fails closed and
requires owner recovery; nothing is silently deleted or reconstructed.

This is a filesystem transaction, not a claim of atomic durability across every
hardware or operating-system failure. It cannot detect malicious owner rewrites
or full-directory rollback. A committed generation must still receive contiguous
closed bars and reconcile every simulated fill and cost through the existing
protective checkpoint machinery.

All artifacts remain `paper_only=true`, `live_trading_permitted=false` and
`trading_authority=false`. This module does not start a process, scheduled task,
recorder or paper session. Tests use synthetic offline evidence only. Independent
Hermes acceptance remains pending.
