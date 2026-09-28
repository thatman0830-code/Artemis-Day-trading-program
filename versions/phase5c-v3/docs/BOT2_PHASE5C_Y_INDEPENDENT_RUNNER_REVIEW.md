# BOT 2.0 Phase 5C-Y Independent Runner Review

**Conclusion: NOT APPROVED — BLOCKERS REMAIN**

## Scope and method

This was an independent review of the sealed Phase 5C-Y candidate only. No implementation files were modified. No protected dataset was scored, no protected model was evaluated, no OOS score was produced, and Phase 6 was not started. Checks included Git state and diffs, independent manifest/anchor and matrix calculations, source-path inspection, a candidate-bound synthetic engineering-coverage run, a no-scoring archive preflight, a protected-mode denial probe using deliberately nonexistent input paths, and the Phase 5C, BOT 2.0, and repository test suites. The review report is the only source-tree file added by this review; generated evidence was written under ignored `outputs/` paths.

## Candidate, manifest, and anchor

| Check | Result |
|---|---|
| Branch | `bot2-phase5c-y-protected-experiment-runner` |
| Required candidate / HEAD | `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb` — exact match |
| Worktree at review start | Clean |
| Manifest SHA-256, independently calculated | `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19` — expected match |
| External anchor | `C:\Users\fjone\Downloads\phase5c_v3_external_anchor_final.txt`; pins exact candidate and manifest |
| Anchor file SHA-256 | `5203d822c24a4bccf9405d8afd5e0fa2e06c9cd9b2b100a95d691a5a26404dae` |
| Signature / custody | `UNSIGNED`; independent custody is `NOT CRYPTOGRAPHICALLY PROVEN` |

The manifest remained frozen at the expected digest. The anchor is a useful external path/content pin, but it is not a cryptographic signature or proof of independent custody.

## Matrix, dispatch, and engineering coverage

I derived the matrix dimensions from the frozen manifest rather than trusting the displayed total. The Cartesian product is **5,184 cells**, with **5,184 unique identities and zero duplicates**: two roots (ES/NQ), three horizons (5/15/30), four windows (WF1–WF4), five model/control pathways (three A0 baselines, A1 MLP, A2 TCN), six ablations, three heads, three candidate seeds, and three shuffle-control seeds in their applicable combinations. Identity construction binds the scientifically relevant dimensions; changing a dimension changes the identity.

The matrix derivation/dispatch/reconciliation utility accounts for all 5,184 identities. However, dispatch accounting is not equivalent to executing the frozen experiment. The candidate-bound synthetic engineering-coverage rerun computed the structurally selected **126** cells and verified 126/126 artifacts across ES/NQ, all horizons and windows, A0/A1/A2, all six ablations, and shuffled-label controls. It reproduced **24 common-comparison groups**, with 42 aligned common rows per group and zero exclusions. Selection was structural, not performance-based. The remaining 5,058 frozen cells were not computed. Evidence status correctly distinguishes `ENGINEERING_COVERAGE_STATUS=COMPLETE` from `FROZEN_EXPERIMENT_STATUS=NOT_EXECUTED`.

The problem is the final edge of the claimed execution chain. `run_phase5c_experiment` rejects `PROTECTED_OOS` unconditionally with `PROTECTED_OOS_NOT_AUTHORIZED` before reading the supplied manifest, anchor, or dataset. The candidate’s actual computation path is synthetic engineering coverage; the matrix orchestration/dispatch records do not establish that the protected runner can execute and reconcile each frozen cell. Therefore the required capability to execute the frozen 5,184-cell experiment is not demonstrated. This is the primary approval blocker.

## A2, temporal controls, comparisons, and artifacts

- A2 remains the frozen causal temporal convolution model: input shape **8 × 24**, **7,417 parameters**, dilations `(1, 2, 4)`, left-only temporal padding and final-valid-timestep readout. No A2 redesign was observed in the candidate diff.
- Causality/future-mutation, fixed-width ablation, masking, sequence-boundary, and leakage controls are present in source and tests. Training is deterministic under the frozen seed; the synthetic learning test verifies parameter updates and the validation-only checkpoint path. The five-point finite-difference gradient probe was independently reproduced: maximum absolute error `7.4699521e-05`, maximum relative error `0.01581323` (within its declared tolerances).
- WF1–WF4 definitions, chronological partitions, purge/embargo requirements and observation-bound fingerprints are sourced from the frozen manifest. Adversarial partition, overlap, lookahead, purge/embargo, and future-sequence cases are covered by the candidate tests; the authorized no-scoring preflight also validated the pinned 30-minute purge/embargo and split definitions.
- TRAIN-only preprocessing is enforced. Calibration and abstention selection are restricted to the authorized validation/calibration partition; OOS fitting is rejected. Shuffled labels are TRAIN-only and bound to frozen control identities/settings.
- A0/A1/A2 common comparisons retain frozen information contracts. The synthetic coverage report verified 24 groups, 42 common rows each, and aligned row identity; row inclusion is eligibility-derived.
- Result and resume artifacts bind to frozen cell/provenance dimensions and use integrity/schema checks, atomic publication/no-overwrite policies, and lineage checks. Synthetic resume/recovery and adversarial artifact controls are exercised by the candidate suite. The coverage report was bound to the exact sealed commit; an older saved coverage bundle bound to the preceding commit was not relied upon.
- Representative negative cases are in the suite (including wrong identity axes, manifest/implementation/data/partition mismatch, duplicated observations, temporal violations, unauthorized preprocessing/ablation/width/calibration/abstention, corrupt/partial artifacts, and resume lineage). The protected-mode probe independently confirmed fail-closed denial before input access. The suite did not produce a clean pass for every negative-test test node; two test setup defects described below remain.

## Ablation-hash investigation

The six sealed runtime hashes were independently reproduced:

| Ablation | SHA-256 |
|---|---|
| ALL | `203dd1ca00c63b0fb81c6bde6f8cc5fff48da81bba6f9737e054e9ac3ec21cba` |
| MINUS_CROSS_MARKET | `e30522babf0e64638c4fc348c6cd7556320a6210e6a8c017fc8e7124a57007c7` |
| MINUS_SESSION_TIME | `5e5c7bdfa36c59ba0ac78b95b02a658e1b4c3a9ae10afbaf5c7ba223c361d4b2` |
| MINUS_VOLATILITY | `4067d7aaf1c138292fc0fc9a36f5c5dd45d4ee1ad481883721bda9e7e36505e3` |
| MINUS_VOLUME | `03dac94bdcf65078121478f85ca41cede47cabd7a88fa695a40fe433560e043a` |
| MINUS_VWAP | `4723cfa603b088be765c58565f4b0e3d6bfc240107aa6c2ddefc693544e42068` |

The older Phase 5C representation used schema `bot2-phase5c-v3-feature-ablation-v1` and described selection of retained features in canonical order (variable-width representation). The current schema, `bot2-phase5c-v3-fixed-dimension-ablation-v2`, hashes the candidate commit, family membership, a 24-position mask, post-TRAIN-standardization zero-mask behavior, and 24 input channels. The feature family membership/order and six excluded families remain the same. The representation and masking contract did change from variable-width selection to a fixed-width mask applied after TRAIN-only standardization with neutral value `0.0`; this is an intentional fixed-dimension contract change authorized by the supplied Phase 5C-W directive, not an unexplained hash-only reserialization. On the reviewed candidate, the six definitions are internally consistent and the current hashes recompute exactly. No unauthorized A2 architecture change was found.

## Protected-data preflight and gate probe

The independently run archive preflight returned **`PREFLIGHT_READY_NO_SCORING`**. It verified the exact candidate and clean tree, manifest/anchor binding, dataset manifest, 650 archive files and tree hash, instrument/session inventory, ES/NQ alignment, frozen date splits, purge/embargo, A2 shape/configuration, control policies, and an empty append-only output destination. The preflight reported `models_scored=[]`, `oos_performance_scores_produced=0`, and `trading_authority=false`.

The protected-mode probe returned **`PROTECTED_OOS_NOT_AUTHORIZED`** using nonexistent input paths, demonstrating denial before data access. Protected models scored: **0**. Protected OOS scores produced: **0**. This proves the review gate is closed safely; it does not prove a protected execution runner is ready.

## Test results and baseline comparison

| Suite | Result |
|---|---|
| Phase 5C | 53 passed, 2 failed |
| BOT 2.0 | 121 passed, 2 failed |
| Full repository | 5,599 passed, 38 failed, 10 skipped |

The full-repository failures were compared by exact test identity with `docs/test_evidence/phase5c-v/baseline_full_suite.log`: 36 baseline failures remain, zero baseline failures disappeared, and **two candidate-only failures** were found:

1. `bot2/phase5c_v3/test_experiment_matrix.py::test_cell_artifact_cannot_be_substituted_across_frozen_identity_axes` — the selected fixture already has model ID `A2_LEARNED_CAUSAL_TCN`; the test's purported mutation sets it to that same value, so the expected rejection is not actually challenged.
2. `bot2/phase5c_v3/test_experiment_runner.py::test_public_synthetic_entrypoint_requires_clean_pinned_repository` — the test expects a dirty-worktree rejection without constructing a dirty fixture; on the required clean, correctly pinned candidate it fails its setup assumption.

These appear to be test-fixture/assumption defects rather than evidence of a demonstrated unsafe acceptance path; manual identity substitution checks and the public guard behaved as expected. Nevertheless they are new candidate-only failures, so the approval requirement of zero candidate-only failures is not met until the tests are made valid and rerun. No remediation was performed.

## Production isolation and authority

The sealed diff is confined to Phase 5C-Y research/runner code, its tests, and research documentation. No production strategy, risk, broker, paper-order, or live-execution file was changed. The candidate and preflight both report trading authority **NONE** / `false`. This review did not place, authorize, modify, or simulate any order.

## Blockers and limitations

1. **Protected execution capability is absent/unproven.** The public entrypoint unconditionally rejects `PROTECTED_OOS`; the actual execution demonstrated is synthetic-only. The 5,184-cell dispatch ledger is not a substitute for a protected-data execution/reconciliation path. The approval standard expressly requires evidence the eventual runner can execute every frozen cell. Do not authorize protected OOS execution on this candidate.
2. **Two candidate-only test failures remain.** Their present causes appear to be invalid test assumptions, but both are required verification cases and the candidate-only regression count is therefore 2, not 0. The sealed candidate must not be modified during this review; a separately authorized remediation/review is needed.
3. **Anchor provenance is not cryptographically independent.** It is unsigned and independent custody is not proven. This was reported transparently; it is not the sole blocker.
4. This report establishes software/test behavior only. Synthetic engineering coverage and no-scoring archive preflight are not protected performance evidence and say nothing about profitability or trading suitability.

## Final authorization

**NOT APPROVED — BLOCKERS REMAIN**

No protected OOS execution, scoring, model changes, tuning, live trading, broker execution, or Phase 6 work is authorized by this review. The candidate and frozen protocol remain unchanged; stop here and return the blockers for a separately authorized remediation and review.
