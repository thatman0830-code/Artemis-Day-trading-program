# End-to-End Supervised Offline Paper Workflow — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused supervised-workflow boundary | 37 passed in 1.77s |
| Full repo | 3,555 passed, 3 skipped in 47.71s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 80 passed in 2.02s |
| Focused (5 test files) | 65 passed in 1.20s |
| Execution | 558 passed, 3 skipped in 3.55s |
| git diff --check | clean |

## Notes

- 3 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
