# Clock and ES/NQ Integrity — Test Results

**Date:** 2026-08-30

## Primary repository baseline

| Suite | Result |
|---|---|
| Forward archive | 8 passed in 0.31s |
| Collector | 5 passed in 0.03s |
| Monitoring | 58 passed in 0.11s |
| Complete V2 | 1168 passed in 2.63s |
| Full repo | 2364 passed, 1 skipped in 43.12s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 100 passed in 0.41s |
| Forward archive | 8 passed |
| Collector | 5 passed |
| Monitoring | 58 passed |
| V2 + monitoring | 1308 passed in 2.83s |
| Full repo | 2520 passed, 26 failed, 1 skipped in 39.32s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
