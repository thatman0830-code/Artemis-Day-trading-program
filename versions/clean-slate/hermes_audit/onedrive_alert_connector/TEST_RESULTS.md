# OneDrive Alert Connector — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused | 10 passed in 0.12s |
| Monitoring | 308 passed in 0.66s |
| Full repo | 2714 passed, 1 skipped in 44.33s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 59 passed in 0.46s |
| Focused | 10 passed in 0.08s |
| Monitoring | 367 passed in 0.73s |
| Full repo | 2829 passed, 26 failed, 1 skipped in 38.31s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
