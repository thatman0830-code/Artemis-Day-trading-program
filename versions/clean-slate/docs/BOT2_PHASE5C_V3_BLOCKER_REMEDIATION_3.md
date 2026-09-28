# BOT 2.0 Phase 5C v3 — Blocker Remediation 3

Date: 2026-09-22
Branch: `bot2-phase5c-v-executable-controls`

This append-only remediation record addresses the blockers in Phase 5C-T independent review #3. Historical review findings remain unchanged.

| Phase 5C-T blocker | Phase 5C-V result |
|---|---|
| Unsigned external anchor / independent custody unproven | Semantics are now explicit and the final external record states `UNSIGNED` and `NOT_CRYPTOGRAPHICALLY_PROVEN`. No signature or independent custody is fabricated. Independent reviewer/user decision remains required. |
| Anchor pinned old implementation while source advanced | Resolved for the candidate via a post-commit external anchor pinning the exact final review-candidate SHA. The earlier repository anchor remains historical and is not represented as independent custody. |
| Git verifier checked ancestry but not exact commit | Resolved in code: `verify_git_binding` compares exact full `HEAD` with the external anchor's `review_candidate_commit`, rejects mismatch with `REVIEWED_COMMIT_MISMATCH`, then checks protocol ancestry and cleanliness. |
| Dirty implementation worktree | Negative test confirms modified tracked content rejects with `IMPLEMENTATION_WORKTREE_NOT_CLEAN`. Candidate is committed and must be clean at post-commit preflight. |
| No fresh full-suite comparison on current tree | Resolved: fresh clean-baseline and candidate `python -m pytest -q` runs used Python 3.11.9 / pytest 9.1.1. Results and exact node IDs are recorded in `BOT2_PHASE5C_V3_FRESH_BASELINE_COMPARISON.md`; raw logs are preserved under `docs/test_evidence/phase5c-v/`. |
| Historical counts did not establish current state | Resolved for the current gate by fresh count plus exact node-ID comparison. The unsupported historical `5,554` quote is distinguished from the reproducible 5,546 baseline and prior 5,555 Phase 5C-S result. |
| Executable shuffle, ablation, A0/A1 fairness, calibration/result provenance missing | Remediated on synthetic fixtures for TRAIN-only shuffled labels, all supported manifest ablations, A0/A1/A2 information contracts, model-to-calibrator binding, and engineering result-artifact lineage. Focused suite: 14 passed. A2 non-ALL ablation remains an explicit incompatibility blocker; no zero-fill/reduced-channel behavior was inferred. |
| Independent review required | Still open by design. This implementation pass does not self-approve or perform the independent review. |

## Verification summary

- Fresh baseline: 5,592 collected; 5,546 passed; 36 failed; 10 skipped.
- Fresh candidate: 5,606 collected; 5,560 passed; 36 failed; 10 skipped.
- Failure sets: 36 common; 0 baseline-only; 0 candidate-only; 0 new unexplained regressions.
- The full repository suite is **not green**. The common failures are absent ignored local data/evidence fixtures and runtime/helper assumptions reproduced in both worktrees; they were not skipped or replaced with fabricated data.
- Gradient check remains at the frozen tolerances: maximum absolute error `7.46995210647583e-05`; maximum relative error `0.015813231634033937` (both within 0.002 / 0.03).
- Canonical manifest SHA remains unchanged: `c9ae6da9f8d73708c3a17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- Protected models scored: 0. Protected OOS execution: NOT AUTHORIZED. Trading authority: NONE.
- No production strategy, risk, broker, paper-order, or live-execution behavior was changed.

## Conclusion

**BLOCKERS REMAIN.** The candidate is for independent re-review only. At minimum, the reviewer must resolve whether the unsigned external anchor is adequate for this research gate and the protocol owner must define a non-redesign A2 ablation mapping or explicitly defer incompatible A2 ablations without changing the frozen science. Do not run OOS or walk-forward scoring in this pass.
