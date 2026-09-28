# V2 Phase 4 Changed File Inventory

## Added

- `accounting.py` — immutable Phase 4 facts, ledger, replay, checkpoints, reconciliation.
- `test_accounting.py` — focused deterministic and adversarial accounting tests.
- `schemas/instrument-accounting-v2.schema.json` — machine-readable Phase 4 contract.
- `PHASE4_INVARIANT_MATRIX.json` — invariant-to-enforcement/test mapping.
- `PHASE4_IMPLEMENTATION_REPORT.md` — scope, ownership, and Phase 5 boundary.
- `PHASE4_CHANGED_FILE_INVENTORY.md` — this inventory.
- `PHASE4_TEST_RESULTS.md` — exact verification commands and results.

## Additively updated

- `__init__.py` — exports Phase 4 public contracts and ledger.
- `PUBLIC_API_SCHEMA_REFERENCE.md` — documents the Phase 4 API.
- `REASON_CODE_CATALOG.md` and `REASON_CODES.json` — additive stable Phase 4 failure codes.
- `test_specifications.py` — updates the expected schema inventory from seven to eight.

No Phase 3 implementation, Core v1, strategy, risk, archive, collector, recorder, credential,
scheduler, provider, exchange, brokerage, wallet, or trading file was modified.
