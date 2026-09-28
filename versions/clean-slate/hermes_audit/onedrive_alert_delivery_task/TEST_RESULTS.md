# OneDrive Alert-Delivery Task — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (delivery + task) | 16 passed in 0.14s |
| Monitoring | 373 passed in 0.81s |
| Full repo | 2779 passed, 1 skipped in 44.82s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 110 passed in 0.26s |
| Focused | 16 passed in 0.46s |
| Monitoring | 483 passed in 0.86s |
| Full repo | 2945 passed, 26 failed, 1 skipped in 39.07s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
