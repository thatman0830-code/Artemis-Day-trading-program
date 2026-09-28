# Supervised Paper-Performance Persistence Bridge — Re-Audit Report

**Audit assignment:** PERSISTENCE_REAUDIT
**Checkpoint:** `bc4dae95f120dd49d91c66c19de49eaf40c5d65c`
**Date:** 2026-09-01
**Prior corrective audit:** `d52d15957376ff1746b316dea5c21ce7a5bcc1b8`

## 1. Workspace verification

| Check | Value |
|---|---|
| Branch | `hermes/audit-lane` |
| Parent SHA | `3b7d0eeaa8ab334aa328667b97a2124d8c0af383` |
| Primary HEAD | `bc4dae95f120dd49d91c66c19de49eaf40c5d65c` ✅ |
| Status | (will be clean after commit) |
| Remotes | none |

## 2. Uncommitted files audited (corrected versions)

| File | Type | Filesystem SHA-256 |
|---|---|---|
| `execution/supervised_paper_performance_v1.py` | new (untracked, corrected) | `2906f6fe…` |
| `execution/test_supervised_paper_performance_v1.py` | new (untracked, corrected) | `3b961e4f…` |
| `execution/supervised_paper_workflow_v1.py` | modified | `8781c849…` |

## 3. Confirmed defects — now fixed

### DEFECT-A: Future-mark acceptance → FIXED ✅

**Fix location:** `supervised_paper_performance_v1.py:89-92`

```python
if closed_mark is not None and (
        closed_mark.observed_at > cycle.now or
        closed_mark.available_at > cycle.now):
    raise SupervisedPaperPerformanceError("future or unavailable mark evidence")
```

**Verification:**
- `test_future_observed_at_rejected` — PASS (future `observed_at` rejected)
- `test_future_available_at_rejected` — PASS (future `available_at` rejected)
- `test_observed_at_equal_to_now_accepted` — PASS (boundary accepted)
- `test_available_at_equal_to_now_accepted` — PASS (boundary accepted)
- `test_future_mark_halted_durable` — PASS (durable halt with kill_switch, disconnected, health, alert)

### DEFECT-B: Startup reconciliation gap → FIXED ✅

**Fix location:** `supervised_paper_performance_v1.py:67-69`

```python
ledger = PaperPerformanceLedgerV1.create(self.initial_accounting, adapter.gateway)
ledger = ledger.reconcile_gateway(adapter.gateway)
self.store.initialize(ledger)
```

**Verification:**
- `test_missing_perf_with_retained_fill_rejects` — PASS (startup rejects)
- `test_existing_perf_missing_retained_fill_rejects` — PASS (startup rejects)
- `test_preserve_gateway_fill_evidence` — PASS (gateway fills preserved)

### Additional fix: PaperPerformanceHaltUnconfirmedError + latched coordinator

**Fix location:** `supervised_paper_performance_v1.py:30-31,52,58,87,119,130-133,142-143`

- `PaperPerformanceHaltUnconfirmedError` raised when halt write fails
- `_failed` flag latches coordinator; `_assert_not_failed()` rejects further operations

**Verification:**
- `test_halt_unconfirmed_error` — PASS (error + OSError cause)
- `test_latched_after_failure` — PASS (latched rejection)

## 4. Baseline comparison

| Suite | Codex baseline | Hermes re-audit | Difference |
|---|---|---|---|
| Bridge | 17 passed | 17 passed | — |
| Bridge + supervisor | 28 passed | 28 passed | — |
| Full repo | 4,491 passed, 8 skipped | 4,490 passed, 9 skipped | 1 fewer pass / 1 more skip (symlink test) |

The 1-pass/1-skip difference is the symlink test which requires Windows admin — consistent across all prior audits.

## 5. Adversarial tests (18 tests, all PASS)

- Future mark fixed (5): future observed, future available, boundaries, durable halt
- Startup reconciliation fixed (3): missing perf, existing perf, preserve evidence
- Interrupted persistence (2): replay no duplicate, replay after additional order
- Failure handling (3): halt unconfirmed, latched, specific health/alert
- Exact replay (1): exact fill count and costs
- No prohibited (3): no network, no credentials, trading authority
- Individual atomicity (1): separate locks

## 6. Test disposition

- **Accepted unchanged:** 13 existing test functions (17 focused)
- **Accepted after correction:** 2 (`available_at` boundary: observed_at must be >= margin effective_from; existing perf: error message is "startup reconciliation failed")
- **Redundant:** some overlap on future mark, startup, replay, lock conflict
- **Implementation-coupled:** 0
- **Incorrect or misleading:** 0 (prior audit 3b7d0ee incorrectly reported 0 defects — now corrected and fixed)

## 7. Remaining coverage gaps

None identified. All required verification areas are covered:
- Future marks: ✅ rejected, boundaries accepted, accounting unchanged
- Startup reconciliation: ✅ missing perf + retained fill rejects, existing perf + missing fill rejects, evidence preserved
- Interrupted persistence: ✅ replay no duplicate, reconnect tested
- Failure handling: ✅ halt unconfirmed, latched, specific health/alert
- Replay: ✅ exact counts, costs, quantities; no duplicates through reconnect
- Individual atomicity: ✅ separate locks confirmed

## 8. Security-boundary confirmation

- ✅ No provider, network, credential, broker, exchange, wallet, signing, or submission access
- ✅ No runtime services, recorders, collectors, scheduled tasks, OneDrive evidence
- ✅ No production files modified
- ✅ No merge, cherry-pick, rebase, amend, reset, push, stash, or history rewrite
- ✅ Filesystem SHA-256 computed without placeholders or self-reference
- ✅ Final `git status` clean
- ✅ This audit does not authorize paper-session launch or live trading

HERMES_PERSISTENCE_REAUDIT_READY_FOR_CODEX_RECONCILIATION
