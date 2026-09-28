# OOS Archive Scanner — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused scanner | 11 passed in 0.94s |
| Complete V2 | 1179 passed in 2.48s |
| Full repo | 2900 passed, 1 skipped in 46.49s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 59 passed in 1.39s |
| Focused scanner | 11 passed in 0.95s |
| Complete V2 | 1320 passed in 2.68s |
| Full repo | 3015 passed, 26 failed, 1 skipped in 38.72s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
