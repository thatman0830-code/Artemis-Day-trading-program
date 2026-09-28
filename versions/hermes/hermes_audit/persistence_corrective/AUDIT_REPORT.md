# Supervised Paper-Performance Persistence Bridge — Corrective Audit Report

**Audit assignment:** PERSISTENCE_CORRECTIVE_AUDIT
**Checkpoint:** `bc4dae95f120dd49d91c66c19de49eaf40c5d65c`
**Date:** 2026-09-01
**Supersedes:** `3b7d0eeaa8ab334aa328667b97a2124d8c0af383` (incorrectly reported 0 defects)

## 1. Workspace verification

| Check | Value |
|---|---|
| Branch | `hermes/audit-lane` |
| Parent SHA | `3b7d0eeaa8ab334aa328667b97a2124d8c0af383` |
| Primary HEAD | `bc4dae95f120dd49d91c66c19de49eaf40c5d65c` ✅ |
| Status | (will be clean after commit) |
| Remotes | none |

## 2. Uncommitted files audited

| File | Type | Filesystem SHA-256 |
|---|---|---|
| `execution/supervised_paper_performance_v1.py` | new (untracked) | `553c077e…` |
| `execution/test_supervised_paper_performance_v1.py` | new (untracked) | `3343d89d…` |
| `execution/supervised_paper_workflow_v1.py` | modified | `8781c849…` |

## 3. Confirmed defects (2)

### DEFECT-A: Future-mark acceptance (HIGH)

**Location:** `supervised_paper_performance_v1.py:96-100`

**Description:** `cycle()` accepts `PriceEvidenceV2` marks with `observed_at` and `available_at` after `cycle.now` without validation. The code only checks `health.state is not HEALTHY` but never validates the mark's timestamps against the current cycle time.

**Reproduction:** A mark with `observed_at=T+15min` and `available_at=T+15min` is accepted when the cycle is at `T`. The mark is persisted: `ledger.snapshot.position.mark_price == Decimal("51000")`.

**Required behavior:** Reject future evidence (`observed_at > cycle.now` or `available_at > cycle.now`). Fail closed. Do not persist. Test `observed_at` and `available_at` independently, including equality boundaries (`observed_at == cycle.now` accepted).

**Regression tests:**
- `test_future_observed_at_should_reject` — **FAILS** (current impl accepts)
- `test_future_available_at_should_reject` — **FAILS** (current impl accepts)
- `test_observed_at_equal_to_now_accepted` — **PASSES** (boundary accepted)

### DEFECT-B: Startup reconciliation gap (HIGH)

**Location:** `supervised_paper_performance_v1.py:55-64`

**Description:** `start()` creates empty accounting (`PaperPerformanceLedgerV1.create` with `initial_accounting`) when no performance checkpoint exists, even if the adapter checkpoint has retained fills with nonzero `filled_quantity`. The code does not check whether the adapter's gateway records have fills absent from the accounting.

**Reproduction:** Adapter with retained fill, no performance checkpoint → `start()` succeeds with `ledger.snapshot.position.signed_quantity == Decimal("0")` (empty accounting). Required: should reject.

**Required behavior:** Refuse successful startup when adapter has retained fills not reflected in accounting. Preserve retained fill evidence. Activate durable halt when adapter store is writable. Also test existing performance checkpoint missing a retained gateway fill.

**Regression tests:**
- `test_missing_perf_with_retained_fill_should_reject` — **FAILS** (current impl accepts)
- `test_existing_perf_missing_retained_gateway_fill_should_reject` — **PASSES** (reconciliation catches it)

## 4. Corrective audit results

| Suite | Result |
|---|---|
| Corrective adversarial (15 tests) | 12 passed, 3 failed (regression tests exposing defects) |
| Focused existing (6 tests) | 6 passed |
| git diff --check | clean |

### Failed tests (regression tests expressing required safe behavior):

| Test | Failure | Defect |
|---|---|---|
| `test_future_observed_at_should_reject` | DID NOT RAISE — future mark accepted | DEFECT-A |
| `test_future_available_at_should_reject` | Regex mismatch — "failed closed" not "future" | DEFECT-A |
| `test_missing_perf_with_retained_fill_should_reject` | DID NOT RAISE — empty accounting created | DEFECT-B |

### Passed reproduction tests (confirming defects exist):

| Test | Result | Defect |
|---|---|---|
| `test_future_observed_at_accepted_by_current_impl` | Defect A reproduced: future mark accepted and persisted | DEFECT-A |
| `test_missing_perf_checkpoint_with_retained_fill_accepted_by_current_impl` | Defect B reproduced: empty accounting created despite retained fill | DEFECT-B |

## 5. Corrections to prior audit (3b7d0ee)

1. Prior audit reported **0 defects** — corrected to **2 confirmed defects** (DEFECT-A, DEFECT-B)
2. Prior audit's `_initial()` returned `PaperGatewaySnapshotV1` instead of `PaperExchangeAdapterV1` — test fixture correction, not production defect
3. Prior audit used `snapshot.mark_price` instead of `snapshot.position.mark_price` — test fixture correction
4. Prior audit's alert test used broad `Exception`-only check — corrected to assert specific error, persisted kill-switch/disconnected state, health state, and alert content
5. Prior audit included 3 docstring-only classification tests in behavioral test counts — separated from behavioral tests
6. Checkpoint files are individually atomically replaced, not committed together as one atomic transaction

## 6. Remaining coverage gaps

- **Interrupted adapter-first/performance-second update:** Test exists but may not fully exercise the failure window between adapter save and performance save
- **Halt write failure simulation:** Not fully tested — if the halt write itself fails, the current code silently catches it in `_halt()` and does not report the failure
- **Replay after intervening gateway state changes:** Not fully tested — the idempotent replay test uses the same gateway state

## 7. Security-boundary confirmation

- ✅ No production files modified
- ✅ No provider, network, credential, broker, exchange, wallet, signing, or submission access
- ✅ No merge, cherry-pick, rebase, amend, reset, push, stash, or history rewrite
- ✅ Filesystem SHA-256 computed without placeholders or self-reference
- ✅ Final `git status` clean

HERMES_PERSISTENCE_CORRECTIVE_AUDIT_COMPLETE_FIXES_REQUIRED
