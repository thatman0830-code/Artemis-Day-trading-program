# V2 Phase 3 Test Results

**Date:** 2026-08-27
**Python:** `C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe` (3.11.9)
**pytest:** 9.1.1

## Hermes baseline (before reconciliation)

**Command:**
```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2 -q
```

**Historical Hermes result:** 219 passed in 1.42s (exit code 0)

## Adversarial tests only

**Command:**
```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2\test_hermes_phase3_adversarial.py -q
```

**Reconciled result:** 127 passed in 1.33s (exit code 0)

## Complete v2 suite (with adversarial tests)

**Command:**
```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2 -q
```

**Reconciled result:** 368 passed in 1.74s (exit code 0), including Phase 4.

## Full offline repository suite after reconciliation

**Command:**
```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest -q
```

**Result:** 1498 passed in 44.89s (exit code 0)

## Summary

| Suite | Tests | Passed | Failed | Errors | Duration |
|---|---|---|---|---|---|
| Baseline (original) | 219 | 219 | 0 | 0 | 1.42s |
| Phase 3 adversarial only, reconciled | 127 | 127 | 0 | 0 | 1.33s |
| Focused Phase 4 | 22 | 22 | 0 | 0 | 0.89s |
| Complete v2 suite, reconciled | 368 | 368 | 0 | 0 | 1.74s |
| Full repository, reconciled | 1498 | 1498 | 0 | 0 | 44.89s |

All tests are offline and deterministic. No provider, archive, recorder, collector,
credential, broker, wallet, exchange submission, or live/paper trading path was invoked.
