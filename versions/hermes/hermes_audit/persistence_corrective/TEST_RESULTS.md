# Supervised Paper-Performance Persistence Bridge — Corrective Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (performance) | 6 passed in 1.08s |

## Worktree corrective adversarial

| Suite | Result |
|---|---|
| Corrective adversarial (15 tests) | 12 passed, 3 failed in 1.23s |
| Focused existing (6 tests) | 6 passed in 1.08s |
| git diff --check | clean |

## Failed tests (regression — required safe behavior not yet implemented)

| Test | Failure | Defect |
|---|---|---|
| `TestFutureMarkDefect::test_future_observed_at_should_reject` | DID NOT RAISE — future mark accepted | DEFECT-A |
| `TestFutureMarkDefect::test_future_available_at_should_reject` | Regex 'future\|unavailable\|stale' did not match 'failed closed' | DEFECT-A |
| `TestStartupReconciliationGapDefect::test_missing_perf_with_retained_fill_should_reject` | DID NOT RAISE — empty accounting created | DEFECT-B |

## Passed reproduction tests (confirming defects exist)

| Test | Result |
|---|---|
| `TestFutureMarkDefect::test_future_observed_at_accepted_by_current_impl` | Defect A reproduced |
| `TestStartupReconciliationGapDefect::test_missing_perf_checkpoint_with_retained_fill_accepted_by_current_impl` | Defect B reproduced |
