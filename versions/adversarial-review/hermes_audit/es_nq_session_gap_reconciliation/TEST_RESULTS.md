# ES/NQ Session-Gap Reconciliation — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused reconciler | 11 passed in 1.01s |
| Complete V2 | 1250 passed in 2.71s |
| Full repo | 2971 passed, 1 skipped in 45.39s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 58 passed in 1.08s |
| Focused | 11 passed in 1.36s |
| Complete V2 | 1390 passed in 3.03s |
| Full repo | 3085 passed, 26 failed, 1 skipped in 39.53s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
