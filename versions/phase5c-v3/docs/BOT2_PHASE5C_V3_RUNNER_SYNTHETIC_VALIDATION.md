# Phase 5C v3 Runner — Synthetic Engineering Validation

**Date:** 2026-09-22
**Classification:** SYNTHETIC ENGINEERING RESULT — NOT ES/NQ MARKET EVIDENCE — NOT VALID FOR TRADING — NOT VALID FOR MODEL-SELECTION CLAIMS
**Protected OOS:** NOT AUTHORIZED

## What was exercised

The synthetic-only cell uses deterministic in-memory fixture observations and a fixed manifest-approved seed. It exercises the existing authorized split and TRAIN-only standardizer; three A0 baselines; A1 and A2 real-label training across all six runtime-defined ablations; A2 fixed width/parameter count; validation-only A0 selection; per-head calibration and abstention; frozen metric calculation; common validation-row identities; machine-readable model/prediction/result provenance; and shuffled-label controls that actually train both learned candidates without changing validation targets.

The synthetic runner result reports 15 model-result entries (3 A0 baselines plus 2 learned candidates × 6 ablations), 6 ablation executions, and 36 shuffled-control training records (2 candidates × 6 ablations × 3 frozen control repetitions for the selected single seed). This is one ES/5-minute/seed-1 fixture cell, not the full frozen matrix. The numeric/hash outputs from this fixture are engineering diagnostics only.

## Safeguards tested

- `PROTECTED_OOS` is rejected before manifest/data access with `PROTECTED_OOS_NOT_AUTHORIZED`.
- Invalid mode strings fail closed; no generic bypass options exist.
- Existing output paths are rejected without mutation.
- A failed setup publishes a failure-only machine-readable artifact and cannot be overwritten/reused as a completed run.
- Successful result and prediction artifacts are checked against their integrity sidecar when loaded; corrupted prediction content is rejected.
- Repeated identical synthetic runs produce identical result and prediction hashes in the focused runner test.
- No broker import, paper/live order request, production risk change, or authority grant is part of this code path.

The current E2E tests call the lower-level synthetic cell routine with a verified manifest fixture, because the public production entry point intentionally requires an exact, clean, anchor-pinned implementation commit. The working tree is under development and the external anchor is deliberately not advanced while the full-matrix blockers remain.

## Limits

Walk-forward partitions, all roots/horizons/seeds, synthetic test windows, A0-by-ablation materialized comparisons, and hash-verified resume/reuse are not yet implemented. The successful cell therefore cannot establish that the complete frozen experiment executes end to end. No protected model was scored and no protected OOS score was produced.

The specific test totals and full-suite baseline comparison are recorded in the remediation report after final test execution.
