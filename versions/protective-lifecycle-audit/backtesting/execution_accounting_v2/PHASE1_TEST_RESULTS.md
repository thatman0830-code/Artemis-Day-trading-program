# V2 Phase 1 Final Test Results

Executed offline from `C:\Users\fjone\hyperliquid-trading-bot` on 2026-08-27.

| Scope | Exact command | Result |
|---|---|---|
| Phase 1 focused | `.\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2 -q` | 28 passed in 0.85s |
| Complete repository | `.\.venv\Scripts\python.exe -m pytest -q` | 1158 passed in 41.55s |

The commands made no network/provider request and accessed no credential. They invoked no archive
writer, collector, recorder control, Task Scheduler mutation, strategy backtest, broker, wallet,
signing, or order path. Phase 1 tests use synthetic local fixtures and temporary directories only.
