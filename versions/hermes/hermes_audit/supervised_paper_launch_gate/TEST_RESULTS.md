# Supervised Paper-Trading Launch Gate — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (launch gate) | 25 passed in 0.04s |
| Full repo | 3,921 passed, 5 skipped in 51.08s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 74 passed in 0.07s |
| Focused (6 test files) | 83 passed in 1.47s |
| Execution | 701 passed, 4 skipped in 6.55s |
| git diff --check | clean |

## Notes

- 4 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
