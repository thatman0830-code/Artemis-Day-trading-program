# BOT 2.0 Phase 5C-Y — Final Blocker Closure

Disposition: **READY FOR INDEPENDENT RUNNER REVIEW**. This is an engineering handoff, not independent approval or authorization to score protected ES/NQ OOS data.

## Frozen boundary and candidate identity

- Branch: `bot2-phase5c-y-protected-experiment-runner`.
- Frozen manifest canonical SHA-256: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`; manifest file unchanged.
- Frozen expected matrix: 5,184 cells. Orchestration reconciled all 5,184 identities; 126 deterministic synthetic engineering cells were computed and verified. The remaining 5,058 cells remain uncomputed. This is not a completed frozen experiment.
- `ENGINEERING_COVERAGE_STATUS=COMPLETE`; `FROZEN_EXPERIMENT_STATUS=NOT_EXECUTED`.
- Protected OOS execution: not authorized. Protected models scored: 0. Protected OOS scores: 0. Trading authority: `NONE`.
- The A2 architecture was not redesigned: input `[8, 24]`, 24 input channels, 7,417 parameters. No live or broker execution, production risk, or paper-order behavior was changed.
- The prior independent-review record is preserved unchanged at `docs/BOT2_PHASE5C_V3_INDEPENDENT_REVIEW_4.md`; that document is historical review evidence for an earlier candidate, not approval of this candidate.

## Implemented blocker closures

### Deterministic engineering coverage

`outputs/phase5c_y_engineering_coverage_final_v2/engineering_coverage_manifest.json` is derived from the frozen manifest before observing any predictive result. It uses structural dimensions only and selects 126 cells: 24 representative comparison groups × three A0 baselines plus A1/A2, plus six shuffled-label control cells (three frozen control seeds for each neural model). It selects no cells by accuracy, loss, confidence, profitability, or other output.

Coverage includes both roots (ES/NQ), all three horizons (5/15/30 minutes), all four walk-forward windows, all five model IDs (three A0, A1, A2), all six A1/A2 ablations, and `NONE` plus every frozen shuffled-label seed for each neural model. A2 is checked on every computed cell for shape `[8,24]` and 7,417 parameters. Ablation execution artifacts bind the canonical runtime ablation identity, TRAIN-only preprocessing hash, 24-channel mask, and post-standardization mask stage.

The coverage-manifest identity is `28c40f2f3270b13c1afd27c25a60f5e2bc88c6159217f7bd58c2a757b9ebf7c5`; the source-implementation digest is `e47f64ead38d6001c99580e8910e07aa79108a9f1270b8169901fa9d83a11f02`.

### Common-comparison evidence

All 24 groups are derived from frozen root × horizon × walk-forward dimensions. Each has actual A0/A1/A2 result artifacts, compatible information contracts, and a published common-comparison record. Alignment uses only authorized eligible observation identity, never model output. Each group has 42 common rows, zero excluded rows, and the row set is hash-bound. The comparison artifact is `outputs/phase5c_y_engineering_coverage_final_v2/common_comparison_records.json`.

### Real intermediate recovery

The runner persists only safe reusable computation boundaries: (1) an atomic `MODEL_TRAINING_COMPLETE` checkpoint containing the actual fitted A1/A2 state and validation logits; and (2) the immutable published cell result, which can reconcile a ledger interrupted before its `COMPLETE` transition. Preprocessing/splits are deterministically rebuilt from the same synthetic input, then their fingerprints and hashes are checked before a model checkpoint can be reused. Calibration/prediction/metric sub-stages are not persisted as reusable artifacts; they are deterministically recomputed from the verified model checkpoint. No fake stage marker is treated as computation evidence.

Checkpoints bind frozen manifest, implementation source digest, dataset identity, cell/root/horizon/seed/WF/model/ablation/control/head, partition fingerprints, preprocessing/input/control/ablation hashes, stage schema, payload hash, and artifact hash. Partial, corrupt, truncated, unexpected, symlinked, wrong-cell, wrong-lineage, and upstream-mismatched artifacts fail closed. Injected interruption after real A1 and A2 training resumes from the published model state; clean and resumed final result/prediction artifacts match exactly. Published-result-before-ledger interruption is separately tested and recovered without recomputation.

## Verification results

- Phase 5C matrix + core + runner suite: **55 passed** (`18` matrix, `16` core, `21` runner); no failures or skips. JUnit: `outputs/phase5c_y_engineering_coverage_final_v2/phase5c_negative_tests.junit.xml`.
- Machine-readable negative-test report: `outputs/phase5c_y_engineering_coverage_final_v2/phase5c_negative_test_report.json` — **PASS**, 55 tests, 0 failures/errors/skips.
- Full BOT 2.0 suite: **123 passed**; JUnit: `outputs/phase5c_y_engineering_coverage_final_v2/bot2_tests.junit.xml`.
- Full repository suite: **5,601 passed, 36 failed, 10 skipped**. Compared with `docs/test_evidence/phase5c-v/baseline_full_suite.log`, exact failing node IDs match: candidate-only failures `0`; baseline-only failures `0`. Machine-readable comparison: `outputs/phase5c_y_engineering_coverage_final_v2/full_repository_baseline_comparison.json`.
- `git diff --check`: passed.
- Engineering coverage report: `outputs/phase5c_y_engineering_coverage_final_v2/engineering_coverage_report.json` — `COMPLETE`, 126/126 selected cells verified, all 24 comparisons verified, full frozen experiment `NOT_EXECUTED`, no protected scoring.

## Seal, trust, and remaining authority limits

The six runtime ablation identities must be recalculated after commit against the exact external-anchor candidate pin; they are intentionally not asserted here from a pre-seal commit. The external Downloads anchor must be updated only after commit to the exact full candidate SHA. Its signature must remain `UNSIGNED` and custody `NOT_CRYPTOGRAPHICALLY_PROVEN`; updating a hash pin does not constitute independent approval or cryptographic custody.

Final preflight must run against that exact post-commit anchor and clean HEAD, and must return `PREFLIGHT_READY_NO_SCORING`. Do not modify the frozen manifest, execute protected ES/NQ OOS, infer results from the subset, or enable trading authority. The full repository still has 36 known baseline failures, although no candidate regressions were found.

The frozen candidate remains subject to a separate independent runner review. This report does not independently approve it, authorize scoring, or advance any later phase.
