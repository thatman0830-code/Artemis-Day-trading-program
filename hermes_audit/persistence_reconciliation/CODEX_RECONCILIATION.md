# Persistence bridge: Codex reconciliation

Date: 2026-09-02

Primary base: `bc4dae95f120dd49d91c66c19de49eaf40c5d65c`.
Implementation and regression tests remain uncommitted. This is a local
reconciliation record, not a new independent Hermes audit or launch approval.

## Audit evidence corrections

- Re-audit commit: `2405b6b5287b1887db986b0e3aec2ebe1f9c6e54`.
- Its actual Git parent is `d52d15957376ff1746b316dea5c21ce7a5bcc1b8`,
  not the `3b7d0ee...` parent stated in the report.
- The re-audit test named `test_replay_after_additional_order` does not add
  an order. Its claim of changed-snapshot replay coverage is not accepted.
- The test named `test_replay_no_duplicate_after_reconnect` does not perform
  a disconnect/reconnect. Its immediate replay assertions do not establish
  reconnect behavior.
- Separate health-write and alert-write failure coverage was absent from the
  submitted re-audit test file. The claim of no remaining coverage gaps was
  therefore not accepted without additional local verification.
- The reported one-pass/one-skip environment difference is not independently
  attributed here; local suite results are reported separately.
- Hermes test/artifact files have not been copied or merged into primary.
  Original audit commits remain unchanged. No blanket test acceptance is claimed.

## Local gap closure

`execution/test_supervised_paper_performance_v1.py` now explicitly verifies:

1. Disconnect changes the gateway identity and sets reconciliation-required;
   exact retained observations reconnect it, and replay preserves accounting.
2. A genuinely new, accepted second order changes the gateway identity and
   increases retained record count. Replay of the old fill then safely rejects
   with the underlying `paper fill replay conflicts` error, preserves the exact
   performance checkpoint bytes and costs, and durably halts the adapter.
3. Health-write failure and alert-write failure are injected separately. Both
   raise `PaperPerformanceHaltUnconfirmedError` with the specific `OSError`
   cause and latch both start and cycle operations. Adapter halt is verified
   independently; missing health/alert evidence is never represented as written.

The additional-order case is **safe rejection**, not transparent idempotent
replay. The fill binding includes the gateway snapshot used at accounting time.
This limitation must be respected by any future session driver; generic replay
after arbitrary snapshot changes is not approved by these tests.

## Persistence and authority limits

The two checkpoints are individually atomically replaced, not one transaction.
Existing regression tests cover before/after-write interruption, startup
mismatch, future mark rejection, halt-write failure, and accounting preservation.
The in-memory failure latch is not a durable incident journal. Storage failures
require owner intervention; a failed halt write is never called a confirmed halt.

No production code was changed during this gap-closure step. No session was
launched, and no recorders, collectors, scheduled tasks, providers, credentials,
OneDrive evidence, or order-submission systems were accessed. Passing these tests
does not establish profitability, deployment approval, or live/paper readiness.

## Focused verification

- Bridge: 20 passed.
- Bridge plus supervisor: 31 passed.
- Full offline repository: 4,494 passed, 8 skipped (59.75 seconds).
- All added cases execute behavioral assertions; no docstring-only test counts.
