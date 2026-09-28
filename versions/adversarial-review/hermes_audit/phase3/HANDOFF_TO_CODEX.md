# Handoff to Codex — V2 Phase 3 OHLC Audit

**Audit assignment:** AUDIT-V2-PHASE3-CONSERVATIVE-OHLC
**Auditor:** Hermes Agent
**Date:** 2026-08-27
**Branch:** `hermes/audit-lane`
**HEAD:** `b2711098c0f9777e52af63e7d41b313f64cc9dc1`

## Summary

Hermes independently auduted Phase 3 conservative one-minute OHLC execution.
All 9 required audit cases were reviewed. Codex found and corrected one source-lineage defect.

## Deliverables

| File | Description |
|---|---|
| `hermes_audit/phase3/AUDIT_REPORT.md` | Full audit report with all 9 cases |
| `hermes_audit/phase3/FINDINGS.json` | Structured findings (empty defects array, 5 observations) |
| `hermes_audit/phase3/OHLC_TRUTH_TABLE_COVERAGE.json` | Truth table row → test mapping (25/25 rows covered) |
| `hermes_audit/phase3/PARTICIPATION_INVARIANTS.json` | 12 participation invariants (all passing) |
| `hermes_audit/phase3/TEST_RESULTS.md` | Test execution results |
| `hermes_audit/phase3/FILE_CHECKSUMS.json` | SHA-256 checksums for all audited files |
| `hermes_audit/phase3/HANDOFF_TO_CODEX.md` | This file |

## Adversarial test file

`backtesting/execution_accounting_v2/test_hermes_phase3_adversarial.py` — 127 reconciled tests
covering all 9 required audit cases. All pass.

## Test results

- Baseline: 219 passed
- Reconciled adversarial only: 127 passed
- Reconciled complete v2 suite: 368 passed
- Full offline repository suite: 1498 passed
- No regressions, no failures, no errors

## Verdict

HERMES_ACCEPTED_V2_PHASE3_OHLC

Hermes modified no production code. Codex reconciliation added the smallest deterministic lineage
extension required to enforce the frozen signal-bar rule and corrected the affected tests/artifacts.

## Notes for Codex

1. `activation_at == bar.open_time` is not sufficient. It is eligible only when the canonical
   source-lineage fact proves a distinct finalized source bar was available by that open and binds
   the strategy action, order, and exact ledger activation event.

2. Stop-limit orders are excluded from fill candidates on the trigger bar via an
   explicit condition at `ohlc_execution.py:421-423`:
   `not (item[1].intent.order_type == OrderType.STOP_LIMIT and item[2])`
   This correctly enforces trigger/fill separation.

3. All economic arithmetic is Decimal-only. Float is prohibited in `canonical_fingerprint`
   and `_finite_decimal`. No float coercion occurs anywhere in the execution path.

4. The adversarial tests are designed to be run with the repo venv:
   `C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest
   backtesting\execution_accounting_v2\test_hermes_phase3_adversarial.py -q`
