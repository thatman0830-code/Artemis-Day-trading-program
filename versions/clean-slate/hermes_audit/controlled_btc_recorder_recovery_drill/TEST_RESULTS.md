# Controlled BTC Recorder Recovery Drill — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (recovery drill) | 6 passed in 0.04s |
| Full repo | 3,684 passed, 5 skipped in 50.57s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 75 passed in 0.06s |
| Focused | 6 passed in 0.01s |
| Full (excluding broken collections) | 1300 passed, 26 pre-existing, 1 skipped in 35.77s |
| git diff --check | clean |

## Notes

- Collection errors from previously committed adversarial tests referencing uncommitted modules — pre-existing, not regressions
- 26 pre-existing `futures_data/` failures (archive data absent)
- No regressions
