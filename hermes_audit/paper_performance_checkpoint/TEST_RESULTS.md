# Durable Paper-Performance Checkpoint — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (checkpoint) | 10 passed, 1 skipped in 1.01s |
| Full repo | 4,383 passed, 8 skipped in 56.64s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 44 passed, 1 skipped in 1.09s |
| Focused (checkpoint+ledger) | 21 passed, 1 skipped in 1.05s |
| Execution | 1050 passed, 2 pre-existing failures, 6 skipped in 7.00s |
| git diff --check | clean (pre-existing trailing blank line) |

## Notes

- 1 skipped: symlink test (Windows admin required)
- 2 pre-existing failures: `test_hermes_supervised_paper_launch_evidence_collector_adversarial.py` git -C vs git -c — pre-existing from a previous audit
- No regressions

## Primary reconciliation correction

- JSON float inside `$decimal`: rejected after requiring a canonical string
- Regression uses a recomputed valid payload checksum
- Corrected focused checkpoint suite: 11 passed, 1 skipped
