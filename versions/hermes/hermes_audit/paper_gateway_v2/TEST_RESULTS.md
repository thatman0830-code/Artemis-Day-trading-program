# V2 Paper-Gateway Foundation — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused gateway | 18 passed in 0.97s |
| Full repo | 3095 passed, 1 skipped in 44.69s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 75 passed in 0.98s |
| Focused gateway | 18 passed in 0.92s |
| Execution + relevant | 93 passed in 0.98s |
| Full (excluding broken collections) | 1387 passed, 26 pre-existing, 1 skipped in 36.05s |
| git diff --check | clean |

## Notes

- Full-suite collection errors from previously committed adversarial test files are pre-existing — they reference uncommitted primary modules not present at this checkpoint in the worktree. Excluding those gives 1387 passed, 26 pre-existing `futures_data/` failures, 1 skipped.

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
