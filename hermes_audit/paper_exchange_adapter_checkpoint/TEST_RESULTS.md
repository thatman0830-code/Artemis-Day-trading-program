# Durable Paper Exchange Adapter Checkpoint — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused persistence/gateway boundary | 54 passed in 1.49s |
| Full repo | 3469 passed, 3 skipped in 47.38s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 75 passed in 1.66s |
| Focused (6 test files) | 69 passed in 1.21s |
| Execution | 467 passed, 3 skipped in 2.80s |
| git diff --check | clean |

## Notes

- 3 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
