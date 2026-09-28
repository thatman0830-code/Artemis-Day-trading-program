# Prepared protective replacement handoff

`PaperOCOHandoffStoreV1` retains one replacement proposal per cancelled predecessor
directory. It is an offline preparation layer, not an order gateway or activation
mechanism. `trading_authority` and `rearm_authorized` always remain false.

## Evidence and retry rules

- Revalidate the predecessor checkpoint, acknowledged accounting, cancellation
  evidence and quantity-only replacement review before preparing or loading.
- Require contiguous eligible one-minute bars from the minute containing the
  partial fill through the exact replacement source bar. Reject touches of either
  protective price, including equality. Intraminute ambiguity is rejected
  conservatively; no synthetic fill is created.
- Retain both typed proposal inputs and gap evidence in a bounded, content-addressed
  envelope. The filename is fixed per predecessor to prevent a second proposal.
- Serialize preparation with the predecessor journal lock. Exact retries validate
  and sync the retained record; conflicting proposals reject without replacement.
- A truncated or corrupt record blocks retry and is never silently repaired.
  A sync failure is reported even if the complete bytes are subsequently readable.
- Loading with a predecessor reopened from its persisted initial configuration
  requires only that session directory, not remembered constructor inputs.

## Limits and next integration

`PREPARED_ONLY` does not mean protected. The predecessor remains cancelled.
`uncovered_tail` explicitly reports time between the last closed bar and the
review timestamp. Every record requires runtime revalidation, even without a tail.
Loading later verifies retained historical facts, not their current freshness.

This does not authenticate a market source, recover deleted records, resist a
malicious owner or full-directory rollback, coordinate proposals across separate
directories, or provide guaranteed physical-disk durability. A failed write may
leave a blocking partial file. Do not delete it automatically.

The next integration must bind this proposal to a single successor generation,
fresh execution-time evidence, risk limits and the supervised paper workflow.
No live or paper runtime is launched by this module. Hermes acceptance is pending.

## Verification boundary

Tests use synthetic offline fixtures only. They cover idempotency, conflicts,
directory-only reopen, missing/unsafe gap evidence, corruption, foreign locks,
sync failure and explicit uncovered tails. They are not real operational drills.
