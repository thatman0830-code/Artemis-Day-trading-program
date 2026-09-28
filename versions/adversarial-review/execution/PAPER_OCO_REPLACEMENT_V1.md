# Read-only quantity-only replacement review

`review_protective_replacement` reloads the predecessor's durable evidence and
requires `CANCELLED_REQUIRES_REARM` with both prior orders cancelled. It verifies
the expected checkpoint ID before review and checks it again before returning.
Accounting must exactly match the acknowledged partial-exit ledger.

New stop and target intents must have distinct fresh order/action IDs, map to their
respective prior orders, and each equal the remaining position quantity. Instrument
grid and effective-date checks apply. Prices, parent entry, configuration, side,
order types, execution version and time-in-force must remain unchanged. This version
does not allow breakeven moves, wider stops, new targets or policy changes.

A finalized, eligible one-minute source bar must start after cancellation is
complete and be available by review time, with close age at most 90 seconds. Its
closing price must be strictly inside the proposed protection. This verifies a
candidate against supplied evidence, not continuous protection during the gap.

The immutable deterministic receipt always has requires_gap_review=true,
rearm_authorized=false and trading_authority=false. It does not reserve a generation,
persist the review, activate orders, or change the predecessor. It is not an
authorization token, and hashes do not authenticate gateway or market evidence.
Repeated reviews are allowed; a future serialized handoff must prevent duplicate
activation and revalidate current state. Initial configuration persistence, gap
assessment, gateway reconciliation and supervised runtime integration remain open.

Synthetic tests cover accepted quantity reduction, deterministic read-only results,
changed quantities/prices/configurations/parents, reused IDs, invalid grids,
activation chronology, incorrect predecessor mapping, unusable source bars and
uncancelled/stale predecessor checkpoints. No operational system is accessed.
