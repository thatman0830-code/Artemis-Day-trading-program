# Offline Test Results

Executed from `C:\Users\fjone\hyperliquid-trading-bot` on 2026-08-27.

| Scope | Command | Result |
|---|---|---|
| Focused v2 neutral contracts | `.\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2\test_specifications.py -q` | 12 passed in 0.79s |
| Complete repository | `.\.venv\Scripts\python.exe -m pytest -q` | 1142 passed in 42.91s |

The focused suite validates immutability, UTC effective intervals, overlap rejection, Decimal-safe
fingerprints, complete ES gate reasons, synthetic/production separation, BTC historical-evidence
gates, mixed-ledger rejection, JSON parsing, and retained source checksums.

Tests used local fixtures and mocks. No test command requested a provider resource, loaded a
credential, submitted an order, or invoked a collector, recorder, or Task Scheduler action. No
archive-writing code was added or called. The only external reads in the milestone were public
first-party documentation pages used to create the pinned normalized source notes.
