# BOT 2.0 Phase 5C v3 — Independent Architecture Review 3

**Conclusion: NOT APPROVED — BLOCKERS REMAIN**

This review does not authorize protected OOS evaluation, model scoring, or walk-forward scoring. Keep the OOS gate closed. No source fixes were made during this review.

## Review identity and scope

- Authorization: user-provided Phase 5C-T final independent architecture review directive.
- Reviewer: a separate, fresh-context review agent that did not participate in implementation; read-only source and artifact review.
- Supplemental verification: the coordinating agent independently checked the external anchor path/hash, reran the focused non-scoring test file with the project virtual environment, and reproduced the current Git-binding failure.
- Repository: `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`.
- Branch: `bot2-phase5c-u-trust-chain`.
- HEAD during review: `4f1d70620a230149046ee52565315de8b9166712`.
- Worktree: dirty; six tracked files modified and three untracked files at review start. The frozen protocol anchor `9a1ecfaf08077252049dd187d44f8641da1186aa` is an ancestor. The reviewed implementation commit pinned in the external anchor is `66caddf995af9c6e78e8852055bae25459b57b18`.
- Prior review record `docs/BOT2_PHASE5C_V3_INDEPENDENT_REVIEW_2.md` was preserved unchanged; this report uses `_3.md` to avoid overwriting the historical NOT APPROVED finding.
- The requested review focused on engineering trust controls only. No protected predictive outputs were opened.

## Protected OOS contamination check

**Protected Phase 5C v3 models scored: 0, based on inspectable repository evidence.** No Phase 5C v3 OOS score/result directory or result artifact was found. The repository `outputs` area contains Phase 5B research artifacts, not Phase 5C v3 predictive results. The Phase 5C v3 runner is preflight-only and declares no scoring implementation. No evidence of Phase 5C v3 OOS or walk-forward scoring was found in the inspected repository/commit history. This does not establish the state of inaccessible external copies or unrelated temporary locations.

**OOS protection status: no repository-visible violation found; gate remains CLOSED.** No A0/A1/A2 experiment, OOS score, or walk-forward score was run for this review.

## Anchor and manifest integrity

- Canonical manifest SHA-256 verified by the repository loader: `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- External anchor file found at `C:\Users\fjone\Downloads\phase5c_v3_external_anchor.txt` (outside the repository); file SHA-256: `58af4b2caf9f02f71f65633b0aeef0e435b0fbefed20de334226bc945aeee0644`.
- `load_verified_manifest(..., external_anchor_path=...)` succeeded and matched the pinned canonical manifest hash. Focused tests also passed manifest mutation/override rejection cases.
- Limitation: the anchor declares itself **unsigned**. The loader proves external path and matching content, not independent custody, authorship, or a user’s separate preservation/comparison. Independent trust-anchor custody remains unverified.
- **Unresolved implementation-pin defect:** the anchor pins reviewed implementation commit `66cadd...`, but current `HEAD` is `4f1d706...`. `verify_git_binding` checks only frozen-protocol ancestry and a clean worktree; it does not enforce the anchor’s reviewed implementation commit. A different clean descendant can therefore satisfy this Git check without being the pinned reviewed implementation.
- The current dirty worktree is rejected by `verify_git_binding` with `IMPLEMENTATION_WORKTREE_NOT_CLEAN`.

## Evidence inspected and test results

The independent reviewer inspected the frozen protocol and manifest, previous NOT APPROVED review, remediation and baseline-comparison reports, Phase 5C v3 runner, manifest verifier, A2 model/preprocessing, integrity/split code, calibration helpers, artifact writer, and focused tests. The separate reviewer did not edit files. Its first pytest attempt used an interpreter without pytest; the coordinating agent then ran the targeted test file with the repository’s Python 3.11.9 / pytest 9.1.1 environment:

```text
python -m pytest -vv -q bot2/phase5c_v3/test_phase5c_v3.py
12 passed in 0.54s
```

The tests are unit/regression tests using synthetic fixtures and do not perform protected OOS scoring. The numerical gradient test uses finite differences with epsilon `1e-3`, absolute tolerance `2e-3`, and relative tolerance `3e-2`; independently reproduced maximum absolute error was `7.46995210647583e-05`, maximum relative error `0.015813231634033937` (PASS).

The prior clean-baseline report records baseline `5,546 passed / 10 skipped / 36 failed` and Phase 5C-S `5,555 passed / 10 skipped / 36 failed`, with 0 new failure IDs at that time. A fresh full-suite comparison was **not** run on this dirty Phase 5C-U worktree, so the current branch’s new-regression count is **not established**. Do not treat the earlier S comparison as current U evidence.

## Requirement findings

| Area | Review result | Evidence / limitation |
|---|---|---|
| Single source of truth / overrides | PASS for tested frozen settings | Verified-manifest type and exact protected-override comparison; adversarial mismatch tests passed. |
| Provenance and artifact binding | PARTIAL / BLOCKED | Artifact code binds manifest, data, model, preprocessing, and lineage; full calibration-to-results execution is not implemented or end-to-end exercised. Reviewed-commit binding defect remains. |
| Atomic, immutable, concurrent artifact writes | PASS for focused synthetic tests | No-replace/atomic write and conflicting concurrent-write behavior exercised by the focused suite; not a protected result artifact. |
| Canonical row identity / duplicates | PASS for focused synthetic tests | Data-derived identities and duplicate/cross-partition rejection exercised. |
| Numerical gradients | PASS | Five probes span three convolution blocks, shared dense layer, and direction head; errors/tolerances above. |
| A2 learning | PARTIAL | Deterministic synthetic fitting test passes and inspects learned parameters; this does not validate production-scale training. |
| A2 causality | PASS for tested implementation | Causal padding/receptive field and future-mutation tests pass; no bidirectional/future pooling found in inspected code. |
| Cadence / sessions / contracts / synchronization | PARTIAL | Synthetic invalid-gap, session/contract, and identity tests exist; no end-to-end protected evaluation harness was reviewed. |
| Frozen temporal partitions | PARTIAL / BLOCKED | Manifest and preflight checks enforce declarations, but runner is preflight-only; no OOS execution path was approved or tested. |
| Purge / embargo | PARTIAL | Authorized split applies interval constraints; synthetic boundaries tested. Full frozen pipeline wiring is incomplete. |
| Train-only preprocessing | PASS for focused synthetic tests | Standardizer accepts train observations and records fingerprints; partition tests passed. |
| Checkpoint selection | PARTIAL | Model code uses train/authorized validation information, but protected runner is not an executable fit/evaluation pipeline. |
| Calibration isolation | PARTIAL | Validation-only guard/artifact helpers exist and focused tests pass; full protocol partition semantics and end-to-end lifecycle remain unverified. |
| Abstention isolation | PARTIAL | Validation-only threshold helper and lineage checks exist; no end-to-end result pipeline. |
| Shuffled-label control | UNRESOLVED | No executable protected experiment harness was established to verify exact frozen seeds/count/constraints. |
| Ablation enforcement | UNRESOLVED | Frozen declaration/preflight checks exist, but the executable OOS runner that would enforce only pre-frozen ablations is absent. |
| A0/A1/A2 baseline fairness | UNRESOLVED | No complete execution pipeline is available to verify equivalent frozen information sets and A0 not being weakened. |
| Production isolation | PASS by changed-file scope | Current diffs are confined to Phase 5C v3 research code/tests/preflight and documentation; no production strategy, deterministic risk, broker, paper-order, or live-execution code changed. A2 trading authority remains NONE. |
| Clean-baseline comparison | PARTIAL / STALE FOR CURRENT TREE | Historical S report indicates 0 new failures then; current U branch is dirty and full-suite comparison was not rerun. |

## Previous blocker disposition

1. Self-referential manifest hash — **RESOLVED**; canonical hash excludes its own hash field and external digest match is enforced.
2. Independent model settings — **RESOLVED for tested protected overrides**; runtime mismatch tests pass.
3. Independent partition tags — **RESOLVED for tested data-derived identity / duplicate cases**.
4. Incomplete manifest/artifact binding — **UNRESOLVED**; artifacts bind manifest identity, but the Git verifier omits the anchor’s reviewed implementation commit binding.
5. Incomplete provenance enforcement — **PARTIAL / UNRESOLVED**; core artifacts are chained, but end-to-end calibration/results provenance is not completed.
6. Artifact overwrite race — **RESOLVED for focused tested writer behavior**.
7. Missing row-uniqueness verification — **RESOLVED for focused tested split/preprocessing behavior**.
8. Missing numerical gradient check — **RESOLVED**; five finite-difference probes pass at documented tolerances.
9. Unclassified full-suite failures — **PARTIAL / UNRESOLVED for current tree**; prior S comparison classifies 36 common failures, but current U worktree has no fresh full-suite comparison.
10. Pending independent review — **REVIEWED; NOT APPROVED**. Independent review cannot substitute for unresolved blockers.

## Blockers and next safe step

1. Do not proceed to OOS scoring: the anchor-to-`HEAD` reviewed-implementation binding is absent and the worktree is dirty, so the preflight Git gate fails.
2. Independent anchor custody is not cryptographically verifiable from the unsigned file alone; user must separately preserve/compare the anchor if the protocol requires independently authenticated custody.
3. Full Phase 5C v3 execution coverage remains incomplete for shuffled-label controls, ablations, A0/A1 fairness, and end-to-end calibration/results lineage.
4. Current Phase 5C-U full-suite failure/regression count has not been reproduced against the same clean baseline in this review.

The next action requires a separately authorized remediation phase. This review itself made no fixes. Preserve the frozen manifest/protocol and prior review record. Do not run OOS evaluation, A0, A1, A2, walk-forward scoring, or any trading execution.

**Final architecture-review conclusion: NOT APPROVED — BLOCKERS REMAIN**

Branch: `bot2-phase5c-u-trust-chain`
HEAD at review: `4f1d70620a230149046ee52565315de8b9166712`
