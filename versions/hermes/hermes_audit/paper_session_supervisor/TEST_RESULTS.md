# Offline Supervised Paper-Session Core — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (supervisor + gateway + checkpoint) | 27 passed in 0.98s |
| Full repo | 3264 passed, 3 skipped in 44.42s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 66 passed in 1.60s |
| Focused (supervisor+gateway+checkpoint) | 38 passed in 1.02s |
| Execution | 253 passed, 3 skipped in 1.41s |
| git diff --check | clean |

## Notes

- 3 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions
