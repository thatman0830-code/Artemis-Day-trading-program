# Codex reconciliation

Date: 2026-08-31

Hermes commit `30f66e6b8a987b03f4ed007120e357c9bdc7575b` contains exactly one adversarial test and four audit artifacts, with no production changes. Those five files were imported by content rather than merging or cherry-picking the divergent audit-lane history.

## Corrected finding

Hermes demonstrated that a CSV row with missing columns caused `item["is_closed"]` to be `None`, leaking `AttributeError`. Accepting either `ArchiveScanError` or `AttributeError` in the adversarial test masked a real public error-contract defect. The submitted statements "no production defects" and "test-side correction" are therefore not accepted unchanged.

The smallest production correction rejects any CSV row containing a missing value before accessing `is_closed`. A focused regression test now requires the exact public `ArchiveScanError` class. No scanning semantics, archive content, recorder, provider, or runtime behavior changed.

The four submitted file checksums describe the pre-correction working files and are retained only as historical audit evidence; they are not checksums of the corrected checkpoint.

## Primary verification

Before importing the adversarial audit files, the corrected primary tree passed:

- Focused archive scanner: 12 passed.
- Complete V2: 1,180 passed.
- Full offline repository: 2,902 passed.

Hermes's isolated-worktree failure count is retained as submitted but is not used to characterize primary because the audit lane lacked the primary repository's current data/archive state.

No providers, credentials, runtime processes, collectors, recorders, scheduled tasks, OneDrive evidence, wallets, brokers, exchanges, signing, or order-submission systems were accessed or modified during reconciliation.
