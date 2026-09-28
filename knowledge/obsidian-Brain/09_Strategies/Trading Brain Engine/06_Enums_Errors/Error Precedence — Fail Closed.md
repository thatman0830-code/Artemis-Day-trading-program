---
title: Error Precedence — Fail Closed
governing_amendments: ["001-C2", "003"]
---

# Error Precedence — Fail Closed

- **`DATA_INTEGRITY_ERROR` has the highest precedence.** It outranks market-state interpretation and any analytical calculation.
- **No error rewrites history.** Error records are immutable.
- **No ambiguous duplicate dataset may produce a finalized analytical snapshot.**

## Global Fail-Closed Duplicate Policy (Amendment 001 C2)
```
duplicate canonical uniqueness key within one authoritative source_version
  → DATA_INTEGRITY_ERROR
  → dataset_status = DATA_INTEGRITY_ERROR
  → affected_calculation_valid = FALSE
  → no finalized analytical snapshot produced
```
No silent deduplication. No retain-and-continue. No averaging. No arbitrary record selection.

Supersedes: [[#29.7.2.14 Trade Sequence — Path]] exclude-and-continue wording; [[#29.7.2.17 Portfolio Attribution]] retain-and-continue wording. [[#29.7.2.16 Portfolio-Level Aggregation]] reject-ambiguous-dataset behavior is consistent.

## Not Errors
"No qualifying observation", "no trade", "no fill", `LRL = NONE`, `NOT_CONFIRMABLE`, `R < 2 → REJECTED` are valid outcomes, not errors.

See [[Amendment 001]], [[Amendment 003]], [[Canonical Error Registry]].
