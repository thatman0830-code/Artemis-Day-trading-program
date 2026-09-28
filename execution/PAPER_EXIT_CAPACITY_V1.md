# BTC spot exit-capacity preflight

The existing bounded paper driver now checks sell quantity **before** forwarding
submissions or verified fills to the paper adapter/accounting persistence bridge.
No independent execution engine, automatic protective orders, or runtime process
was added.

Previously the bounded driver could accept a sell intent while flat or while a buy
was still unfilled. Notional limits alone do not establish that spot units are held.
The accounting layer could later reject a resulting unsupported short position,
after the adapter had processed an otherwise valid paper fill. Submission tests
reproduced the missing flat/unfilled-position guard before the fix.

## Rules

- Reload and verify current adapter/performance checkpoints. Their gateway identity
  and fill quantities must already reconcile; do not silently advance accounting.
- Held units come from the verified accounting position, not requested entry size.
- Outstanding ACCEPTED/PARTIALLY_FILLED sell orders reserve their **remaining**
  quantity. Outstanding orders without known session intents reject.
- New sells cannot exceed held units minus outstanding sell reservations.
- Sell fills cannot exceed held units before gateway mutation. Existing per-order
  fill limits, intent/side/chronology checks, and accounting reconciliation remain.
- Confirmed cancellation frees that order's unit reservation. It does not recycle
  the session's conservative cumulative notional or command budgets.
- Invalid inputs use the existing durable halt and explicit unconfirmed-halt path.

The gate deliberately gives no OCO credit. Two independent full-position stop/target
orders would reserve the same units twice and reject. Proper paired protection
still requires a coordinated lifecycle that resolves, cancels or resizes siblings.
This patch does not claim stop/target installation or live reduce-only semantics.

## Evidence

Synthetic integration tests use the actual bounded session and checkpoint stores:
flat/unfilled-entry sell rejection, independent duplicate exits, oversized fill
rejection, partial exits to flat with exact costs, remaining-unit reservations,
confirmed cancellation/replacement, and changed checkpoint rejection. Valid fill
fixtures are explicitly supplied test facts, not fills generated from market data.
Invalid submissions/fills do not alter gateway order records; halt state may change.

The guard assumes the existing single-owner serialized session. Reloading two files
is not a cross-file atomic transaction or protection against concurrent hostile
writers. Startup freshness, clock guards, protective lifecycle, real source input,
V2 fill generation and runtime validation remain separate requirements.

No operational paper session, recorder, scheduler, provider, credential, broker,
exchange or live-order path was accessed or changed. These are local regression
tests, not an independent Hermes audit or evidence of profitability.
