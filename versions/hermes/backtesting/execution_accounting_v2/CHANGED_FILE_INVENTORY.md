# Changed File Inventory

All new files are under `backtesting/execution_accounting_v2/` unless stated otherwise.

## Neutral infrastructure

- `__init__.py`
- `specifications.py`
- `test_specifications.py`
- `schemas/evidence-record-v2.schema.json`
- `schemas/specification-record-v2.schema.json`
- `schemas/execution-assumption-v2.schema.json`
- `schemas/risk-inputs-v2.schema.json`

## Evidence and deliverables

- `AUTHORITATIVE_SPECIFICATION_AUDIT.md`
- `MACHINE_READABLE_SPECIFICATION_EVIDENCE.json`
- `OWNER_INPUT_TEMPLATE.md`
- `PRODUCTION_ELIGIBILITY_MATRIX.md`
- `SOURCE_INVENTORY.json`
- `TEST_RESULTS.md`
- `CHANGED_FILE_INVENTORY.md`
- Nine files in `evidence_snapshots/`, individually enumerated by `SOURCE_INVENTORY.json`

## Existing design artifact amended

- `backtesting/execution_accounting_v2_design/RISK_REASON_CODES.json` — additive stable missing-spec,
  historical-evidence, ambiguity, owner-approval, and instrument-classification reason codes.

No Core v1, archive, collector, recorder, Task Scheduler, strategy, result, credential, brokerage,
wallet, signing, or execution file was modified by this milestone.
