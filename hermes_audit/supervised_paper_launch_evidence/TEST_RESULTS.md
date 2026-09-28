# Supervised Paper Launch-Evidence — Test Results

**Date:** 2026-09-01

## Primary repository baseline

| Suite | Result |
|---|---|
| Focused (evidence) | 11 passed in 0.77s |
| Full repo | 4,006 passed, 5 skipped in 50.01s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 69 passed in 0.85s |
| Focused (4 test files) | 51 passed in 1.42s |
| Execution | 781 passed, 4 skipped in 5.97s |
| git diff --check | clean |

## Notes

- 4 skipped: symlink tests in checkpoint module (Windows admin required)
- No regressions

## Codex reconciliation

| Suite | Result |
|---|---|
| Focused evidence, adversarial, gate, and workflow | 117 passed in 1.22s |
| Full repository | 4,077 passed, 4 skipped in 51.32s |
| DEF-001 | Corrected: direct construction cannot grant trading authority |
