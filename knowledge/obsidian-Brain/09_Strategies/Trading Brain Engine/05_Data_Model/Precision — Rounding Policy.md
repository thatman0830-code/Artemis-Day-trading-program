---
title: Precision — Rounding Policy
governing_amendments: ["002-R3"]
---

# Precision / Rounding Policy (Amendment 002 R3)

- **Deterministic decimal arithmetic.** No binary-float dependence.
- **≥ 28 significant digits** computation precision.
- **No calculation from rounded display values** (display precision ≠ calculation precision).
- `NULL != 0`. **Exact zero remains exact zero.**
- Distinguish **missing** vs **zero** vs **NULL** everywhere.
- **EQ normalization:** `EQ_raw = (ZoneHigh + ZoneLow) / 2`, normalized to `minimum_tick` via **ROUND HALF UP** (not generic nearest-tick). See [[#28 Entry-Zone Selection]].
- **Quantity floor:** quantity floored to the legal increment. See [[#29.2 Position Sizing]].
- Statistical equality/invariants evaluated at canonical computation precision.

See [[Amendment 002]], [[#29.7.1 Trade Accounting]].
