# Off-Host Alert Delivery Foundation — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused | 8 passed in 0.08s |
| Monitoring | 240 passed in 0.48s |
| Full repo | 2646 passed, 1 skipped in 44.08s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 66 passed in 0.23s |
| Focused | 8 passed in 0.09s |
| Monitoring | 306 passed in 0.67s |
| Full repo | 2768 passed, 26 failed, 1 skipped in 38.92s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
