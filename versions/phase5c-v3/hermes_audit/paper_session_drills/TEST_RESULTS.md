# Bounded Paper-Session Recovery Drills — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (drills + supervisor + gateway + checkpoint) | 81 passed in 1.75s |
| Full repo | 3335 passed, 3 skipped in 45.43s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 48 passed in 1.99s |
| Focused (drills+supervisor+gateway+checkpoint) | 43 passed in 1.19s |
| Execution | 306 passed, 3 skipped in 2.59s |
| git diff --check | clean |

## Notes

- 3 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
