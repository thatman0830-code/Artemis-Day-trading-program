# V2 Phase 5 Reconciliation Test Results

This file records the integration gates, not the isolated Hermes worktree's
runtime-evidence failures.

Required commands:

- `python -m pytest backtesting/execution_accounting_v2/test_hermes_phase5_adversarial.py -q`
- `python -m pytest backtesting/execution_accounting_v2/test_risk_sessions.py -q`
- `python -m pytest backtesting/execution_accounting_v2/test_rollover_funding.py -q`
- `python -m pytest backtesting/execution_accounting_v2 -q`
- `python -m pytest -q`
- `git diff --check`

Results:

- integrated Hermes Phase 5: 123 passed in 1.04s;
- Phase 5 focused: 28 passed in 0.93s;
- Phase 6 focused: 26 passed in 0.91s;
- complete execution/accounting v2: 612 passed in 2.15s;
- full offline repository: 1,743 passed in 43.81s;
- `git diff --check`: passed.

The integrated Hermes inventory contains 123 tests.
