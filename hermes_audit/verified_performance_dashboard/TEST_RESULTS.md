# Verified Performance Dashboard Integration — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (dashboard) | 10 passed, 1 skipped in 1.05s |
| Full repo | 4,430 passed, 9 skipped in 56.93s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 43 passed in 3.43s |
| Focused (dashboard) | 10 passed, 1 skipped in 1.02s |
| git diff --check | clean |

## Notes

- 1 skipped: symlink test (Windows admin required)
- No regressions

