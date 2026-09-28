# Owner-Context Health Adapter — Test Results

**Date:** 2026-08-30

## Primary repository baseline (uncommitted files)

| Suite | Result |
|---|---|
| Focused adapter | 27 passed in 0.05s |
| Monitoring | 42 passed in 0.06s |
| Complete V2 | 958 passed in 2.48s |
| Full repo | 2130 passed, 1 skipped in 43.26s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 99 passed in 1.04s |
| Focused adapter | 27 passed in 0.05s |
| Monitoring | 42 passed in 0.06s |
| V2 + monitoring | 1181 passed in 2.63s |
| Full repo | 2285 passed, 26 failed, 1 skipped in 36.61s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.

## Summary

| Suite | Tests | Passed | Failed |
|---|---|---|---|
| Focused adapter (primary) | 27 | 27 | 0 |
| Monitoring (primary) | 42 | 42 | 0 |
| Full repo (primary) | 2131 | 2130 | 0 |
| Adversarial (worktree) | 99 | 99 | 0 |
| V2+monitoring (worktree) | 1181 | 1181 | 0 |
| Full repo (worktree) | 2312 | 2285 | 26 |
