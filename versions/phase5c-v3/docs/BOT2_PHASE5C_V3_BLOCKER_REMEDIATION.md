# BOT 2.0 Phase 5C-S — Blocker Remediation

Status: implementation and regression comparison complete; independent review pending. Protected OOS evaluation remains locked.

## Scope and safety boundary

Work is limited to the Phase 5C v3 experimental harness and its tests/reports. The Phase 5A/B, v1/v2, v3 protocol, earlier review, frozen manifest, raw data, and prior preflight artifacts were not rewritten. No protected OOS or walk-forward performance was inspected, no model was scored, and no production strategy, risk control, paper-order path, broker integration, or live execution setting was changed. The runner remains preflight-only.

## Resolved blockers

1. **Self-referential manifest integrity — resolved.** Added `config/bot2_phase5c_v3_manifest.lock.json`; canonical v3 manifest SHA-256 is independently pinned in `bot2/phase5c_v3/manifest.py`. The lock file itself is pinned by SHA-256 in code. The lock also binds the raw archive-tree digest and protocol parent/anchor commits. A verified-manifest wrapper is only constructed by the pinned loader and returns defensive copies.
2. **Independent settings/partition authority — resolved in the harness.** Model construction accepts a verified manifest plus an authorized seed; architecture, target/feature versions, training hyperparameters, seeds, and date windows are derived from it and checked against the frozen specification. Runtime override checks reject unknown or mismatching values. Data partitions carry canonical row/sequence identities; fit-time checks validate partition tags against manifest date windows, market, contracts, cadence, versions, horizon, dataset digest, preprocessing digest, and cross-partition overlap.
3. **Artifact lineage — resolved by enforced bindings.** Artifact identity binds experiment/protocol, manifest, dataset manifest, feature registry, target spec, architecture, seed, market/horizon, sequence cadence/length, partitions/windows, and raw archive tree. Preprocessing must be TRAIN-only and bind to the manifest and feature width. Hash-format, lineage, provenance-chain, and artifact-content checks fail closed.
4. **Artifact overwrite/race — resolved.** Saves serialize to a unique same-directory temporary file, flush and fsync it, then publish with a no-replace hard link and validate the resulting digest. Existing targets are not overwritten; concurrent same-target attempts are covered by a test.
5. **Preprocessing row uniqueness — resolved.** The standardizer requires canonical `(exact contract, session ID, exchange timestamp UTC)` row IDs, TRAIN partition, manifest date/market/contract eligibility, and unique identities. Exact duplicate identities and conflicting duplicate identities have distinct rejection reasons. Cross-partition sequence overlap is rejected.
6. **Numerical gradient checking — resolved.** Finite-difference probes cover each of the three convolution blocks, shared dense block, and a head weight, compared with analytic gradients under fixed tolerances. On the five fixed probes, maximum absolute error was `7.46995210647583e-05` and maximum relative error was `0.015813231634033937`; both meet the configured tolerances (`2e-3` absolute, `3e-2` relative).
7. **Full-suite clean baseline — resolved.** A clean checkout at the exact pre-v3 parent was tested with the same command and interpreter as the remediation worktree. All 36 failure IDs reproduce exactly; no new failures and no resolved baseline failures occurred. Their missing local fixtures and branch-local Python runtime causes are itemized in `BOT2_PHASE5C_V3_BASELINE_COMPARISON.md`.
8. **Independent review / review-record resolution — pending.** A new reviewer must inspect the committed implementation without protected results. The final review verdict and every checklist item will be recorded in `BOT2_PHASE5C_V3_INDEPENDENT_REVIEW_2.md`. No self-approval is claimed.

## Implemented controls and tests

- Causal temporal convolutions use left-only padding, dilations `[1, 2, 4]`, fixed receptive field 15, and final valid timestep T readout. The test mutates future timesteps and asserts all prior outputs remain identical.
- Model fit is restricted to TRAIN and VALIDATION_AND_CALIBRATION; validation-only early stopping is maintained. Protected OOS partitions are not supplied to training, scoring, calibration, abstention, or the preflight run.
- Data identity and split checks use exact instrument/session/exchange timestamp identities, enforce chronology and non-overlap, and validate exact sequence cadence/contract inventories.
- Tests cover deterministic fixed-seed training, manifest/pin mutation and override rejection, malformed and duplicate identities, split leakage, architecture/target/feature mismatch, provenance-chain mismatch, artifact tampering, no-overwrite behavior, and concurrent writers.
- `runner` checks the frozen protocol anchor is an ancestor and refuses to run on a dirty worktree. This intentionally requires the reviewed implementation to be committed before preflight.

## Current test results

- Focused Phase 5C v3 tests: **9 passed in 2.23 s**.
- `bot2` test subset: **77 passed**.
- Full suite: remediation **5,555 passed, 10 skipped, 36 failed**; exact clean baseline **5,546 passed, 10 skipped, 36 failed**. Failure-set comparison: **0 new**, **0 resolved**. Thus the full repository suite is not all-green; the same 36 failures remain and are not attributable to Phase 5C-S changes.
- One environment warning noted during pytest: the worktree `.pytest_cache` denied writing `nodeids`; it did not change the collected test results. The persisted baseline and branch `lastfailed` sets both contain 36 IDs and compare exactly.

## Phase gate

Current state is engineering-remediation-complete pending independent review. `evaluation_permitted=false`, `oos_model_scoring_performed=false`, and `trading_authority=false` remain frozen. The review may approve or block; either result requires stopping without protected OOS evaluation. Do not proceed to Model B/C/D/E or neural fusion.
