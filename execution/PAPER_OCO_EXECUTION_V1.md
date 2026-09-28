# Shared-position protective execution evaluation

This offline coordinator wraps the existing V2 one-minute OHLC engine for one
long BTC spot stop-market/limit-target pair. It does not submit orders, install
broker protection, cancel a sibling, resize an order, generate cost assumptions,
or persist runtime state.

## Implemented lifecycle

Arming verifies the accounting and order ledgers. Exactly two active, unfilled,
GTC sell intents must each match held quantity and the same accounted entry parent.
The initial supported accounting history has only one distinct buy-order identity.
Instrument/run identities, stop < average entry < target, aligned arming time and
known order-event chronology must agree. First execution bar starts at arming;
later bars are contiguous. The coordinator does not skip an unobserved initial gap.

V2 retains source-bar lineage, next-bar eligibility, exact volume participation,
grid checks and conservative adverse stop priority when both levels touch. The
coordinator checks at most one fill and total quantity no greater than its shared
position. Zero volume does not create a fill. No-fill evaluations may continue.

Any proposed fill enters AWAITING_ACCOUNTING and blocks all further evaluation,
including evaluation of the sibling. Explicit accounting acknowledgement requires
the same original ledger prefix, matching immutable instrument/policy identity,
exact proposed execution fills and the projected remaining quantity. Costs must be
supplied by the accounting caller and validated there; none are invented here.

After acknowledgement the state remains blocked:

- FLAT_REQUIRES_SIBLING_CANCELLATION: quantity is zero, but no cancellation has been
  performed or confirmed by this component.
- PARTIAL_REQUIRES_REARM: quantity remains; protection must be resized/rearmed in a
  new verified generation. It is not claimed to be continuously protected here.

There is no automatic rearm method. Invalid data or failed acknowledgement latches
HALTED. The submitting coordinator must enforce the block and reconcile actual
gateway state before any further action. Accounting acknowledgement alone is not
gateway reconciliation or sibling cancellation proof.

## Scope and limitations

The state is in-memory and single-use. Constructing a new object from old evidence
could replay evaluation: durable generation IDs, anti-replay storage, ownership,
reservation binding and restart recovery must precede runtime use. A frozen result
and content hash do not authenticate source data, approval, or delivery. The caller
must not bypass these controls by invoking the raw bar engine independently.

The supplied order ledger contains already-established lifecycle facts; this
module does not create or backdate activation events. It does not verify that an
unfilled entry remainder has been cancelled at the gateway. Accounting changes
while ARMED reject and require reconciliation rather than silently altering capacity.

Tests use actual V2 execution and accounting engines on synthetic candles. They
cover stop/target collision, full and partial fills, zero volume, post-fill blocking,
accounting acknowledgement, missing fills, wrong ownership/quantity, replay/gaps,
forming bars and determinism. These are simulated execution facts, not observed
market trades or actual operational paper-session evidence.

Remaining work: durable coordination with reservation-backed paper submission,
verified sibling cancellation/resize/rearm, explicit fee specifications, actual
source/strategy orchestration, and supervised runtime validation. No recorders,
schedulers, providers, credentials, live orders or operational processes changed.
This checkpoint is locally tested, not independently Hermes-audited.
