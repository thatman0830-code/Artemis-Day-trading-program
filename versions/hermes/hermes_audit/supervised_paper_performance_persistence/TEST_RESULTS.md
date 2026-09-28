# Supervised Paper-Performance Persistence Bridge — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (performance) | 6 passed in 1.09s |
| Full repo | 4,479 passed, 9 skipped in 59.19s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 23 passed in 1.09s |
| Focused (performance+workflow) | 17 passed in 1.17s |
| git diff --check | clean |

## Notes

- No regressions
