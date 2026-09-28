# Stopped-Recorder Classification Correction — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (health report) | 9 passed in 0.75s |
| Full repo | 3,864 passed, 5 skipped in 50.07s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 32 passed in 0.10s |
| Focused (report+adapter+collector) | 43 passed in 0.78s |
| Monitoring | 748 passed in 1.07s |
| git diff --check | clean |

## Notes

- No regressions
