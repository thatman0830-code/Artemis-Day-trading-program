# Atomic contingent-pair admission

`PaperGatewaySnapshotV1.submit_contingent_pair` admits a BTC paper stop and target
as one immutable state transition. Either both paper records appear or neither
does. This is an internal simulator operation and has no external transport.

The pair requires distinct, content-addressed identities; one accounted parent;
equal SELL quantity; GTC duration; stop-market and limit roles; matching market,
instrument, contract, run, configuration, timestamps, reference price and
authorization identity; and strict `stop < reference < target` geometry.

The pair shares one position exposure for admission, so the total limit uses the
larger leg rather than adding both mutually exclusive exits. Each leg must still
pass the per-order limit and both consume open-order capacity. Existing open
orders remain conservatively additive. `PARTIALLY_FILLED` records are now included
in ordinary submission exposure and open-order counts; they cannot disappear from
risk accounting merely because a partial fill occurred.

Exact replay of both retained submissions is idempotent. A reused key, one
pre-existing leg, changed request, unhealthy gateway, stale/future market data,
missing authorization, invalid geometry, or insufficient capacity rejects the
entire pair without half-admission.

The durable adapter now represents a pair as one command and one typed receipt.
Its checkpoint format preserves existing single-order receipts byte-for-byte while
using an explicit pair receipt shape for two paper-order identities. The bounded
session applies the same owner confirmation, command budget, spot exit-capacity,
order-notional and gross-exposure gates, counting the mutually exclusive pair once.

The durable adapter also exposes the sibling resolution as one command and one
typed receipt. It accepts the transition only when the pair identity and ordered
paper-order identities exactly match a previously accepted pair receipt. Foreign
or reordered identities fail closed without changing the gateway snapshot. The
resolution and its receipt survive checkpoint reload, and exact command replay
cannot apply the fill or cancellations twice.

The supervised performance coordinator recognizes the retained fill inside an
accepted atomic resolution. It requires the exact matching execution fill and
explicit cost evidence, writes those facts to Phase 4 accounting, and reconciles
every gateway order before the performance checkpoint advances. Missing or
conflicting economics durably halt the paper workflow after preserving the
gateway outcome. Exact resolution replay cannot duplicate P&L or costs.

Constructing this resolution directly from the OCO evaluator's generated fill
now requires the active coordinator's exact pending result and output ledger,
the retained accepted adapter pair receipt, the unchanged gateway records,
explicit fill economics, and a post-evaluation resolution time. The deterministic
bridge creates the matching paper fill, required residual/sibling cancellations,
adapter command, and verified performance evidence. Detached results, foreign
orders, stale pairs, inconsistent quantities, bad chronology, or mismatched costs
reject before a gateway command exists. This component grants no live-trading
permission and does not start paper trading.

The same bridge now emits bounded V2 cancellation acknowledgements for the OCO
journal. A full exit closes the sibling; a partial exit closes both the filled
leg's residual and its sibling. Replaying those acknowledgements proves the old
protective generation is no longer executable without silently rearming it.

`PaperOCOSupervisedTransactionStoreV1` records the cross-checkpoint progress as
`PREPARED`, `PERFORMANCE_COMMITTED`, `ACCOUNTING_ACKNOWLEDGED`, and `COMMITTED`.
Each forward-only transition uses an exclusive writer lock, compare-and-swap
identity, canonical checksum, and atomic replacement. An interrupted replacement
preserves the preceding stage; missing stage evidence, skipped transitions,
tampering, or competing writers fail closed.

`PaperOCOSupervisedCoordinatorV1` persists the complete content-addressed handoff
inside the one-generation OCO directory, then executes and resumes the recorded
stages against the gateway, performance, and OCO stores. It safely replays an
interruption before the performance marker and recognizes an already committed
OCO acknowledgement when only the following marker write was lost. Corrupt or
conflicting evidence and an underlying OCO journal left `IN_FLIGHT` remain
fail-closed rather than being guessed into a successful state.

## Atomic resolution

`PaperGatewaySnapshotV1.resolve_contingent_pair` stages an observed fill and every
required cancellation against a temporary immutable snapshot. It publishes that
snapshot only when the complete resolution succeeds. A full fill cancels the
opposite leg. A partial fill cancels both the winner's unfilled residual and the
opposite leg. Exact complete replay is idempotent; partial replay fails closed.

The primitive requires a healthy, connected, reconciled gateway; exact two-order
membership; previously unresolved records; correct versions; and cancellations
strictly after the fill. Invalid coverage, foreign records, stale versions,
overfills, or any rejected constituent event preserve the original snapshot.
The durable adapter binds the supplied pair identity to its retained pair
receipt before exposing this transition.
