# BOT 2.0 Phase 5C — Preflight Blockers (No Evaluation Performed)

Status: **STOPPED BEFORE MODEL/BASELINE SCORING — NOT READY.** This is a preflight architecture/data-integrity review, not a Phase 5C performance report. No model was trained, no baseline was evaluated, no OOS metric was calculated, and no OOS model result was inspected. The Phase 5C v1 manifest remains unchanged.

## Scope and provenance checks

- Review branch: `bot2-phase5c-protocol-review`, created from Phase 5B commit `6a79f53e653944620fe582be33caccdd370269f9`.
- Frozen Phase 5C manifest: `config/bot2_phase5c_experiment_manifest_v1.json`, canonical SHA-256 `5a1249607d12dd303b0f72210868e984b5791e8bfc8af5b9535bd6e4079d003b`.
- Dataset manifest: canonical SHA-256 `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`.
- Target-distribution artifact: `outputs/bot2_phase5b/target_distributions_v3.json`; its canonical content hash matches the dataset manifest.
- The Phase 5C manifest points to the dataset-manifest hash; target version (`bot2-future-market-state-v3`) and feature version (`bot2-feature-registry-v2`) match. Phase 5A's frozen manifest still hashes to `35188dd73aa2fc94b3e2a4ecffcd7e750d367205e7abeed86de863e6a23181b4` and was not edited.
- Dataset facts remain 438,873 ES bars, 438,806 NQ bars, 438,723 exact synchronized rows, 313 sessions, 2025-06-02 through 2026-08-26. Thirteen label-frequency cells were flagged for severe imbalance in Phase 5B.

## Stop conditions found

1. **The frozen manifest itself blocks OOS.** It sets `requires_separate_architecture_review_before_oos: true`. No separate signed architecture-review artifact or approval is present. A same-turn preflight does not count as that required independent gate.
2. **The frozen v1 protocol does not specify the analyses now required.** It contains one chronological TRAIN/VALIDATION/OOS split, but no Phase 5C walk-forward windows, frozen feature-ablation list, shuffled-label seed/permutation protocol, calibrated reliability-bin count, abstention coverage thresholds, uncertainty-comparison rule, or time-series uncertainty method. The older Phase 5A manifest has some such fields, but its target and feature versions differ; copying them into v1 would silently extend/change the authoritative Phase 5C specification. No such borrowing was done.
3. **Imbalance treatment is not frozen.** The data include rare NQ FLAT classes (below 1% in multiple 15/30-minute splits) and rare 30-minute TREND classes (about 0.5–0.7%). The Phase 5C manifest does not define class weights, sampling, exclusion, or an explicit unweighted-loss policy. Choosing after observing results would violate the instruction. This needs a pre-evaluation choice or an explicit frozen `NONE` policy.
4. **The real feature path is not proven safe across archive gaps.** Phase 5B reports 2,217 missing aggregate minutes for ES and 2,284 for NQ. `bot2/features_labels/features.py` computes horizon/rolling features from the last N observed rows without first requiring exact one-minute cadence. `bot2/neural/sequences.py` enforces a shared session ID but not exact one-minute adjacency (nor an explicit contract-boundary check). A sequence or feature labelled “5-minute” can therefore span more than five elapsed minutes when sparse intervals are present. No full real feature matrix was materialized/validated in Phase 5B. This is a concrete causal/semantic data-integrity blocker; simply reporting missingness is not enough.
5. **The frozen architecture descriptions are not executable enough.** The Phase 5C manifest names A1/A2 but does not freeze A1 width, optimizer/loss/update order, initialization details, class-index mapping, invalid-label eligibility, or A2 transform/head configuration. The code's `CausalTemporalConv.transform` is a fixed sequence-summary transform (mean, last value, and a difference summary), not a learned convolution. The Phase 5C request calls it a causal temporal-convolution candidate, while the manifest names a fixed transform plus MLP. This must be resolved by architecture review, not silently reinterpreted.
6. **A requested simple statistical comparator is not frozen.** The manifest specifies previous-label persistence, TRAIN majority, and a TRAIN transition matrix, but not a logistic/statistical baseline. Existing logistic helper is binary and does not by itself define comparable three-head probabilities, multiclass handling, regularization, or fit protocol. Adding an ad hoc comparator now would change the experiment after its v1 freeze.

## Future protocol draft

`config/bot2_phase5c_experiment_manifest_v2_draft.json` records these unresolved choices while preserving the v1 manifest and its hashes. It is deliberately marked `DRAFT_NOT_FROZEN` and `evaluation_permitted: false`; it is not a replacement manifest and does not authorize training or scoring. A future approved/frozen protocol must specify the missing windows, baselines, class mapping and imbalance handling, A1/A2 training details, shuffle control, ablations, calibration/abstention, uncertainty estimates, and exact valid-row policy. It must also repair/test cadence-aware feature and sequence eligibility against the actual archive, then receive the separate architecture review before OOS work.

## Actions not taken

No baseline or neural training/evaluation was run. No prediction, P&L, trading, risk, execution, or live-trading behavior was changed. No Phase 5C results classification was assigned: the experiment did not reach evaluation, so the evidence cannot classify model improvement or failure.

The pre-existing unrelated worktree modifications were preserved and are not part of this review.

**Phase 5C v1: STOPPED BEFORE OOS — protocol/data blockers remain.**
