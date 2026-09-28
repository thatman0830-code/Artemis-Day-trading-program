# V2 Phase 4 Test Results

Run offline on 2026-08-27 with the repository virtual environment.

```text
python -m pytest backtesting/execution_accounting_v2/test_accounting.py -q
22 passed in 0.87s

python -m pytest backtesting/execution_accounting_v2 -q
241 passed in 1.30s

python -m pytest -q
1371 passed in 42.84s

git diff --check
passed (no whitespace errors)
```

All tests use local deterministic facts. No provider, network, credential, archive, recorder,
collector, scheduler, brokerage, exchange, or trading path was accessed.
