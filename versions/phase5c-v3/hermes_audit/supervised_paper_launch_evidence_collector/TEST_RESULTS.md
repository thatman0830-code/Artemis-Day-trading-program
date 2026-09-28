# Supervised Paper Launch-Evidence Collector — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (collector) | 11 passed in 0.78s |
| Full repo | 4,087 passed, 5 skipped in 50.51s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 88 passed in 0.92s |
| Focused (3 test files) | 48 passed in 0.12s |
| Execution | 881 passed, 4 skipped in 6.38s |
| git diff --check | clean |

## Notes

- 4 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions

## Real owner-context reconciliation

- DEF-001 corrected: repository ownership mismatch now uses per-command `safe.directory`.
- No global Git configuration is written.
- DEF-002 corrected: exact 40-character SHA-1 and 64-character SHA-256 repository object IDs are supported.
