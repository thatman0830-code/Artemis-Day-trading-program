# Phase 5C v3 Runner Remediation Record

**Branch:** `bot2-phase5c-y-protected-experiment-runner`
**Base candidate:** `b0a889bce8d70bd9553b5118429c0f291c1e493f`
**Date:** 2026-09-22
**Disposition:** `BLOCKERS REMAIN`

## Implemented in this remediation

- Added `bot2/phase5c_v3/experiment_runner.py` with explicit PREFLIGHT, SYNTHETIC_VALIDATION, and hard-disabled PROTECTED_OOS modes.
- Restricted supported synthetic execution to the anchor- and clean-commit-bound `run_phase5c_experiment` entry point; the direct fixture bundle helper is private and used only by engineering tests.
- Added an explicit CLI with no bypass flags.
- Orchestrated A0, A1, and A2 for one manifest-bound synthetic ES/5-minute/seed-1 cell, including each frozen feature ablation, actual shuffled-label model training, calibration, abstention, metrics, prediction identity alignment, fairness metadata, and provenance.
- Added failure-only artifacts and atomic publication; existing output locations are immutable. Automatic partial reuse is disabled.
- Made artifact-file publication atomic and no-overwrite, and made result loading reject missing, extra, symlinked, malformed, or schema-incompatible artifacts with stable machine-readable reason codes.
- Added canonical result/prediction integrity files and corrupted-artifact/race checks; a destination that appears during publication is preserved and never replaced by a success or failure bundle.
- Added runtime-ablation hash correction, preserving old documents and frozen runtime definitions.
- Preserved the existing A2 model shape (8 × 24) and parameter count (7,417); no production risk or broker behavior was edited.

## Open blockers — prevent candidate sealing

1. **Incomplete execution matrix:** only one ES/5-minute/seed-1 fixture cell runs. The runner does not orchestrate both roots, every horizon, every manifest seed, or each frozen walk-forward window.
2. **Walk-forward/test path missing:** no authoritative walk-forward split orchestration or synthetic test-partition path exists. The current runner only builds the manifest’s main TRAIN and VALIDATION/CALIBRATION split.
3. **A0 comparison materialization incomplete:** A0 baseline artifacts run once per cell; fairness metadata is repeated for ablation conditions, but complete A0 × ablation result records are not materialized in the result matrix.
4. **Resume contract is conservative but partial:** completed artifacts are immutable and partial outputs are not resumed. Stage-level resume with manifest/commit/seed/stage verification is intentionally not implemented.
5. **Full-suite comparison:** the recorded clean Phase 5C-V baseline in `docs/test_evidence/phase5c-v/baseline_full_suite.log` is 5,546 passed / 36 failed / 10 skipped (5,592 collected). The fresh post-remediation Phase 5C-Y run collected 5,618 tests: 5,572 passed / 36 failed / 10 skipped. Exact failed-node comparison found **0 candidate-only failures and 0 baseline-only failures**; the same 36 known failures remain. The earlier Phase 5C-X review records its own fresh run as 5,562 passed / 36 failed / 10 skipped; that historical run is not substituted for this Y run.
6. **Seal not performed:** because the matrix and test-gate blockers remain, the external candidate anchor remains pinned to the Phase 5C-W candidate; no new candidate SHA is declared, and no post-commit preflight is claimed.

## Authority and protected-data status

- Protected ES/NQ models scored: **0**.
- Protected OOS scores produced: **0**.
- Protected OOS execution: **NOT AUTHORIZED**.
- Trading authority: **NONE**.
- Synthetic data: **engineering validation only**.
- Independent approval: **not performed in this implementation phase**.
- External-anchor signature: **UNSIGNED**.
- Independent custody: **NOT CRYPTOGRAPHICALLY PROVEN**.

## Test evidence

- Focused runner adversarial/synthetic tests: `pytest -q bot2/phase5c_v3/test_experiment_runner.py` — **10 passed**.
- BOT 2.0 suite: `pytest -q bot2` — **94 passed**.
- Full repository suite: `pytest -q --tb=no --junitxml=<temporary report>` — **5,572 passed, 36 failed, 10 skipped** (5,618 collected). The run completed; it is not an all-green suite.
- Failure-node comparison against the recorded baseline file — **36 common failures, 0 candidate-only, 0 baseline-only**. This establishes no new failing test IDs relative to that baseline snapshot, not that the full suite passes or that the unrelated failures are harmless.
- Determinism and artifact integrity: the focused E2E test runs identical fixture/configuration twice and asserts identical result and prediction hashes; loader tests reject corrupted prediction bytes and malformed artifact sets; injected file/directory publication races preserve the competing target.
- Public clean-commit/anchor-pinned synthetic entry and PREFLIGHT were **not** run against a sealed candidate: this branch remains dirty/uncommitted during implementation, and the external anchor has deliberately not been advanced. The lower-level E2E fixture tests do not satisfy that final candidate-binding gate.
