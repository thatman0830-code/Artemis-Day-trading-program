# Test Results — AUDIT-V2-PHASE1-PHASE2

## Environment

- Python: `C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe` (3.11.9)
- pytest: 9.1.1
- Workspace: `C:\Users\fjone\hyperliquid-trading-bot-hermes`
- Branch: `hermes/audit-lane`
- HEAD: `76fdc05cf0b587e874bcb24bf2f0788e82de7a55`

## Baseline (pre-adversarial)

```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2 -q
```

Result: **49 passed** in 1.23s (exit code 0)

## Adversarial test file (new)

```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2\test_hermes_phase1_phase2_adversarial.py -q
```

Result: **160 passed** in 1.09s (exit code 0)

## Complete focused V2 suite (after adversarial added)

```
C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe -m pytest backtesting\execution_accounting_v2 -q
```

Result: **209 passed** in 1.15s (exit code 0)

## Adversarial test coverage summary

| Category | Tests | Status |
|---|---|---|
| Phase 1: Contract immutability (frozen+slots) | 10 | PASS |
| Phase 1: Decimal-only enforcement (float/int/NaN/Infinity leakage) | 22 | PASS |
| Phase 1: Timezone-naive rejection (all datetime fields) | 13 | PASS |
| Phase 1: Schema version validation | 5 | PASS |
| Phase 1: Specification interval gaps and overlaps | 7 | PASS |
| Phase 1: Evidence checksum validation | 4 | PASS |
| Phase 1: Mixed schema/ledger versions | 2 | PASS |
| Phase 1: Synthetic-fixture leakage | 2 | PASS |
| Phase 1: Eligibility blocker coverage | 6 | PASS |
| Phase 1: Deterministic serialization and fingerprints | 5 | PASS |
| Phase 1: SHA-256 identity validation | 4 | PASS |
| Phase 1: Order type / TIF validation | 6 | PASS |
| Phase 1: Grid validation | 6 | PASS |
| Phase 1: Repository provenance | 4 | PASS |
| Phase 2: State transition graph vs. frozen matrix | 4 | PASS |
| Phase 2: Terminal state immutability | 5 | PASS |
| Phase 2: Zero fills, overfills, quantity conservation | 8 | PASS |
| Phase 2: Cancellation / fill ordering | 3 | PASS |
| Phase 2: Replacement lineage | 4 | PASS |
| Phase 2: Duplicate and conflicting events | 2 | PASS |
| Phase 2: Stale versions | 2 | PASS |
| Phase 2: Equal-timestamp deterministic ordering | 4 | PASS |
| Phase 2: DAY/GTC/IOC constraints | 9 | PASS |
| Phase 2: Stop-limit trigger/fill separation | 5 | PASS |
| Phase 2: Checkpoint/replay equivalence and tamper detection | 5 | PASS |
| Phase 2: Mixed v1/v2 rejection | 2 | PASS |
| Phase 2: Forced close intent | 2 | PASS |
| Phase 2: End-of-data validation | 3 | PASS |
| Phase 2: Negative transition coverage | 3 | PASS |
| Phase 2: Deterministic output comparison | 3 | PASS |
| **Total** | **160** | **ALL PASS** |

## Defects found

No production code defects were found. All 160 adversarial tests pass. The existing 49 tests also pass.

## Reconciliation scope

These counts describe the immutable Hermes audit commit. The maintained integration contains 158
adversarial tests after removing three redundant/misleading negative-transition tests, collapsing
one unused duplicate parametrization, and expanding public non-finite Decimal coverage. Current
integration results are recorded in `CODEX_RECONCILIATION.md`.
