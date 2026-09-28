# Supervised Paper Operational Drills — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (operational drills) | 4 passed in 1.19s |
| Full repo | 3,638 passed, 4 skipped in 47.76s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 40 passed, 1 skipped in 2.87s |
| Focused (4 test files) | 41 passed in 1.88s |
| Execution | 602 passed, 4 skipped in 5.78s |
| git diff --check | clean |

## Notes

- 1 skipped: symlink test (Windows admin required)
- 4 skipped in execution: checkpoint symlink tests (Windows admin required)
- No regressions
