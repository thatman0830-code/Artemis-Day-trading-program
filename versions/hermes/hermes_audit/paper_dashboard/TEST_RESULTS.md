# Read-Only Supervised Paper Dashboard — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (dashboard) | 8 passed, 1 skipped in 0.07s |
| Full repo | 4,259 passed, 6 skipped in 51.24s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 73 passed, 1 skipped in 6.23s |
| Focused | 8 passed, 1 skipped in 0.07s |
| Monitoring | 829 passed, 2 skipped in 6.43s |
| git diff --check | clean |

## Notes

- 1 skipped: symlink test (Windows admin required)
- 2 skipped in monitoring: symlink tests
- No regressions
