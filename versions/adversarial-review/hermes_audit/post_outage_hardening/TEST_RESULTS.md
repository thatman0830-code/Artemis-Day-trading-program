# Post-Outage Operational Hardening — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (forward + collector) | 18 passed in 1.19s |
| Monitoring | 484 passed in 0.78s |
| Full repo | 3030 passed, 1 skipped in 44.44s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 46 passed in 0.06s |
| Focused collector | 6 passed in 0.04s |
| Monitoring | 530 passed in 0.91s |
| Full repo | 3132 passed, 26 failed, 1 skipped in 39.22s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (2 pinned-Python + 24 archive data absent). No regressions.
