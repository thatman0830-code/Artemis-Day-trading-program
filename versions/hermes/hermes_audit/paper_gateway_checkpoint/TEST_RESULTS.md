# Durable Paper-Gateway Checkpoint — Test Results

**Date:** 2026-08-31

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (gateway + checkpoint) | 27 passed in 0.98s |
| Full repo | 3179 passed, 1 skipped in 44.35s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 74 passed, 3 skipped in 1.44s |
| Focused | 27 passed in 0.95s |
| Execution | 176 passed, 3 skipped in 1.11s |
| git diff --check | clean |

## Notes

- 3 skipped: symlink tests require admin on Windows (os.symlink not available without privilege)
- Potential finding PF-001 (LOW): decimal.InvalidOperation not caught by ValueError except clause — still rejects, just different exception type
