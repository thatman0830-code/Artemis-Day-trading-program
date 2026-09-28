# Controlled Stale-Data and OneDrive Alert-Escalation Drill — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (stale alert drill) | 8 passed in 0.04s |
| Full repo | 3,767 passed, 5 skipped in 51.66s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 96 passed in 0.06s |
| Focused | 8 passed in 0.02s |
| git diff --check | clean |

## Notes

- No regressions
