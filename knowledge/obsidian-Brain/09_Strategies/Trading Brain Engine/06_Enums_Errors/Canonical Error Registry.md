---
title: Canonical Error Registry
governing_amendments: ["003", "001-C2"]
---

# Canonical Error Registry (Amendment 003 + owner-authorized additions)

Error records are **immutable**. No error may rewrite history. "No qualifying analytical observation" and "no trade / no fill" are **not** errors. See [[Error Precedence — Fail Closed]].

## Amendment 003 Taxonomy
| Code | Owning module |
|---|---|
| `DATA_INTEGRITY_ERROR` (absolute precedence) | global |
| `SETUP_INVALID` | #27 |
| `EXECUTION_DATA_INVALID` | [[#29.0 Execution Eligibility]] |
| `ENTRY_INVALID` | #29.1 |
| `ENTRY_NOT_FILLED` | #29.1 |
| `POSITION_SIZE_INVALID` | #29.2 |
| `PROTECTIVE_ORDER_INVALID` | #29.3 |
| `TARGET_ORDER_INVALID` | #29.3 |
| `EXIT_RESOLUTION_INVALID` | #29.4 |
| `EXECUTION_COST_INVALID` | #29.5 |
| `POSITION_LIFECYCLE_INVALID` | #29.6 |
| `ACCOUNTING_ERROR` | #29.7.1 |
| `PERFORMANCE_DATA_INVALID` | #29.7.2.* |
| `ATTRIBUTION_INVALID` | #29.7.2.17 |

## Owner-Authorized Additions (additive housekeeping, no schema conflict)
| Code | Owning module |
|---|---|
| `STOP_SELECTION_INVALID` | [[#13 Stop-Loss Selection]] |
| `ACTIVE_RANGE_INVALID` | [[#21 Active Dealing Range]] |
| `PORTFOLIO_STARTING_EQUITY_MISSING` | [[#29.7.2.16 Portfolio-Level Aggregation]] |

## Non-Error Outcomes (NOT ErrorRecord codes)
Per owner semantics, these are **valid non-confirmation / status outcomes**, not infrastructure errors — do not force them into `ErrorRecord`:
- `NOT_CONFIRMABLE` — [[#11 CISD — 1M Confirmation]] §38 (missing valid delivery reference)
- `INVALID_CISD_REFERENCE` — [[#11 CISD — 1M Confirmation]] §39 (reference not opposing required direction)
- `LRL = NONE` — [[#24 LRL Selection]] (no qualifying target)
- `R < 2 → REJECTED` — [[#27 Setup Qualification]]
- `EXPECTED_EXECUTABLE_R < 2 → EXECUTION_INELIGIBLE` — [[#29.0 Execution Eligibility]]
- `AUTHORIZATION_REVOKED`, `ORDER_CANCELED`, `ORDER_EXPIRED`, and `UNFILLED` are lifecycle outcomes, not errors

`DUPLICATE_TRADE_RECORD` (analytics) → **emits** the canonical `DATA_INTEGRITY_ERROR` fail-closed status (Amendment 001 C2).

See [[Amendment 003]], [[Amendment 001]].
