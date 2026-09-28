# Watchdog Deployment Controls — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused task tests | 5 passed in 0.04s |
| Monitoring | 129 passed in 0.69s |
| Full repo | 2535 passed, 1 skipped in 43.73s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 103 passed in 0.12s |
| Focused task tests | 5 passed in 0.03s |
| Monitoring | 232 passed in 0.76s |
| Full repo | 2694 passed, 26 failed, 1 skipped in 37.75s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
