# Phase 5C v3 Experiment Runner Architecture

**Phase:** 5C-Y implementation work on `bot2-phase5c-y-protected-experiment-runner`
**Disposition:** `BLOCKERS REMAIN` — not a sealed candidate and not approval for protected execution
**Review date:** 2026-09-22

## Scope and safety

This adds a manifest-bound research-runner component; it does not modify strategy, risk, broker, or production execution behavior. The public entry point is `bot2.phase5c_v3.experiment_runner.run_phase5c_experiment`. Its explicit modes are `PREFLIGHT`, `SYNTHETIC_VALIDATION`, and `PROTECTED_OOS`. `PROTECTED_OOS` returns the machine-readable `PROTECTED_OOS_NOT_AUTHORIZED` failure before opening the manifest or data. There is no generic force/skip/bypass flag and no broker or order interface in the module.

`PREFLIGHT` delegates to the existing Phase 5C preflight. The supported synthetic entry requires the verified external anchor and `verify_git_binding` (pinned exact HEAD plus clean worktree); only the underscored fixture helper is used by engineering tests while a candidate is being developed. Scientific settings come only from the verified frozen manifest. No manifest or strategy protocol file was changed.

## Current orchestration path

The implemented synthetic cell follows this path:

1. Verify the frozen manifest wrapper and its non-scoring / no-trading-authority flags.
2. Generate an in-memory synthetic TRAIN and VALIDATION/CALIBRATION fixture; synthetic mode does not open real market-data files.
3. Fit the existing standardizer on TRAIN only and obtain splits through `build_authorized_split`, then validate the resulting split.
4. Run the three A0 label baselines on the common validation rows. Select strongest A0 per head using only the manifest’s stated validation log-loss / macro-F1 / stable-ID ordering.
5. Train the existing A1 NumPy multi-head MLP and A2 causal TCN on each of the six canonical ablations. A2 remains 24 channels, `[batch, 8, 24]`, and 7,417 parameters; the mask remains post-standardization.
6. Execute each frozen shuffled-label control through actual A1/A2 training, with TRAIN-only shuffled assignments and original validation targets.
7. For each model/head, run and verify the existing calibration and abstention helpers, then calculate the frozen classification/calibration metrics and emit row-aligned prediction records.
8. Emit a result, prediction file, and integrity sidecar only after the run is complete. A thrown model/control error discards success-looking staged files and publishes a failure-only JSON artifact with a stage and reason code.

The synthetic fixture labels results as engineering-only, not ES/NQ market evidence, not valid for trading, and not valid for model-selection claims. The fixture binds its observations to the frozen feature/target schemas for contract exercise; it does **not** represent the real archived ES/NQ observations named by the frozen source-manifest hash.

## Versioned artifact schemas

- Runner envelope: `bot2-phase5c-v3-experiment-runner-v1`.
- Prediction record/file: `bot2-phase5c-v3-prediction-contract-v1`.
- Failure artifact: `bot2-phase5c-v3-runner-failure-v1`.
- Integrity sidecar: `bot2-phase5c-v3-runner-integrity-v1`.
- Existing versioned observation, feature, target, model-input, calibration, abstention, and ablation contracts are reused; none are replaced.

Prediction records contain experiment/model/architecture, instrument and contract, horizon/head, stable observation identity and exchange time, logits and calibrated class probabilities, uncertainty and abstention decision/threshold/source, manifest and implementation identity, model/preprocessing/calibration/ablation hashes, seed, partition identity, and partition fingerprint. The result envelope contains the run scope, manifest and dataset-manifest hashes, model results and model-artifact provenance, selected A0 identifiers, metric definitions, prediction payload hash, common-row alignment summary, ablation execution hashes, shuffled-label control records, fairness records, content hash, and explicit protected-scoring/authority fields.

Successful output directories contain `result.json`, `predictions.json`, and `integrity.json`. The integrity sidecar binds exact canonical content hashes, manifest, implementation pin, seed, and mode; loading checks canonical file serialization, pair agreement, sidecar hash, provenance fields, and matrix completeness. The hash chain detects accidental corruption but is not a signature or proof of independent custody. Failure output contains only `failure.json`; incomplete runs do not masquerade as completed results.

## Retry / resume behavior

Artifacts are immutable. Existing output paths are rejected before work begins. Automatic partial reuse/resume is disabled; a retry must use a new output directory and recompute from the verified inputs. This is deterministic and conservative, but it does **not** implement verified stage-level resume. No model or cache artifact is reused.

## Current implementation boundary

This is not yet the complete frozen experiment runner. The implemented API runs one selected synthetic cell (default ES, 5-minute horizon, seed 1) with one TRAIN/VALIDATION fixture. It does not iterate the full ES/NQ × all manifest horizons × all three manifest seeds × every frozen walk-forward window; it does not construct the manifest's walk-forward TRAIN/validation/test partitions; and it does not provide a synthetic test-partition execution path. A0 artifacts are represented once per cell, with fairness records replicated across ablation conditions, rather than materializing a full model-result record for every A0-by-ablation comparison. Therefore the harness has not proved that the complete experimental matrix runs exactly as frozen.

These omissions are explicit blockers in `BOT2_PHASE5C_V3_RUNNER_REMEDIATION.md`. The runner must not be used to infer market performance or for model-selection claims, and protected ES/NQ scoring remains disabled.
