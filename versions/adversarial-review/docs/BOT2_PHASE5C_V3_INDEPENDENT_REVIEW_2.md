# BOT 2.0 Phase 5C v3 — Final Independent Architecture Review

**Conclusion: NOT APPROVED — BLOCKERS REMAIN**

This review does not authorize OOS evaluation, model scoring, or walk-forward evaluation. The experiment remains stopped before protected OOS execution.

## Review identity and scope

- Branch: `bot2-phase5c-s-remediation`
- Exact implementation commit reviewed: `66caddf995af9c6e78e8852055bae25459b57b18`
- Worktree state checked by reviewer: clean at that commit.
- Reviewer method: separate independent agent/context, read-only inspection of the implementation and protocol artifacts; no participation in remediation.
- Reviewer: `/root/phase5c_s_independent_review` (separate review agent; final response supplied independently to the implementer).
- OOS performance, predictions, scores, and model-selection results were not opened by the reviewer.
- The independent reviewer attempted the focused Phase 5C tests but the run did not complete within its review session and was interrupted. Therefore it did not independently reproduce the reported focused-test or full-suite results.

## Protected OOS scoring check

**Protected models scored: 0, based on inspectable repository evidence.** This is an artifact/repository-state check, not a claim about inaccessible external copies.

- The branch has no `outputs/bot2_phase5c_v3` directory.
- The repository `outputs` tree contains Phase 5B artifacts only; no Phase 5C v3 score/result artifacts were found.
- No Phase 5C v3 experiment registry/result artifact was found in the branch file inventory.
- The previously recorded preflight result was `PREFLIGHT_READY_NO_SCORING`, with an empty scored-model list and zero OOS performance scores. That prior evidence is documented in the remediation report; the independent reviewer did not rerun preflight.
- The reviewed commit and tree contain no known OOS result output. Temporary files outside the inspected project tree cannot be conclusively ruled out.

**OOS protection status: no evidence of scoring found; OOS gate remains closed.** No protected OOS evaluation was run for this review.

## Manifest and provenance identities

- Canonical v3 manifest SHA-256, as recorded in the implementation/provenance report: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- Lock-file SHA-256 observed during this review: `7cb99e0862aad63d28896ab888f9422e99737f923a0f8ded8b3dc3238dbc4a32`.
- **External pin verification: FAIL.** The reviewer found the pin file and expected lock digest are both inside the same repository. A future commit can replace both while retaining protocol ancestry. This is a repository-local consistency check, not an independent trust anchor.
- **Single source of truth: PASS with limitations.** Verified manifest is required by the model API and protected overrides are rejected. Separate partition identity/data binding and fit-time purge/embargo enforcement still fail (below).
- **Full artifact/provenance binding: FAIL.** Artifact load verifies artifact/weight hashes and checks the manifest hash in the lineage, but it does not reconcile every provenance-chain value with its corresponding artifact field and source/content hash. Calibration/results and the commit actually used are not fully bound/verified at load.
- **Reproducible end-to-end lineage: FAIL.** Archive→dataset→features→targets→manifest→preprocessing→model→calibration→results is not fully proven by load-time checks; in particular, lineage consistency and code-commit identity remain insufficiently enforced.

## Architecture checklist and evidence

| Area | Result | Independent reviewer’s evidence / limit |
|---|---|---|
| External manifest pin | FAIL | Pin file and expected digest are repository-local; no outside trust anchor or exact reviewed-commit requirement. |
| One authoritative configuration / protected overrides | PASS, limited | Model requires `VerifiedManifest`; protected overrides are rejected. This does not remedy independent partition identity or purge/embargo gaps. |
| Artifact and provenance binding | FAIL | Loader does not reconcile all chain fields with artifact fields/content hashes; manifest hash alone is explicitly compared. |
| Artifact atomicity / no overwrite | PASS | Same-directory temporary write, no-replace hard-link publication, digest validation. Local filesystem semantics only. |
| Concurrent conflicting writes | PASS | No-replace publication and concurrency test support same-destination safety on documented local filesystem. |
| Canonical row uniqueness | PASS | TRAIN standardizer requires canonical IDs and rejects duplicate identities including conflicting values. |
| Cross-partition duplicate leakage | FAIL | Partition identities are caller supplied and not cryptographically/data-wise bound to actual feature/target rows; fabricated distinct IDs can bypass the disjointness gate. |
| Numerical gradients | PASS by source/test inspection; rerun unverified | Test covers conv blocks 1–3, shared dense weights, and output head against finite differences. Previously reported max absolute error `7.46995210647583e-05`, max relative error `0.015813231634033937`; tolerances `2e-3` absolute / `3e-2` relative. Reviewer did not reproduce because the focused test timed out. |
| A2 learned parameters | PASS by inspection | Trainable convolution parameters and output heads are updated by gradient/Adam path; validation-selected checkpoint. No OOS participation observed. |
| A2 causality | PASS by inspection | Left-only padding, final-time readout, future-mutation test; no bidirectional/future pooling identified. |
| Cadence / temporal windows | PASS, limited | UTC, adjacency cadence, and manifest date-window checks exist. Fit-time session/contract transition details were not separately demonstrated by an independent run. |
| Purge / embargo | FAIL | Frozen 30-minute policy is pinned/preflight-checked, but fit validates date windows/identity overlap without enforcing elapsed-time purge and embargo at split boundaries. |
| TRAIN-only preprocessing | PASS by API contract | Standardizer rejects non-TRAIN partition tag; dependent partition identity-to-data weakness remains. |
| Validation-only checkpoint selection | PASS by inspection | Fit requires validation/calibration partition for early stopping; OOS not used. |
| Calibration isolation | PASS as frozen policy only | Preflight pins validation-only calibration and excludes OOS; calibration fitting is not executed in this harness. |
| Abstention isolation | PASS as frozen policy only | Threshold policy is pinned to validation-only and OOS scoring disabled; no OOS fitting observed. |
| Shuffled-label control | PASS as frozen policy only | TRAIN-only control policy and seeds are pinned in manifest/preflight; no protected performance inspected. |
| Ablations and acceptance criteria | PASS | Definitions are manifest-bound and runtime override-protected. |
| Baseline fairness | PASS by report/protocol inspection | Frozen definitions govern A0/A1/A2 information sets; A0 was not found weakened. Not independently executed. |
| Test baseline / regressions | PASS by report only; rerun unavailable | Prior report records same 36 failure IDs on baseline and remediation branch, with no new/resolved IDs. Reviewer did not independently reproduce full-suite comparison. See count discrepancy below. |
| Production isolation / trading authority | PASS | Reviewed Phase 5C runner is preflight-only; no production strategy, risk, broker, paper-order, or live-execution behavior was changed by this review. A2 trading authority remains NONE. |
| OOS uninspected | PASS | Reviewer reports no protected performance, scores, or walk-forward results opened. Repository artifact check found no Phase 5C v3 output directory/results. |

## Previous blocker dispositions

| Previous blocker | Disposition |
|---|---|
| 1. Self-referential manifest hash | **UNRESOLVED** — repository-local pin is not an independent trust anchor. |
| 2. Independent model settings | **RESOLVED** — verified manifest required; protected caller overrides rejected (subject to remaining gates). |
| 3. Independent partition tags | **UNRESOLVED** — caller-provided partition identities are not bound to actual rows; cross-partition duplicate bypass remains possible. |
| 4. Incomplete manifest/artifact binding | **UNRESOLVED** — load-time artifact/provenance equality is incomplete. |
| 5. Incomplete provenance enforcement | **UNRESOLVED** — full lineage/code-commit binding is not established on load. |
| 6. Artifact overwrite race | **RESOLVED** — no-replace atomic publication and concurrency test inspected. |
| 7. Missing row-uniqueness verification | **RESOLVED for canonical TRAIN row IDs** — standardizer rejects duplicate IDs; distinct blocker remains for partition-to-data binding. |
| 8. Missing numerical gradient check | **RESOLVED by implementation/test artifact; independent rerun unverified** — documented finite-difference check exists and prior run passed. |
| 9. Unclassified full-suite failures | **RESOLVED in report, not independently rerun** — the 36 IDs are listed/classified in baseline comparison. |
| 10. Pending independent review | **RESOLVED as a process step, but gate failed** — separate independent review completed and returned NOT APPROVED. |

## Full-suite baseline comparison

Prior recorded test runs, using the main repository’s Python 3.11.9 / pytest 9.1.1 environment and `python -m pytest -q`, were:

| Checkout | Reported result |
|---|---|
| Clean pre-v3 baseline | 36 failed, 5,546 passed, 10 skipped |
| Phase 5C-S remediation branch | 36 failed, 5,555 passed, 10 skipped |

The prior comparison reported identical 36 failure IDs and zero newly failing or resolved IDs; those failures were attributed to absent ignored runtime fixtures or local virtual-environment assumptions. The independent reviewer inspected that report but did not reproduce the runs.

**Evidence discrepancy:** the Phase 5C-T authorization supplied with this review states a previous repository result of 5,554 passed / 10 skipped / 36 failed, while the prior recorded baseline run above is 5,546 passed / 10 skipped / 36 failed. This discrepancy was not resolved during the independent review and remains a documentation/evidence blocker for a fully reproducible baseline comparison. Do not infer regression-free status solely from matching failure IDs until the count discrepancy is reconciled.

Focused Phase 5C tests: prior implementer record says 9 passed; independent reviewer’s attempt did not complete, so independent confirmation is unavailable. The reviewer did not run the full suite.

## Remaining blockers

1. No independently authenticated trust anchor for the external manifest pin; pin can be changed alongside its expected digest in-repository.
2. Artifact loader does not fully reconcile manifest, dataset, feature, target, preprocessing, model, calibration/result provenance fields and hashes.
3. Caller-supplied sequence identities are not bound to the actual rows, so duplicate observations can be relabeled to evade cross-partition leakage checks.
4. Frozen purge/embargo intervals are not enforced at fit-time split boundaries.
5. Independent reviewer could not complete the focused test rerun; test results remain unverified by the reviewer.
6. Baseline pass-count discrepancy (5,546 recorded versus 5,554 in the Phase 5C-T authorization) remains unexplained.

No fixes were made during this review. This document records findings only; remediation belongs to a subsequent authorized phase.

## Final conclusion

**NOT APPROVED — BLOCKERS REMAIN**

Keep the protected OOS gate closed. Do not run A0, A1, A2, protected OOS scoring, or walk-forward scoring. Await a separate remediation authorization, then a fresh independent review of the new committed implementation.
