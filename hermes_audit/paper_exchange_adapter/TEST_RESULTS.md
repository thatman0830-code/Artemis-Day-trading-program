# Fail-Closed Paper Exchange Adapter — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused adapter+gateway boundary | 58 passed in 0.98s |
| Full repo | 3398 passed, 3 skipped in 46.63s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 60 passed in 1.00s |
| Focused (5 test files) | 58 passed in 1.16s |
| Execution | 381 passed, 3 skipped in 3.11s |
| git diff --check | clean |

## Notes

- 3 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
