# V2 Phase 5 Independent Audit — Reconciled

- Source audit commit: `2b54c6b423c1b6bd92df60692800e76951e056db`
- Audited parent: `6edb0390311d6564878cf99cb667165351e310a4`
- Reconciled onto Phase 6 checkpoint: `a0f972ab950559baa5b7a071d0da7a80afddbaf6`
- Source boundary: one adversarial test file and five audit artifacts; no production files.

## Independent findings

Phase 5 public behavior passed the accepted adversarial coverage. No Phase 5
production correction was required. The first post-accounting evaluation fixes
the session reference and peak; a later evaluation cannot reset the reference.
Post-accounting priority is maintenance margin, session loss, then drawdown.
Forced flattening emits an immutable instruction only for a non-flat position,
and a later eligible finalized bar is required; Phase 5 creates no order or fill.
Exposure, leverage, concentration, position and initial-margin limits remain
pre-trade checks. Maintenance, session-loss and drawdown remain post-accounting
checks.

## Test reconciliation

Of 129 submitted tests, 123 were accepted unchanged. Four were rejected as
redundant and two as implementation-coupled. In particular,
`test_duplicate_decision_conflict_rejects` did not exercise a conflict; it
repeated idempotency and was removed. See `FINDINGS.json` for group-level detail.

## Corrections to submitted audit claims

Sixteen of seventeen submitted checksum values represented Windows working-tree
bytes rather than canonical Git-object bytes. This reconciliation records
canonical hashes. Reset wording was corrected: the audit branch was moved only
after a preservation reference was created; the source commit proves the audit
deliverables survived. The reported 26 full-suite failures were isolated-worktree
evidence gaps, not Phase 5 regressions; the primary repository suite is rerun as
part of reconciliation rather than inheriting that claim.

No remote, provider, credential, archive, collector, scheduler, exchange, or
out-of-sample path is used by the integrated tests.
