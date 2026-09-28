# BOT 2.0 Phase 5C v3 — Executable Controls (Phase 5C-V)

Date: 2026-09-22
Scope: synthetic/non-protected engineering fixtures only. This document does not authorize model evaluation, OOS scoring, walk-forward scoring, order simulation, or trading.

## Identity boundaries

The scientific protocol remains identified by the frozen v3 manifest and its canonical SHA-256:

`c9ae6da9f8d73708c3a17a28788c80722c5852c48ca658f8ffad75ecb56dc19`

Implementation identity is separate. `VerifiedManifest.pin["review_candidate_commit"]` supplies the implementation candidate commit. The preflight Git gate requires exact `HEAD == review_candidate_commit`, requires the frozen protocol anchor in ancestry, and rejects any dirty tracked or untracked worktree with `IMPLEMENTATION_WORKTREE_NOT_CLEAN`. These implementation repairs do not alter the scientific manifest.

## Executable controls

- `experiment_controls.py` derives model input and ablation contracts from the verified manifest; supplied features, shape, and temporal scope must match those contracts exactly.
- `is_verified_manifest` re-hashes the frozen manifest payload at trust checks; bypassing the wrapper's public immutability or constructing a modified wrapper with the private test token no longer preserves verified status.
- The shuffled-label control consumes only authorized TRAIN rows, uses the frozen seed/run mapping, shuffles each head separately within the frozen root/contract/session/horizon group, preserves group class counts, and emits a deterministic content-hashed assignment artifact. Evaluation partitions are not mutated; the artifact records that no predictions, metrics, or protected-model scores were generated.
- Feature selectors are drawn only from the manifest's six ablation IDs. `apply_ablation_to_rows` physically selects the retained columns in manifest order; arbitrary feature removal/addition and feature-order changes fail closed.
- A0 contracts expose no feature tensor. Label-based A0 inputs carry an information-end timestamp; future label information is rejected. A1 contracts bind the eight-step ordered feature tensor (or frozen ablation subset). A2 contracts bind the eight-step, 24-channel causal tensor and require the final information timestamp to be no later than decision time.
- The A2 ablation width conflict remains explicit: A2 freezes its first convolution at 24 input channels, but the non-ALL ablations remove columns. The manifest does not define channel masking, zero-fill, or a reduced-width A2 architecture. Therefore non-ALL A2 ablation execution rejects with `FROZEN_A2_ABLATION_INPUT_WIDTH_CONFLICT`; no mapping was invented.
- `fit_model_temperature_calibrator` derives logits directly from the bound model instance and validation partition. Calibration artifacts bind manifest, exact candidate commit, dataset, model artifact, preprocessing artifact, validation/calibration partition fingerprint, target/head, method/version, policy digest, logits/label digests, and calibrator digest. OOS fit is rejected.
- `results.py` implements an engineering-fixture provenance envelope. It reconciles model, preprocessing, calibration, split, instrument, horizon, head, seed, ablation/control identity, metrics-configuration digest, and result-content hash. It accepts a fixture digest only; prediction and metric payloads are not generated or accepted.
- The CLI `scripts/run_phase5c_v3_preflight.py --dry-run ...` first runs the focused Phase 5C v3 synthetic/control test suite, and only on success runs the no-scoring data preflight. Its JSON reports the control-test result separately from the data/Git preflight.

## Calibration partition terminology

The frozen manifest says `fit_partition: "VALIDATION only"`; the implementation's only permitted validation object is `VALIDATION_AND_CALIBRATION`, the frozen 2026-01-01 through 2026-02-27 interval. That exact partition label is used consistently in artifacts and guards. It does not include OOS and does not create a new date split.

## Test evidence

Focused command:

```text
python -m pytest -q bot2/phase5c_v3/test_phase5c_v3.py
```

Result: **14 passed**. The tests include exact commit match/mismatch, tracked dirty-tree rejection and clean-tree acceptance, external manifest pin validation, synthetic shuffled-label execution and override rejection, all manifest ablation selectors, unauthorized selector rejection, A0/A1/A2 input contracts and future-information rejection, end-to-end synthetic calibration/result lineage, result corruption rejection, purge/embargo and data-derived row-identity adversarial checks, fixed gradient tolerances, and session/contract/cadence boundary cases. No protected model was scored.

Full-suite fresh comparison and raw outputs are in [BOT2_PHASE5C_V3_FRESH_BASELINE_COMPARISON.md](BOT2_PHASE5C_V3_FRESH_BASELINE_COMPARISON.md) and `docs/test_evidence/phase5c-v/`.

## Status

Shuffled-label, supported ablation, A0/A1/A2 information-contract, calibration-lineage, result-provenance, and integrity controls execute on engineering fixtures. The full Phase 5C-V conclusion is **BLOCKERS REMAIN** until the A2 ablation semantics are resolved by an authorized protocol decision and the external anchor's unsigned custody limitation is independently assessed. This is not approval for protected scoring.
