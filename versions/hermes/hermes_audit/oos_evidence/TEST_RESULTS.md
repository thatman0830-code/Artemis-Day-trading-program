# OOS Evidence Readiness — Test Results

**Date:** 2026-08-30
**Python:** `C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe` (3.11.9)

## Primary repository baseline (uncommitted OOS files present)

| Suite | Command | Result |
|---|---|---|
| OOS evidence focused | `pytest test_oos_evidence.py -q` | 16 passed in 0.94s |
| Complete v2 suite | `pytest execution_accounting_v2 -q` | 866 passed in 2.27s |
| Full repo | `pytest -q` | 1996 passed, 1 skipped in 46.17s |

## Worktree adversarial (with temporarily copied OOS files)

| Suite | Result |
|---|---|
| Adversarial only | 82 passed in 0.98s |
| Complete v2 suite | 947 passed, 1 failed (schema count) in 2.37s |
| Full repo | 2051 passed, 27 failed, 1 skipped in 36.70s |

## Failures explained

- **1 v2 failure**: `test_all_machine_schemas_parse_offline` expects 11 schema
  files but the OOS schema makes 12. The primary repo's modified
  `test_specifications.py` expects 12. This is a version mismatch between the
  worktree commit and the uncommitted primary changes. NOT a production defect.

- **26 full-repo failures**: Pre-existing `futures_data/` tests requiring data
  archive files absent from the worktree. Unrelated to OOS evidence.

- **1 additional full-repo failure**: Same schema count mismatch as above.

## Summary

| Suite | Tests | Passed | Failed | Duration |
|---|---|---|---|---|
| OOS focused (primary) | 16 | 16 | 0 | 0.94s |
| Complete v2 (primary) | 866 | 866 | 0 | 2.27s |
| Full repo (primary) | 1997 | 1996 | 0 | 46.17s |
| Adversarial (worktree) | 82 | 82 | 0 | 0.98s |
| Complete v2 (worktree) | 948 | 947 | 1 | 2.37s |
| Full repo (worktree) | 2079 | 2051 | 27 | 36.70s |

No production defects. The 1 v2 failure is a version mismatch (worktree expects
11 schemas, primary uncommitted changes add a 12th). The 27 full-repo failures
are 26 pre-existing + 1 same schema count mismatch.
