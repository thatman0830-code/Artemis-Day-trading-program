# OOS and Operational Resilience — Test Results

**Date:** 2026-08-30

## Primary repository baseline (uncommitted files)

| Suite | Result |
|---|---|
| OOS evidence focused | 16 passed in 0.95s |
| Operational resilience focused | 15 passed in 0.03s |
| Complete v2 suite | 866 passed in 2.37s |
| Full repo | 2011 passed, 1 skipped in 42.59s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 92 passed in 1.01s |
| v2 + monitoring | 1055 passed in 2.54s |
| Full repo | 2159 passed, 26 failed, 1 skipped in 37.48s |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.

## Summary

| Suite | Tests | Passed | Failed |
|---|---|---|---|
| OOS focused (primary) | 16 | 16 | 0 |
| Resilience focused (primary) | 15 | 15 | 0 |
| Full repo (primary) | 2012 | 2011 | 0 |
| Adversarial (worktree) | 92 | 92 | 0 |
| v2+monitoring (worktree) | 1055 | 1055 | 0 |
| Full repo (worktree) | 2186 | 2159 | 26 |
