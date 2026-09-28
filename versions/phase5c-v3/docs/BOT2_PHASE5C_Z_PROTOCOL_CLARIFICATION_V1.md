# BOT 2.0 Phase 5C-Z — A0 Abstention and Comparison Protocol Clarification v1

**Status: PROPOSED — NOT ADOPTED. No scoring or execution authority.**  
**Effective ID if separately approved:** `BOT2-PHASE5C-V3+Z-CLARIFICATION-V1`  
**Current effective protocol remains:** `BOT2-PHASE5C-V3` (subject to existing authorization gates).  
**Original frozen protocol:** `docs/BOT2_PHASE5C_V3_PROTOCOL.md`; canonical manifest SHA-256 `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.  
**Exact original protocol Markdown SHA-256:** `23905DBD4215669477645313B931243A644E83755577C4ABF7AC57A0ADC62667`.  
**Exact original v3 manifest-file SHA-256:** `FB12989A0E4062EA63B0A335D62B718BA02AD3082C42E63372CABC2F035A1FA5`.  
**Clarification SHA-256:** recorded as a detached digest in `docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1.md.sha256` and the coordinator review; the digest is not embedded in this file to avoid self-reference.

This is a prospective scientific-protocol proposal drafted after structural preflight. It preserves the original frozen artifacts byte-for-byte and does not itself amend, supersede, authorize, or activate them. A future experiment must bind to both original protocol/manifest hashes and the separately approved clarification hash. Approval requires a new effective protocol identity, prospective freeze, and independent review before any scoring. This proposal is not a decision to run an experiment.

## 1. Original ambiguous language

The frozen A0 definition says previous-label persistence uses the latest target whose full information interval ends no later than decision time `T`, “otherwise abstain.” The frozen comparison rule says the primary comparison uses the identical intersection of valid observations for every candidate/seed within each root/head/horizon/window and reports excluded counts and reasons. It does not define whether an A0 abstention makes only A0 unavailable, removes the row for every participant, remains in a fixed-denominator score, or makes the cell incomplete.

## 2. Discovery and information boundary

The ambiguity was surfaced during a protected structural preflight when some frozen A0 cells encountered prior-label ineligibility. The review was prompted by structure/readiness, not model performance. The prior no-score receipt reported zero protected inferences, predictions, probabilities, metrics, P&L, and scores. The clarification pass did not rerun the archive or inspect protected predictions, probabilities, outcomes, or performance. The receipt’s structural counts are not used to select this rule or any threshold.

## 3. Definitions

- **Frozen cell identity:** an expected root × head × horizon × walk-forward window × candidate/seed identity already in the frozen matrix. No identity is deleted by this clarification.
- **Target/data-eligible universe `U`:** canonical row IDs satisfying only the frozen source, instrument/contract, session, timestamp, input/data-integrity, target-definition, split, purge, and embargo requirements. Membership must be determined before model inference and without realized target class, prediction correctness, loss, confidence, scores, P&L, or performance.
- **Causal prediction availability `P(m,s)`:** row IDs for which model `m` and required seed `s` have all frozen inputs and state available at decision time `T`, using only the frozen model definition. This is a pre-inference mask, derived and hashed before inference; it is not inferred from successful outputs after the fact. It may not depend on logits, probabilities, entropy, predicted class, target value/class, correctness, loss, or run success.
- **A0 abstention:** a valid row in `U` on which a prior-dependent A0 baseline has no lawful prior state available by `T`. It is recorded as a model-specific abstention with a reason; it does not invalidate the underlying row.
- **Common-comparison rows `C(G)`:** for a predeclared participant group `G`, `C(G) = U ∩ ⋂ P(m,s)` over exactly the models/seeds in that comparison. This is a conditional paired estimand, not a claim about all of `U`.
- **Prediction/runtime failure:** a planned model/seed fails, omits output, emits non-finite/invalid output, or violates the frozen output contract for a row in its precomputed availability mask. This is a fail-closed error, never an exclusion that shrinks `C(G)`.
- **Entropy/selective abstention:** the separate frozen validation-selected entropy-threshold analysis. It does not change `U`, `P`, or primary paired row membership; report its existing realized coverage/rejection counts separately.

All IDs use a canonical stable serialization/order. Hashes bind the complete sorted ID list plus schema/version and comparison-group ID.

## 4. Row eligibility rule

Construct `U` once per frozen comparison group from the exact frozen contract and provenance. A row can leave `U` only for a predeclared, model-neutral source/data/target/split/purge/embargo reason. Target-class values and all model outputs are forbidden as membership conditions. Record every excluded candidate row ID and one primary reason code (plus optional subordinate diagnostics), so counts reconcile exactly to the enumerated source universe. Hash the source universe, `U`, and exclusion ledger before inference.

The same `U` applies to all models in the group. No cross-session, cross-contract, forward-fill, synthetic label, or model-specific data-quality exception is introduced. Existing frozen instrument/session/contract, contiguous-input, full-label-interval, purge, and embargo constraints remain unchanged.

## 5. A0 abstention rule

- `A0_PREVIOUS_LABEL_PERSISTENCE`: emit the most recent eligible target only if its entire information interval ends no later than `T`, it precedes `T`, and it satisfies the frozen root/head/horizon, instrument/contract, and session scope. If none exists, emit no class/probability and record `A0_ABSTAIN_NO_PRIOR_LABEL_ELIGIBLE_AT_T`.
- `A0_TRAIN_TRANSITION_MATRIX`: use only TRAIN transition counts with the frozen Laplace `α=1` rule and a lawful latest prior state. If there is no eligible prior state, emit no transition-conditioned prediction and record `A0_TRANSITION_ABSTAIN_NO_PRIOR_STATE_AT_T`. No synthetic start state, majority fallback, forward fill, future label, or cross-session/contract prior is allowed.
- `A0_TRAIN_MAJORITY`: remains the frozen TRAIN-only per-root/head/horizon majority with lexical tie-break; it does not require a row-specific prior. The separate tie-break remediation proposal is not adopted by this document.
- An abstention is not a prediction, is not a fabricated class, does not erase the row from `U`, and does not itself fail or structurally invalidate the cell. The underlying A0 code and frozen candidate identity remain visible.

**Prospective prior-source rule proposed:** at each `T`, the prior-state stream consists only of target labels from the same exact frozen instrument/contract, session, root/head/horizon, target version, and source identity whose anchor timestamp is `< T` and whose full target-information interval ends `<= T`. Eligible matured labels may originate in any earlier chronological partition and may include an earlier row from the current walk-forward test window only after its information interval has ended by the later decision time. This is a causal streaming baseline, not permission to use a label before maturity or to use future information for its own prediction. Never bridge a session, contract, root/head/horizon, target version, or source. For transition probabilities, counts remain TRAIN-only with frozen Laplace α=1; only the conditioning state follows this matured-prior rule. This rule must be independently reviewed as a prospective clarification; current code's partition choice is not made authoritative by this proposal.

## 6. Common-comparison intersection rule

For each comparison group, freeze the participant set before any protected predictions. The participant set must include the selected comparator(s), every candidate being compared, and all required seeds used by the frozen aggregation. Do not intersect unrelated roots, heads, horizons, or walk-forward windows. Bind the group ID, exact candidate/seed set, original protocol hash, clarification hash, dataset/archive hash, partition fingerprint, `U` hash, and row-mask hashes in a pre-inference receipt.

1. Build `U` and each model/seed's causal-availability mask from frozen inputs and decision-time information before inference; persist and hash them. `U` must be explicit and independently bound, never inferred as the union of model-supplied lists. Require every mask to be a canonical, duplicate-free subset of `U`; reject unknown IDs, reorderings, omissions from the declared source universe, and group mismatches.
2. Derive `C(G)` mechanically from those masks. For any direct A0/A1/A2 head-to-head metric, every participating model/seed uses the exact same `C(G)` and denominator.
3. An A0 abstention remains recorded against `U`. Where it makes a participant unavailable, the row is omitted from the paired metric denominator for every participant in that specific comparison; predictions from A1/A2 may not be used in that head-to-head metric on that row. The row is not deleted from source data, `U`, other independently predeclared comparisons, or coverage reporting.
4. For strongest-A0 selection, validation comparison uses the exact same validation comparison rows for all frozen A0 candidates. After selection is frozen using the existing validation rule, each test/OOS comparison uses the selected A0 and the specified A1/A2 participant set only; an unselected A0 must not restrict the selected-baseline test/OOS denominator.
5. Keep the pre-inference mask distinct from output validation. If inference fails on any row declared available, the affected cell/comparison is `BLOCKED_ERROR`; never recalculate `C(G)` from successful outputs or delete the failed row. Recompute every reported paired metric from prediction/target records indexed by the exact hashed `C(G)` and verify identity alignment and denominator. A caller-supplied “performance blind” flag is not evidence; the receipt must prove derivation from approved inputs and code.
6. A0/A1/A2 candidate definitions, seeds, selection rule, calibration method, metrics, horizons, splits, and model architectures are otherwise unchanged.

This intersection is scientifically appropriate only for **conditional paired comparison**: it ensures equal denominators and paired row identity without scoring an A0 abstention as a fabricated class. It does not estimate performance over all of `U`; availability-dependent row selection can change the population and must be disclosed. Coverage/abstention remains a separate, non-performance diagnostic. The exact `U`, masks, C, hashes, reasons, participants, and denominators must be fixed before inference and target-class values are available to the selection process.

## 7. Cell executability and completion

Cell execution remains prohibited unless all existing independent review, clean-state, artifact, and explicit authorization gates are separately satisfied. This proposal is not an authorization.

Proposed minimum cell disposition vocabulary, subject to independent review:

- `PENDING`: expected frozen identity not started.
- `STRUCTURALLY_INELIGIBLE`: a frozen, model-neutral input/data prerequisite for the identity is absent or invalid; include exact reason. A0-only row abstention is not this state.
- `BLOCKED_ERROR`: a required available model/seed fails, output is missing/invalid, provenance/hash checks fail, or execution cannot satisfy the frozen contract. Fail closed; no denominator shrinkage.
- `EXECUTED_WITH_ABSTENTIONS`: all planned artifacts and row dispositions are present and valid, including one or more legitimate causal A0 abstentions. This describes execution, not statistical adequacy.
- `COMPLETED_INCONCLUSIVE`: artifacts are complete, but common-comparison rows are empty or fail the already frozen support rule. Retain identity and reason; no metric-based claim.
- `COMPLETED`: artifacts and common-row support satisfy frozen criteria and the authorized analysis was completed. Does not imply a favorable result.
- `MISSING`, `DUPLICATE`, and `UNKNOWN`: preserve the existing ledger's distinct audit/error meanings; never normalize them to an A0 abstention or silently omit them.

Every frozen matrix identity remains accounted for exactly once. Partial artifacts are not complete. A cell with some legitimate row abstentions may be executable and complete if the common comparison remains computable and meets frozen support. A cell with no/insufficient common rows is not a scoring success; retain it as inconclusive rather than deleting the identity or relaxing the requirement.

## 8. Metric denominator rule

For every paired primary or secondary head-to-head metric, denominator is exactly `|C(G)|`; all participants' metric inputs use the same canonical row IDs and labels. Record denominator per metric and verify it equals the common-row manifest count. For seed aggregation, require every frozen seed specified by the protocol on every row in `C(G)`; a missing seed output is `BLOCKED_ERROR`, not a row exclusion. Report nonpaired per-model descriptive metrics, if any, under separate labels and never present them as a direct comparison. The validation A0-selection group is the three frozen A0 candidates on their predeclared common validation rows; after selected-A0 freeze, test/OOS paired comparisons include only that selected A0 and the specified A1/A2 candidate/seed group. Thus an unselected A0 cannot shrink the selected-baseline test/OOS set.

No abstention penalty, class, probability, or utility score is invented. Metrics that cannot be computed on a nonempty `C(G)` are absent with a reason, not set to zero.

## 9. Minimum support and cell completeness

The frozen v3 protocol already requires at least 20 eligible session clusters per root/window and at least two distinct sessions containing each of the three target classes in every cell; otherwise the cell is inconclusive. Apply those existing support criteria to the actual common comparison rows used by the relevant metric. No additional raw-row minimum or coverage percentage is created here. If `C(G)` is empty, mark `COMPLETED_INCONCLUSIVE` with `COMMON_COMPARISON_EMPTY`; if it is nonempty but lacks frozen support, use `COMPLETED_INCONCLUSIVE` with `COMMON_SUPPORT_INSUFFICIENT`. Do not tune the support rule using the 72 observed blocked identities or any archive distribution.

Completion means the identity has a complete auditable disposition and required artifacts. It does not mean statistical support is adequate, nor that the cell is READY for inference. Maintain separate fields for artifact completion and inference/support status.

## 10. Coverage and reason-code reporting

For each comparison group, report without selecting cells:

- source candidate count, `|U|`, and a hash of canonical `U` IDs;
- per-model/seed causal-available count and rate against `|U|`;
- per-model/seed abstention count/rate and exact row IDs by reason;
- common count `|C(G)|`, common coverage `|C(G)|/|U|`, and hash of canonical `C(G)` IDs;
- model-neutral row-exclusion counts by frozen eligibility reason;
- runtime/output failures separately (which block; they are not ordinary exclusions);
- the actual denominator for each reported metric and class/session support diagnostics on the fixed common rows;
- separate frozen entropy/selective-coverage and rejection counts, without using them to redefine primary row membership.

Coverage counts/rates and identity hashes are diagnostic/availability statistics, not accuracy, profitability, ranking, or performance. Label conditional metrics explicitly as **conditional on the frozen common-comparison intersection**. Never describe them as full-universe performance.

Proposed machine-readable reason codes (versioned under a new schema; not yet implemented):

- `ROW_EXCLUDED_FROZEN_DATA_RULE:<rule_id>`
- `ROW_EXCLUDED_FROZEN_TARGET_INTERVAL_RULE:<rule_id>` (metadata validity only; never target-class value)
- `ROW_EXCLUDED_FROZEN_SPLIT_PURGE_EMBARGO:<rule_id>`
- `A0_ABSTAIN_NO_PRIOR_LABEL_ELIGIBLE_AT_T`
- `A0_TRANSITION_ABSTAIN_NO_PRIOR_STATE_AT_T`
- `MODEL_INPUT_UNAVAILABLE_AT_T:<model_id>`
- `COMMON_COMPARISON_EXCLUDED_MODEL_UNAVAILABLE:<model_id>`
- `PREDICTION_RUNTIME_FAILURE:<model_id>:<seed>`
- `PREDICTION_OUTPUT_MISSING:<model_id>:<seed>`
- `PREDICTION_OUTPUT_INVALID:<model_id>:<seed>`
- `COMMON_COMPARISON_EMPTY`
- `COMMON_SUPPORT_INSUFFICIENT`
- `MATRIX_IDENTITY_MISSING`, `MATRIX_IDENTITY_DUPLICATE`, `MATRIX_IDENTITY_UNKNOWN`

For each reason, row IDs and counts must reconcile. Use a deterministic primary exclusion reason precedence; preserve secondary diagnostics. A generic model-ineligible reason alone is insufficient.

## 11. A0, A1, and A2 implications

- **A0:** persistence/transition abstain only when their causally required prior state is unavailable under the approved scope. Majority remains TRAIN-only and deterministic. No A0 candidate gets an imputed or fabricated score for an abstention.
- **A1:** architecture, snapshot, seed, features, fit, outputs, and authority are unchanged. A1 predictions on a row excluded from a specific paired comparison due to A0 abstention are not included in that comparison but remain auditable.
- **A2:** architecture, input shape `[8,24]`, 7,417 parameters, training, seed, features, targets, calibration, metrics, ablations, abstention behavior, and authority remain unchanged. No neural change is proposed.

## 12. Walk-forward, calibration, and abstention implications

- Derive `U`, availability masks, and common IDs separately inside each frozen walk-forward root/head/horizon/window/partition. Do not bridge windows or let later windows affect earlier identity sets.
- Validation-only A0 selection uses a single predeclared paired validation set for all A0 candidates. The selected A0 is then frozen before any test/OOS comparison.
- Calibration remains validation-only, with the original temperature grid and fit rule. Fit each existing calibrator on that model's predeclared, causal-available validation predictions only; bind and report fit-row IDs/hash/count, with no target-class-dependent eligibility rule. No test/OOS row or availability may influence fit, threshold, or validation selection. Paired validation comparison metrics use the applicable predeclared common validation rows. This clarification does not change the calibrator or its parameters.
- The frozen entropy-based selective-prediction analysis remains separate: validation-chosen thresholds, requested coverage points, timestamp/instrument/contract tie order, and full cutoff tie groups stay unchanged. Entropy rejection cannot redefine `U`, causal masks, or nonselective primary denominators. For any direct paired selective-performance comparison at a requested coverage point, first apply each participant's already-frozen validation threshold within the fixed `C(G)`, then use the exact intersection of all participants' retained row IDs for that selective paired metric; report each model's own realized coverage, selective intersection count/hash, and conditional denominator. If a valid selective output is absent unexpectedly, fail closed. Keep availability abstentions distinct from entropy rejections. This paired selective intersection is conditional, not population coverage.
- Abstentions due to absent causal A0 prior and frozen entropy-based selective rejections are separate types with separate reasons and denominators.

## 13. Ablation and reconciliation implications

Every frozen ablation/seed/candidate identity remains in the ledger. Any paired claim must identify its participants and common-row hash. Ablations may not receive a different denominator post hoc because their results look favorable. Reconcile the expected matrix exactly: each identity is present once and has one terminal disposition; common-row counts/reasons and metric denominators reconcile to the hashes and ledger. This proposal does not alter the 5,184 expected identity count.

## 14. Explicitly prohibited behaviors

Do not forward-fill a missing prior, use an immature/future label, bridge a prohibited session/contract/root/head/horizon/target-version/source, substitute another baseline, fabricate predictions, change entropy thresholds, select or remove rows by correctness/confidence/loss/target class/P&L/performance, derive U from a union of model rows, compute intersections from successful outputs, change participants or seeds after predictions, shrink denominators after runtime failures, drop identities, relax support/coverage after observing counts, choose rules to improve READY count or rankings, rely on a caller-supplied blindness flag, or treat coverage as performance. Any empty/insufficient group remains an auditable inconclusive identity; no post-hoc status conversion is permitted. No protected scoring, OOS, profitability analysis, or trading action is authorized by this proposal.

## 15. Versioning, effective date, and approval

This file is a separate prospective addendum; original protocol and manifest remain immutable. Proposed ID `BOT2-PHASE5C-V3+Z-CLARIFICATION-V1` is **not effective** until a protocol owner approves it, an independent reviewer approves precision/scientific validity, a clean implementation review proves immutable pre-inference `U`/mask construction, exact common-row metric recomputation, abstention threshold verification, complete row-level reason reconciliation, and correct terminal states, a clean versioned manifest binds both originals and this exact clarification hash, and all separate execution authorization gates pass. Approval/effective timestamp must be recorded prospectively; never backdate it.

The detached SHA-256 in the companion sidecar and coordinator review binds the exact bytes of this proposal. Any edit requires a new version/hash and a new independent review. The future experiment must record the original protocol Markdown hash, canonical original manifest hash and exact manifest-file hash, the approved clarification hash, effective ID, approval evidence, and code/data hashes.

**No scoring authorization. No adoption. Stop for independent review.**
