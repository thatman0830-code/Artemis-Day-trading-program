# Adversarial Test Plan

All tests are offline and deterministic.

- Orders: invalid transitions, duplicate/conflicting IDs, replacement lineage, cancel/fill races,
  DAY/GTC/IOC boundaries, partial-fill conservation, unsupported type/profile rejection.
- OHLC: no same-bar fill, gaps through stops/limits, equality at every boundary, stop-limit trigger
  isolation, both-side collision, adverse tick rounding, zero/missing volume, shared-volume priority.
- Time: equal timestamps, DST/session boundaries, closed-bar visibility, future facts, stale and gapped
  streams, shuffled input producing the same canonical order or a rejection.
- Futures: positive/negative long and short PnL, point value, tick size, commission components,
  initial/maintenance margin, variation settlement, liquidation, rollover overlap and close failure.
- BTC: spot and perpetual profiles, unknown-profile rejection, missing mark/funding, signed funding,
  funding boundary exposure, linear multiplier and unsupported inverse-contract rejection.
- Accounting: every fill balances, realized plus unrealized reconciliation, fee conservation, margin
  availability, duplicate cost prevention, Decimal-only values, no NaN/infinity.
- Risk: each reason code, simultaneous breaches, stable priority, pre/post distinction, forced-order
  lineage, session loss and drawdown boundary equality.
- Results: attribution reconciliation, version-scope isolation, deterministic fingerprints, immutable
  inputs/outputs, split isolation, and no analytics feedback.
- Security/separation: imports and static scans prove no provider, credential, wallet, signing,
  exchange submission, recorder control, archive writes, Task Scheduler, or network dependency.

Acceptance requires all schema examples validate, all truth-table rows have a test, every state edge
has positive and negative tests, all accounting invariants reconcile exactly, and replay fingerprints
match across repeated runs and supported process/hash-seed variations.
