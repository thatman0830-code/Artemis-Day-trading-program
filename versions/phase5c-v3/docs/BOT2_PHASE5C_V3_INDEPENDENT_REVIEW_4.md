# BOT 2.0 Phase 5C v3 — Independent Review 4

**Disposition: NOT APPROVED — BLOCKERS REMAIN**

Review date: 2026-09-22. This is an assessment of the sealed Phase 5C-W candidate only. No implementation, protocol, or model changes were made. No protected model was scored, no OOS performance score was produced, and no trading authority was created.

## Review identity and method

- Exact candidate reviewed: `b0a889bce8d70bd9553b5118429c0f291c1e493f`.
- Branch: `bot2-phase5c-w-fixed-dimension-ablation`.
- A separate fresh-context review agent that did not implement Phase 5C-W inspected the candidate and independently ran selected synthetic-only ablation and gradient checks (4 passed, 12 deselected). It did not run OOS or performance scoring.
- The coordinating reviewer separately verified the exact Git state, independently recalculated the manifest digest, inspected the implementation and prior review evidence, ran the full Phase 5C test module (16 passed), ran the full repository suite, compared exact failure IDs with the frozen baseline, reproduced the numerical gradient check, and ran the supplied post-commit no-scoring preflight.
- Review method: source and test inspection plus synthetic non-protected tests and no-scoring preflight. This is independent engineering review; it is not external cryptographic attestation or authorization to execute.

## Identity, integrity, and scoring gate

1. **Exact commit / HEAD — PASS.** `HEAD` equals `b0a889bce8d70bd9553b5118429c0f291c1e493f`.
2. **Worktree — PASS at review start.** The candidate tree was clean before this report was created. This report is a new uncommitted documentation artifact; it does not change the candidate commit.
3. **Candidate anchor — PASS with limitation.** `C:\Users\fjone\Downloads\phase5c_v3_external_anchor_final.txt` pins both `reviewed_implementation_commit` and `review_candidate_commit` to the requested SHA. The file SHA-256 is `a9274944109ed1a3aa0d350d4ee3b7b52db9d238fb0673475e465841102b736d`. The anchor is explicitly `UNSIGNED`, and independent custody is `NOT_CRYPTOGRAPHICALLY_PROVEN`. The older tracked `docs/phase5c_v3_external_anchor.txt` still refers to a prior candidate; it is historical, not the external anchor used by the passing preflight.
4. **Canonical manifest — PASS.** Independent canonical JSON serialization (sorted keys, compact separators, UTF-8, excluding `manifest_sha256`) recalculates to `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`, matching the file, external anchor, and preflight. The scientific manifest is unchanged.
5. **OOS protection — no violation found in inspected scope.** The manifest has evaluation and OOS-scoring flags false; the preflight reports `models_scored: []`, `oos_performance_scores_produced: 0`, and `trading_authority: false`. The candidate repository has no `outputs/bot2_phase5c_v3/results` directory or Phase 5C v3 score artifacts; its `outputs` tree contains only Phase 5B output. The configured Downloads Phase 5C result directory was absent during review, and repository history contains no Phase 5C v3 scoring commit. This finding covers the project tree, the named Downloads locations, and inspected review evidence—not inaccessible external or temporary copies.
6. **Counts and authority — PASS within inspected evidence.** Protected models scored: 0. OOS scores produced: 0. Trading authority: NONE. Protected OOS execution remains NOT AUTHORIZED.

## Architecture and data controls

7. **A2 architecture — PASS.** The frozen causal TCN remains sequence length 8, 24 input channels, three left-padded causal convolution blocks (kernel width 3; dilations 1, 2, 4; channel widths 24→32→32→16), final-valid-timestep readout, shared 16-unit layer, and three 3-class heads. Parameter count remains 7,417; receptive field is 15. The W ablation change did not alter model architecture, optimizer, or training configuration.
8. **A2 causality — PASS on inspected implementation and synthetic tests.** Convolution reads only current/past indices; the final-timestep readout has no future pooling. Tests cover future-input mutation, left-only padding, sequence cadence, and session/contract boundaries. The frozen sequence length is 8 and cadence is 60 seconds.
9. **Fixed-dimension ablations — PASS in implementation/tests.** `ALL`, `MINUS_CROSS_MARKET`, `MINUS_VWAP`, `MINUS_VOLUME`, `MINUS_VOLATILITY`, and `MINUS_SESSION_TIME` keep A2 input width 24, shape `[batch, 8, 24]`, and 7,417 parameters.
10. **Masking order — PASS.** Raw authorized TRAIN rows are standardized using the TRAIN-fitted transform first, then the frozen mask is applied, then the fixed-width tensor reaches the model. Fit-time validation recomputes the masked tensor from canonical observations and the bound TRAIN preprocessor.
11. **Neutral value — PASS.** All channels use `train-unique-row-population-zscore-v1`; zero in standardized space represents the TRAIN mean. The scale guard for constant TRAIN channels is `1e-12`. Masks do not use validation/calibration/OOS statistics and do not redefine natural missingness.
12. **Feature order — PASS in static contract and negative tests.** The canonical 24-channel order is derived from the verified manifest. Reordered, missing, duplicate, unknown, or wrong-width features fail closed in the tested input/contract path.
13. **Ablation hashes — INVESTIGATED; supplied directive contains two mismatched literals.** Runtime canonical hashes were independently recomputed from the verified manifest and exact candidate pin. `MINUS_VWAP`, `MINUS_VOLUME`, `MINUS_VOLATILITY`, and `MINUS_SESSION_TIME` match the directive. For `ALL`, the directive prints `482acdb0217aa30f94a11452c3ccbf560d5f6828693c7cf16c20d073836992d`; the runtime digest is `482acdb0217aa30f94a11452c3ccbfe560d5f6828693c7cf16c20d073836992d`. For `MINUS_CROSS_MARKET`, the directive prints `faf62abb5fec0cba7ac9a98f6fffe70411dd72b95fa108992a8e8ce4b9f575e39`; runtime produces `faf62abb5fec0cba7ac9a98f6ffe70411dd72b95fa108992a8e8ce4b9f575e39` (one fewer `f`). The runtime values are deterministic and commit-bound; these reference-text discrepancies appear to be transcription errors, but the authoritative identity list should be corrected/confirmed before any protected execution.
14. **Unauthorized masks — PASS in synthetic tests.** Arbitrary/unknown masks, wrong mask length, altered masks, reordered features, model/split mask substitution, and feature-family mismatch are rejected.
15. **A0/A1/A2 fairness — PARTIAL.** Machine-checkable information contracts enforce the same frozen ablation membership: A0 is label-only, A1 has the manifest-defined 8×24-to-192 representation, and A2 uses the same 24 ordered channels and mask. However, these contracts do not provide a Phase 5C end-to-end execution path for the full A0/A1/A2 comparison; see blocker below.
16. **Manifest authority — PASS for inspected controls.** Protected fields derive from the verified manifest, runtime overrides are checked, and mismatch tests fail closed. The preflight verified frozen seeds, target, partitions, metrics, ablation IDs, and disabled scoring/authority flags.
17. **Data-derived row identity — PASS in synthetic adversarial tests.** Identity derives from exact contract, session, and exchange timestamp; fake caller IDs cannot disguise the same observation across partitions.
18. **Partition fingerprints — PASS in synthetic tests.** Fingerprints derive from actual authorized observations and change when content/identity changes.
19. **Cross-partition duplicates — PASS in synthetic tests.** Prohibited overlap is checked among TRAIN, validation/calibration, and OOS identities; duplicate observations are rejected.
20. **Purge/embargo — PASS for implemented fit-time checks and covered fixtures.** The fit boundary validates purged/embargoed rows and partition metadata instead of trusting caller claims. Synthetic tests cover safe, touching/crossing, and manipulated boundaries. Preflight confirms the frozen 30-minute purge and 30-minute embargo policy.
21. **Preprocessing isolation — PASS.** Fitting accepts unique eligible TRAIN observations only, enforces TRAIN dates and manifest feature order, and uses the resulting state for later transforms. OOS fitting is rejected.
22. **Checkpoint isolation — PASS at model API boundary.** Checkpoint selection consumes the authorized `VALIDATION_AND_CALIBRATION` object only; OOS metrics are not an input to selection. This is a shared frozen validation/calibration window, not an independently held-out calibration interval.
23. **Calibration provenance — PASS on synthetic fixtures; execution not performed.** Calibration artifacts bind manifest, candidate commit, dataset, model, preprocessing, validation/calibration fingerprint, head, method/version, and content hash. OOS calibration fitting is rejected.
24. **Abstention isolation — PASS on synthetic fixtures.** Threshold selection is restricted to the frozen validation/calibration object; OOS fitting/selection attempts fail closed.
25. **Shuffled-label control — PASS on synthetic fixtures.** The executable control uses manifest-defined TRAIN-only shuffling, frozen seeds and grouping/constraints, deterministic identity, and provenance binding; unauthorized settings are rejected.
26. **Result provenance — PARTIAL.** Synthetic engineering result envelopes bind protocol/manifest/commit/dataset/partition/model/preprocessing/calibration/instrument/horizon/head/seed/ablation/control/metric and content identities, with corruption rejection. They accept fixture digests and do not generate or verify actual prediction/metric results.
27. **Artifact safety — PASS on synthetic tests.** Writes are atomic/no-overwrite; content hashes and provenance are checked; conflicting duplicate writes fail safely.

## Numerical and test verification

28. **Gradient check — PASS.** Independent finite-difference check over convolution blocks, shared layer, and direction head: maximum absolute error `0.0000746995210647583`; maximum relative error `0.015813231634033937`. Both are within frozen tolerances (`<= 0.002`, `<= 0.03`).
29. **Phase 5C tests — PASS.** Fresh run: 16 passed. The independent reviewer also ran selected ablation/gradient tests: 4 passed, 12 deselected.
30. **BOT 2.0 tests — PASS.** Fresh candidate evidence: 84 passed.
31. **Full repository tests — baseline parity, with known failures.** Fresh run: 5,562 passed, 36 failed, 10 skipped. The exact 36 failed node IDs equal `docs/test_evidence/phase5c-v/baseline_full_suite.log`; comparison found 0 candidate-only and 0 baseline-only failures. Failures are therefore not new candidate regressions, but the full suite is not green. Pytest emitted a cache-write permission warning; it did not affect test outcomes.
32. **Post-commit preflight — PASS, no scoring.** The supplied command returned `PREFLIGHT_READY_NO_SCORING`, `EXACT_REVIEW_CANDIDATE_COMMIT_AND_CLEAN_TREE_VALID`, archive hashes valid for 650 files, and all listed manifest/dataset/split/architecture checks passing. The output explicitly reports no models scored, zero OOS scores, and no trading authority. This is preflight readiness only.

## Production isolation

33. The reviewed commit changes only Phase 5C v3 control/model/data-integrity tests, its ablation contract/configuration, and documentation. No production strategy, deterministic risk engine, broker execution, paper-order execution, or live-trading implementation was changed. A2 trading authority remains NONE.

## Historical blocker disposition

| Historical item | Disposition | Evidence / scope |
|---|---|---|
| Cadence and session/contract boundaries | RESOLVED | Manifest-bound 60-second sequences and synthetic negative tests. |
| Target semantics | RESOLVED for the frozen manifest | Pinned target hash and preflight target specification; no target changes in W. |
| Learned A2 implementation and causality | RESOLVED for model mechanics | Frozen TCN implementation, causal tests, gradient check. |
| Execution harness | UNRESOLVED | CLI is preflight-only; it cannot train/score/evaluate the protected experiment. |
| Manifest integrity | RESOLVED | Independently recomputed canonical SHA-256 matches all pins. |
| External anchor | DOCUMENTED NON-BLOCKING LIMITATION for research review | External file pins candidate, but remains unsigned and custody is unproven. |
| Candidate pin / clean tree | RESOLVED at review start | External anchor matches exact HEAD; clean before this review report. Older tracked anchor is historical/stale. |
| Provenance / data-derived row identity / partition overlap | RESOLVED for tested controls | Synthetic provenance and duplicate adversarial tests. Actual result artifacts not generated. |
| Purge/embargo and preprocessing isolation | RESOLVED for fit-time controls | Synthetic fit-boundary tests and train-only standardizer. |
| Gradient correctness | RESOLVED for checked probes | Numeric errors within frozen limits. |
| Full-suite baseline comparison | RESOLVED as regression comparison | Exact failure-node parity; no candidate-only failures; suite still has 36 baseline failures. |
| Shuffled-label and ablation controls | RESOLVED for synthetic execution | Tests pass; two hash literals in the X reference text are inconsistent with runtime digest. |
| A0/A1/A2 fairness | PARTIALLY RESOLVED | Contracts express common information removal; full comparator execution is absent. |
| Calibration provenance | RESOLVED for synthetic artifact guards | OOS fitting rejects; uses the frozen combined validation/calibration partition. |
| Result provenance | PARTIALLY RESOLVED | Engineering fixture envelope only; no actual metric/result writer. |
| Fixed 24-channel ablation contract | RESOLVED in W implementation | Shape/parameter invariance and mask validation pass synthetic tests. |

## New blockers and final outcome

1. **The sealed code is not executable for the protected Phase 5C v3 experiment.** `docs/BOT2_PHASE5C_V3_EXECUTION_HARNESS.md` expressly says the only CLI is dry-run preflight, there is no model-evaluation command, and scoring artifacts are not written. `results.py` creates/verifies engineering-fixture provenance only. The full frozen A0/A1/A2 experiment cannot be run from this candidate; the manifest-defined A1 comparator has no Phase 5C integrated train/evaluation path. A `PREFLIGHT_READY_NO_SCORING` result does not resolve this gap.
2. **Two directive hash references are inconsistent with the exact runtime canonical digests.** The discrepancy is likely a text typo, but the frozen experiment's authoritative identities must be corrected/confirmed before execution; this review did not change the user-provided directive or candidate.

The unsigned anchor remains an explicitly documented non-cryptographic limitation, not a claim of proven custody. It is not treated as cured by the hash. The older repository-local anchor should not be mistaken for the current external candidate pin.

**Final conclusion: NOT APPROVED — BLOCKERS REMAIN.** Do not execute OOS, score A0/A1/A2, run walk-forward performance, or generate protected metrics. No implementation remediation was performed. Protected models scored = 0; OOS scores produced = 0; trading authority = NONE.

## Requested final-response checklist

1. Review method: separate-context static/code review plus synthetic tests; coordinator repeated verification.
2. Reviewer independence: separate fresh-context reviewer did not implement W; ran four selected tests independently.
3. Exact commit: `b0a889bce8d70bd9553b5118429c0f291c1e493f`.
4. HEAD equality: PASS.
5. Worktree cleanliness: clean before review report creation; report is the sole untracked file now.
6. Canonical manifest SHA-256: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
7. Manifest verification: PASS; independent canonical digest matches.
8. Protected models scored: 0 found in inspected evidence.
9. OOS protection: no violation found in inspected scope; OOS gate remains closed.
10. A2 architecture: PASS, fixed 8×24 input and 7,417 parameters.
11. A2 causality: PASS for inspected code and synthetic tests.
12. Fixed-dimension ablation: PASS in synthetic implementation/tests.
13. Masking order: PASS; TRAIN-only standardization precedes fixed mask.
14. Neutral value: PASS; standardized zero is the TRAIN mean.
15. Feature order: PASS; canonical manifest order, invalid variants fail closed.
16. Ablation SHA: four match; ALL and MINUS_CROSS_MARKET reference literals differ from canonical runtime hashes (see item 13 above).
17. Unauthorized-mask tests: PASS for covered synthetic attacks.
18. A0/A1/A2 fairness: PARTIAL; contracts align information removal, full comparator execution is absent.
19. Manifest authority: PASS for inspected frozen-setting gates.
20. Row identity: PASS for covered synthetic fake-ID/duplicate attacks.
21. Partition fingerprints: PASS for covered content mutation tests.
22. Cross-partition duplicates: PASS for covered TRAIN/validation/OOS cases.
23. Purge/embargo: PASS for covered fit-boundary checks and fixtures.
24. Preprocessing isolation: PASS; TRAIN-only fit enforced.
25. Checkpoint isolation: PASS at API boundary; uses the frozen combined validation/calibration partition.
26. Calibration provenance: PASS on synthetic fixtures; OOS fit rejected.
27. Abstention isolation: PASS on synthetic fixtures; OOS selection rejected.
28. Shuffled-label result: PASS on synthetic fixtures; manifest settings and provenance enforced.
29. Result provenance: PARTIAL; engineering fixture envelope only, no actual score/result generation.
30. Artifact safety: PASS for tested atomic/no-overwrite/hash controls.
31. Gradient maximum absolute error: `0.0000746995210647583`.
32. Gradient maximum relative error: `0.015813231634033937`.
33. Phase 5C tests: 16 passed; independent selected run 4 passed, 12 deselected.
34. BOT 2.0 tests: 84 passed.
35. Full-suite results: 5,562 passed, 36 failed, 10 skipped.
36. Candidate-only regressions: 0; exact failure IDs match baseline.
37. External anchor: candidate pins verified; unsigned and custody unproven.
38. Production isolation: PASS; only research/control/docs files changed in W.
39. Historical blockers: resolved/partial/unresolved dispositions are itemized above; execution harness and full result generation remain unresolved.
40. New blockers: no protected experiment runner/A1 integrated path; two hash-reference discrepancies need correction/confirmation.
41. Final conclusion: **NOT APPROVED — BLOCKERS REMAIN**.
42. Review document: `docs/BOT2_PHASE5C_V3_INDEPENDENT_REVIEW_4.md`.
