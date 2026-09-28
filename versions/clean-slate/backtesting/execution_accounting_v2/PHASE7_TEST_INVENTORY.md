# Phase 7 Exact Test Inventory

`test_reporting_validation.py` contains 53 deterministic tests covering:

- finalized trade costs, Decimal enforcement, chronology and immutability;
- eight-component reconciliation and unresolved-state finality;
- normal/empty/single/zero-variance metrics, drawdown, recovery, ordering and no-look-ahead;
- point-in-time regime labels and segmentation;
- all seven stress kinds and exact empirical probability of ruin;
- capital-level economic hurdles;
- 200-trade OOS promotion, expectancy, planned R:R, reconciliation and partition gates;
- result replay, duplicate lineage, tamper detection, schema parsing, and authority absence.
- partition relabeling/overlap, non-lowerable promotion floor, market isolation,
  and explicitly required stress/ruin evidence.

`test_specifications.py` also validates discovery of the eleventh V2 machine schema.
