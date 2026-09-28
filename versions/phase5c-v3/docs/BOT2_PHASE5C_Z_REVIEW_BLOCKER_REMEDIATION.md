# BOT 2.0 Phase 5C-Z Review-Blocker Remediation

**Status: BLOCKERS REMAIN — remediation is incomplete and uncommitted.**

## Starting point and scope

- Remediation branch: `bot2-phase5c-z-review-remediation`
- Parent / reviewed Y candidate: `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`
- Frozen Phase 5C manifest SHA-256: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19` (unchanged)
- The Phase 5C-Y independent review report was preserved without alteration.
- No protected authorization artifact was created; no protected market data was scored or inspected for performance; no OOS metrics were generated; trading authority remains `NONE`.

The Z branch contains the preserved two test-fixture fixes, the no-score guard and its first real-archive structural preflight. A real archive dry run completed without protected inference, but 72 cells remain structurally unready; the authorization/shared-continuation architecture and full verification are incomplete. No commit or anchor update was made.

## Failure reproduction and classification

1. `bot2/phase5c_v3/test_experiment_matrix.py::test_cell_artifact_cannot_be_substituted_across_frozen_identity_axes`
   - Reproduced individually before the fix: **failed**, assertion `DID NOT RAISE ValueError` at the forged-artifact check.
   - Cause: the test hard-coded the forged `model_id` to `A2_LEARNED_CAUSAL_TCN`; sorted frozen identity order can make the selected fixture already A2, resulting in no mutation.
   - Classification: **TEST ISOLATION / FIXTURE DEFECT**, not a demonstrated production acceptance defect.
   - Fix on Z: select a different model ID dynamically from the fixture's actual model ID, preserving the expected fail-closed assertion.

2. `bot2/phase5c_v3/test_experiment_runner.py::test_public_synthetic_entrypoint_requires_clean_pinned_repository`
   - The previous clean-checkout run failed because it expected a dirty repository without creating a dirty fixture. On this reproduction, the test passed individually and in the full suite because the preserved Y review report is an untracked file in the worktree. This demonstrates environment dependence; it is not an order-independent test.
   - Classification: **TEST ISOLATION DEFECT / ENVIRONMENT-FIXTURE DIFFERENCE**.
   - Fix on Z: create a unique temporary untracked marker in the repository for the duration of the assertion and remove it in `finally`, so the negative precondition is explicit and independent of checkout contents.

The two corrected test nodes passed in a combined focused run with the no-score-boundary and protected-mode denial tests (**25 passed**). `py_compile` passed for all modified Python implementation/test files. The Y full-suite reproduction before edits reported 5,600 passed, 37 failed, 10 skipped. Exact comparison with the established baseline found 36 baseline failures, zero baseline-only failures, and one candidate-only failure in this dirty-checkout run (the matrix fixture above). The earlier clean Y review run had two candidate-only failures; the second was the dirty-state test assumption. A Z full-suite comparison has not been performed.

## Z protected real-data preflight — completed, blocked

The new `PROTECTED_PREFLIGHT_NO_SCORE` entrypoint was run against the externally anchored frozen manifest and actual Pass B ES/NQ archive. Its latest receipt is `outputs/phase5cz_protected_preflight_no_score_v7.json`. The call completed as `BLOCKED_NO_SCORE`; it performed structural archive/data/input checks and stopped before model inference or scoring.

| Structural check | Result |
|---|---|
| Manifest SHA-256 (canonical) | `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19` — matches the frozen external anchor |
| Dataset manifest SHA-256 | `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67` |
| Raw archive tree SHA-256 | `405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b` |
| Archive | 650 files; ES 438,873 events; NQ 438,806 events |
| Adapter dataset fingerprints | ES `857fbdcfe324db45b88a364ac3923a5f23ae12017851d93140be3e23a6bd13d4`; NQ `8cc8cb7f803e2de7f7d63f3652feafe8162d16106fd05f11f60cba5dcf7fc323` |
| ES/NQ synchronization | 438,723 exact matches; 150 ES unmatched; 83 NQ unmatched |
| Feature contract | Registry hash `a0c32f664d76bf6e971c5c30cd002fba3aec57826d60f920c24596e70e6fcd3c`; 24 features; schema/order checked |
| Target contract | Frozen target spec hash `4c66debf7805374575451cf5d8d097f16aefed23478cd240e3540bd9943e12c1`; version/horizons checked; structural fingerprint `43639edc733db752be1aab541eb5e0dadba0c51758f4478714af855657947954` |
| Walk-forward | WF1–WF4 derived from the pinned manifest and validated; calendar label-boundary exclusions recorded; elapsed purge applied before the strict validator; validation/calibration embargo remains enforced by the split builder |
| A2 shape and parameter count | `[8, 24]`; 7,417; no protected inference |
| Matrix receipts | 5,184 derived identities; 5,184 unique; 0 duplicates; 5,184 per-cell receipts |
| Cell status | 5,112 `READY`; 72 `NOT_READY` |
| Not-ready reason | All 72: `A0_PRIOR_LABEL_INELIGIBLE` (ES/NQ, 30-minute horizon, WF2, A0 previous-label/transition paths) |
| No-score counters | Protected inference/prediction/probability/metric/P&L/trade-signal/model-score/result-score artifact counters all 0; blocked scoring operations 0; trading authority `NONE` |

The purge-boundary preflight fix applies the manifest's elapsed-time condition (`label_end < first timestamp of next partition - purge_minutes`) before passing rows to the still-strict matrix and split validators. It does not relax those validators. The 72 A0 failures were not suppressed: the existing A0 implementation requires a same-contract/session prior label to be fully matured at each validation decision, and the no-score receipt found at least one ineligible input sequence in those frozen cells. That is a structural readiness failure, not a performance result. No class or outcome distribution is reported.

The six runtime ablation hashes were recomputed and match the independently reviewed Y values: ALL `203dd1ca00c63b0fb81c6bde6f8cc5fff48da81bba6f9737e054e9ac3ec21cba`; MINUS_CROSS_MARKET `e30522babf0e64638c4fc348c6cd7556320a6210e6a8c017fc8e7124a57007c7`; MINUS_SESSION_TIME `5e5c7bdfa36c59ba0ac78b95b02a658e1b4c3a9ae10afbaf5c7ba223c361d4b2`; MINUS_VOLATILITY `4067d7aaf1c138292fc0fc9a36f5c5dd45d4ee1ad481883721bda9e7e36505e3`; MINUS_VOLUME `03dac94bdcf65078121478f85ca41cede47cabd7a88fa695a40fe433560e043a`; MINUS_VWAP `4723cfa603b088be765c58565f4b0e3d6bfc240107aa6c2ddefc693544e42068`.

## Protected execution authorization — not implemented

No authorization schema, authorization artifact verifier, public protected-mode execution path, or synthetic-authorized end-to-end matrix path has been implemented in this remediation. The runner has three distinct mode values, but `PROTECTED_OOS` still rejects unconditionally. Its existing cell executor is synthetic-only. The no-score archive preflight does load real archive data and constructs features, targets, partitions, sequences, and per-cell readiness receipts; it does not hand a shared `VerifiedCellInputs` object to a gated continuation (`VerifiedCellInputs` remains an unused type), and 72 cells fail A0 eligibility.

The real preflight proves structural compatibility only for the 5,112 ready cells; it does not prove a post-authorization real execution path. A synthetic-only authorization contract, exact binding checks, test-only denial matrix, same-input continuation, synthetic end-to-end continuation through A0/A1/A2 and publication/reconciliation, and shared-path identity tests remain unimplemented. A real implementation must keep OOS labels/predictions inaccessible until valid future authorization and must distinguish synthetic results from protected results.

The supplied fixture must be synthetic-only and independently bound to its synthetic archive; a real authorization artifact must not be generated during this remediation. Since the verifier and shared execution machinery are absent, no claims are made for no-auth/wrong-auth denial coverage or authorized synthetic end-to-end execution.

## Frozen controls observed

- The manifest was not changed; its SHA-256 remains `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- The exact Y branch was not modified; Z descends from its exact reviewed commit.
- The matrix was re-derived from the frozen manifest during the Z real-data preflight: 5,184 unique cell identities, zero duplicates. This is a structural ledger result, not completion of the experiment.
- Existing Y engineering evidence remains the previously reviewed 126 structurally selected synthetic cells, ES/NQ, 5/15/30 horizons, WF1–WF4, A0/A1/A2, six ablations, shuffled-label controls, A1/A2 recovery, and 24 common-comparison groups. No new Z revalidation was completed.
- A2 architecture was not changed. The Z real-data preflight rechecked shape 8×24 and 7,417 parameters without inference.
- The six independently recomputed runtime ablation hashes match the Y values listed above. This is a structural identity check, not a model result:
  - ALL `203dd1ca00c63b0fb81c6bde6f8cc5fff48da81bba6f9737e054e9ac3ec21cba`
  - MINUS_CROSS_MARKET `e30522babf0e64638c4fc348c6cd7556320a6210e6a8c017fc8e7124a57007c7`
  - MINUS_SESSION_TIME `5e5c7bdfa36c59ba0ac78b95b02a658e1b4c3a9ae10afbaf5c7ba223c361d4b2`
  - MINUS_VOLATILITY `4067d7aaf1c138292fc0fc9a36f5c5dd45d4ee1ad481883721bda9e7e36505e3`
  - MINUS_VOLUME `03dac94bdcf65078121478f85ca41cede47cabd7a88fa695a40fe433560e043a`
  - MINUS_VWAP `4723cfa603b088be765c58565f4b0e3d6bfc240107aa6c2ddefc693544e42068`

## Verification not completed

The following required gates were not completed on Z: resolving the 72 A0 ineligible cells without changing scientific rules; authorization focused tests; wrong/malformed authorization matrix; authorized synthetic end-to-end publication and reconciliation; shared continuation using the exact verified inputs; Phase 5C, BOT 2.0 and complete repository suites after implementation; two clean-state full-suite runs; candidate-only failure comparison for both runs; post-commit no-scoring preflight; clean committed candidate; external anchor update; and fresh independent review. No execution result may be inferred from the pre-change Y full-suite run.

## Remaining blockers

1. Resolve the 72 A0 prior-label-ineligible inputs within the frozen data/eligibility contract; do not weaken temporal safety or alter A0 scientific behavior merely to force readiness.
2. Implement and independently test the external authorization contract with strict binding to exact candidate commit, manifest, dataset/archive and frozen protocol; keep real authorization absent.
3. Implement the same verified-input continuation path for future protected execution and synthetic-only authorized testing; prove that synthetic authorization cannot access the real archive.
4. Complete wrong/malformed authorization denial tests (zero protected outputs), synthetic post-gate A0/A1/A2 end-to-end execution/publication/reconciliation, and shared-path identity tests.
5. Rerun focused, Phase 5C, BOT 2.0, and full-repository suites twice from clean test states; compare exact failures to baseline and require zero candidate-only failures in both runs.
6. Only after all gates pass, commit Z, run post-commit preflight without real authorization, update the external anchor honestly as unsigned/unproven custody, and request a new independent review.

**Conclusion: BLOCKERS REMAIN.** No protected OOS execution, protected scoring, live trading, or Phase 6 work is authorized.
