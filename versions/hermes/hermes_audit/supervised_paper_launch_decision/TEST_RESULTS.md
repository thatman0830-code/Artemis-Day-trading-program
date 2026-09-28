# Supervised Paper Launch-Decision Contract — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (decision) | 7 passed in 0.80s |
| Full repo | 4,184 passed, 5 skipped in 50.31s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 67 passed in 0.84s |
| Focused (3 test files) | 45 passed in 0.10s |
| Execution | 957 passed, 4 skipped in 6.23s |
| git diff --check | clean |

## Notes

- 4 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
