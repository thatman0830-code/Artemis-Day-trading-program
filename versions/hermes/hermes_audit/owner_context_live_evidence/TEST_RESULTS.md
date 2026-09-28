# Owner-Context Live-Evidence Bridge — Test Results

**Date:** 2026-08-30

## Primary repository baseline (uncommitted files)

| Suite | Result |
|---|---|
| Focused collector | 5 passed in 0.04s |
| Focused report | 8 passed in 0.05s |
| Monitoring | 58 passed in 0.08s |
| Complete V2 | 1057 passed in 2.53s |
| Full repo | 2245 passed, 1 skipped in 42.60s |

## Worktree adversarial (with temporary copies)

| Suite | Result |
|---|---|
| Adversarial only | 111 passed in 1.23s |
| Focused collector + report | 13 passed in 0.06s |
| Monitoring | 58 passed in 0.10s |
| V2 + monitoring | 1308 passed in 2.52s |
| Full repo | 2412 passed, 26 failed, 1 skipped in 37.10s |
| git diff --check | clean (CRLF warnings only) |

## Failures

26 pre-existing `futures_data/` failures (archive data absent). No regressions.
