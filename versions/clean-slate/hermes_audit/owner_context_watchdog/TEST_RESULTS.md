# Owner-Context Health Watchdog — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Watchdog + task focused | 4 passed in 0.08s |
| Monitoring | 62 passed in 0.12s |
| Full repo | 2468 passed, 1 skipped in 43.94s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 64 passed in 0.30s |
| Focused watchdog + task | 4 passed in 0.35s |
| Monitoring | 126 passed in 0.37s |
| V2 + monitoring | 1376 passed in 2.89s |
| Full repo | 2588 passed, 26 failed, 1 skipped in 37.97s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
