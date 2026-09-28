# Supervised Paper-Performance Persistence Bridge — Re-Audit Test Results

**Date:** 2026-09-01

## Primary repository baseline (corrected production code)

| Suite | Result |
|---|---|
| Focused (bridge) | 17 passed in 1.28s |
| Bridge + supervisor | 28 passed in 2.11s |
| Full repo | 4,490 passed, 9 skipped in 59.06s |

## Worktree adversarial (with temporary copies of corrected files)

| Suite | Result |
|---|---|
| Adversarial only (18 tests) | 18 passed in 1.15s |
| Focused (bridge) | 17 passed in 1.33s |
| Bridge + supervisor | 28 passed in 1.33s |
| git diff --check | clean |

## Codex baseline comparison

| Suite | Codex | Hermes | Difference |
|---|---|---|---|
| Bridge | 17 passed | 17 passed | — |
| Bridge + supervisor | 28 passed | 28 passed | — |
| Full repo | 4,491 passed, 8 skipped | 4,490 passed, 9 skipped | 1 fewer pass / 1 more skip (symlink) |

## Notes

- 9 skipped: symlink test requiring Windows admin (1 more than Codex's 8)
- No regressions
- Both prior confirmed defects (future-mark, startup gap) are now fixed
