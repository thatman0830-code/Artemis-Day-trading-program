# BOT 2.0 — Phase 5C Protocol v4 Proposal

**Status: PROPOSED — NOT ADOPTED. No implementation, inference, scoring, OOS, or trading authority.**

| Identity | Value |
|---|---|
| Proposed protocol ID | `BOT2-PHASE5C-V4` |
| Version | `4.0.0-proposal.1` |
| Machine companion | `config/bot2_phase5c_v4_protocol_proposal.json` |
| Original protocol | `BOT2-PHASE5C-V3`, unchanged and retained as historical evidence |
| Original manifest canonical SHA-256 | `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19` |
| Dataset identity | Bind to the existing frozen v3 data/source identity; do not re-materialize or change data because of the structural result |

This is a new, prospective research-protocol design, not a patch or retroactive reinterpretation of V3. V3's disposition is **`NON_EXECUTABLE_AS_WRITTEN_DUE_TO_PROTOCOL_AMBIGUITY`**, not “failed.” V3 files and hashes remain immutable. This document makes explicit new V4 scientific choices where V3 was incomplete; those choices require protocol-owner and independent scientific approval before use.

## 1. Why a new protocol; performance-blind disclosure

A protected structural no-score preflight disclosed 5,184 expected cells, 5,112 structurally ready, and 72 structurally blocked. The observed pattern was 36 ES and 36 NQ paths, all 30-minute/WF2 for prior-dependent A0 baselines. The pattern is disclosed for provenance only; it is not a selection criterion, sample-size target, or reason for any rule below. The new rules apply identically across ES/NQ, all 5/15/30-minute horizons, all WF windows, and every comparable future occurrence.

The pre-existing no-score receipt reports protected inference 0, predictions 0, probabilities 0, metrics 0, P&L 0, scores 0, and trades 0. This design did not rerun the protected archive or inspect protected outputs/performance. No rule was selected to improve readiness, coverage, rankings, or a metric.

The five independent design reviews agree that V3 does not determine A0 prior source/no-prior transition behavior, abstention denominators, or calibration interactions. They differ on whether the board/coordinator should choose those prospectively now or leave them for owner decision. This proposal chooses explicit, conservative defaults for a *new* protocol; each is identified below as a V4 choice, not frozen V3 intent. A fresh reviewer may reject the proposal.

## 2. Scope and invariants

V4 preserves the existing dataset identity, instruments, feature/target contracts except for the eligibility rule explicitly stated below, horizons, WF windows, seeds, A0/A1/A2 architecture/training definitions except the newly specified A0 output semantics, A2, and the absence of trading authority. It does not redesign A2, tune hyperparameters, change features/targets, select rows by results, run inference, or calculate metrics.

The entire pipeline is staged as:

```text
frozen source + protocol validation
  → structural row universe and pair-eligibility ledgers (hash/freeze)
  → model inference
  → validation-fitted calibration transform
  → frozen selective-abstention decision
  → score under predeclared primary/secondary denominator
  → performance reporting
```

The row identities for primary paired comparisons are fixed before inference. Inference, calibration, abstention, scores, and P&L cannot add/remove rows from those primary sets.

## 3. Original-protocol ambiguity and candidate decisions

| Decision | Candidate options | V4 choice and rationale | Bias/statistical risk | Causal implication |
|---|---|---|---|---|
| Missing prior for persistence/transition | Abstain; exclude a cell; fallback to majority/marginal; impute | Explicit per-row unavailability/abstention; no fallback. This preserves each baseline's identity and cannot fabricate information. | Coverage can differ; report it and use pair-specific sets. Cell-level exclusion loses valid observations and is not used. | No forecast may use a prior not fully matured at `T`. |
| Paired rows | One three-way intersection; separate pair sets; full-U penalty | Fixed pair-specific sets for each named comparison; a separate three-way set is sensitivity-only. This preserves A1-vs-A2 population when A0 lacks a prior. | Pair populations can differ, so comparisons are explicitly conditional; report `U`, pair counts, and coverage. No pair is chosen by sample size. | All pair masks are determined from frozen structural prerequisites before inference. |
| Inference-time entropy abstention | Drop rows; penalize abstentions; score probabilities plus coverage curve | Primary nonselective metrics use all pre-inference pair rows and available probabilities; frozen abstention affects only separate, fully reported selective metrics. | Selective metrics have a different conditional denominator; label them separately and never substitute for primary results. | Thresholds remain validation-only and frozen before test/OOS. |
| Calibration and A0 | Neural-only, all candidates, or no calibration | Apply the same temperature-scaling algorithm to each candidate's native probability output; bind model/seed and validation fit rows. A0 without an output due to missing prior is not calibratable. | Model-specific fit rows can differ; disclose fit-row identities and coverage. No OOS information can affect them. | Calibration follows inference and cannot change primary eligibility. |
| Partition boundary for features | Existing 30-minute guard; full sequence+feature dependency; shared history | Require a 37-minute input dependency guard (30-minute feature lookback + 7-minute sequence offset) for partition-start scoring/calibration rows, and purge prior labels by their exact interval. | More conservative row loss, applied uniformly and based on dependency geometry, not the observed 72 cells. | Prevents raw feature dependencies from crossing evaluation partition boundaries. |

## 4. V4 A0 definitions

These are new explicit V4 semantics. V3 is not changed. All classes use the exact frozen vocabulary/order from the manifest; the lexical rule below applies to class labels, not probability-index decoding.

| Baseline | Inputs and source | V4 prediction/probability | Missing information | Tie/session behavior |
|---|---|---|---|---|
| `A0_TRAIN_MAJORITY` | Eligible TRAIN labels only, per root/head/horizon. | Constant categorical forecast with Laplace-smoothed TRAIN frequencies: `p(c)=(n_c+1)/(N+K)`. Predicted label is a maximum-count class. | If TRAIN has no eligible labels for a frozen cell, `STRUCTURAL_BLOCKED_A0_TRAIN_EMPTY`; do not synthesize a class. | Lexicographically smallest frozen class label among tied maxima. No row-specific prior; same contract/session scoring scope as the comparison rows. |
| `A0_PREVIOUS_LABEL_PERSISTENCE` | Fully matured historical labels in the same root/head/horizon, exact listed contract, and exact session, available by `T`. For V4 only, source history may include earlier chronological partitions and earlier test-window labels whose target interval has ended by `T`; no current/future label. | One-hot forecast for the latest eligible prior label. | If none exists, set `A0_UNAVAILABLE_NO_MATURED_PRIOR`; no prediction/probability, no forward fill, fallback, or imputation. | Session/contract reset; use the latest strictly earlier anchor with interval end `<=T`. Duplicate/conflicting labels at the same identity are a data-integrity block, not an arbitrary tie. |
| `A0_TRAIN_TRANSITION_MATRIX` | TRAIN-only adjacent valid label pairs for the same root/head/horizon, exact contract/session, and expected one-minute cadence; no gap or partition-crossing pair. Counts use Laplace `α=1`. Conditioning state uses the same matured-prior stream/scope as persistence. | Smoothed conditional transition distribution from the TRAIN matrix and the latest eligible prior state. | If no matured conditioning state exists at `T`, set `A0_UNAVAILABLE_NO_MATURED_PRIOR`; no unconditional marginal, majority fallback, synthetic start-state, or fabricated transition. | Reset at exact session/contract boundaries. Transition edges require both targets to be valid, adjacent at the frozen cadence, and fully within TRAIN. Probability decoding uses frozen lowest-class-index argmax; this does not alter lexical A0-majority tie semantics. |

V4 explicitly selects a causally matured stream for prior-dependent baselines. A previous evaluation label becomes usable only after its full future information interval has ended before a later `T`; it can never be used to predict its own label or any earlier row. This is a deliberate prospective definition—not a claim that V3 specified the source partition. If independent review rejects online matured prior labels from prior OOS rows, V4 is not approved until a new rule is proposed and reviewed.

For categorical log loss, all probabilities are normalized and clipped only under the frozen metric convention. A0 abstentions have no probability vector and are not assigned a guessed class or loss.

## 5. Structural eligibility and pre-inference ledgers

### 5.1 Structural universe `U`

For each frozen comparison group, `U` is the canonically sorted set of decision-row IDs that satisfy only the frozen dataset/source identity, schema, instrument, exact contract/session, timestamp, sequence, feature/target interval metadata, partition, purge, and embargo contracts. Structural membership can use metadata that a required interval/source row exists and is correctly bounded; it must not use target class/value, prediction, confidence, correctness, score, loss, P&L, return, Sharpe, or run success.

Build and hash the complete candidate source universe, `U`, and its excluded-row ledger before inference. Each excluded row gets one deterministic primary reason from a frozen precedence table, with secondary diagnostics permitted but not replacing the primary cause. Counts must reconcile exactly. Do not derive `U` as the union of models' prediction/output rows.

### 5.2 Pair-specific eligibility

Before inference, enumerate all comparison groups from this protocol and the frozen experiment matrix. For each group `G`, define `PAIR_ELIGIBLE(G)` as `U` intersected with the availability masks for exactly the participants and seeds in that pair, computed from frozen model-definition prerequisites at `T`.

- Required pairs: `A1 vs selected A0`, `A2 vs selected A0`, `A2 vs A0-majority`, `A2 vs A0-persistence`, `A2 vs A0-transition`, and `A1 vs A2`.
- The first two remain the confirmatory acceptance comparisons under the existing 32-test family. Component-specific pairs and A1-vs-A2 are predeclared secondary comparisons; report all of them and do not select the one with the largest sample or most favorable result.
- For validation-only strongest-A0 selection, compare all three A0 candidates on one pre-inference common validation set available to all three. Freeze the selected baseline before test/OOS. For test/OOS selected-A0 pairs, unselected A0 candidates do not constrain the set.
- A separately labeled three-way intersection (`selected A0 + A1 + A2`) may be reported as a sensitivity analysis only. It cannot replace pair-specific primary sets.

An A0 with no matured prior is structurally unavailable for that A0 pair before inference. It remains in `U`, is marked `A0_UNAVAILABLE_NO_MATURED_PRIOR`, and is excluded only from the corresponding pair-specific set. A1/A2 remain available on their own valid inputs; their availability is not rewritten. The row stays eligible for A1-vs-A2. This is deterministic and independent of the predictions.

### 5.3 Pre-inference ledger fields

The immutable row ledger contains: protocol/manifest/data hashes; schema/canonicalization version; source row ID; instrument; exact contract/session; exchange timestamp; root/head/horizon/WF window; partition; sequence and feature/target interval metadata (not target class); structural eligibility and reason; each A0 prerequisite status/reason; A1/A2 input-availability status and input-contract hash; pair-group IDs; pair eligibility by group; reason code; and per-row/partition/group hashes. It must not contain predictions, probabilities, confidence, calibration output, abstention output, correctness, loss, or P&L. Downstream states are separate append-only records.

For a fixed dataset snapshot, protocol and implementation commit, rebuilding this ledger must yield byte-identical canonical rows and hashes without instantiating A0/A1/A2 or running inference, calibration, or metrics. A future engineering test must verify this in an inference-disabled environment; no such test is implemented in this proposal.

## 6. Causality, split boundaries, and instrument/session behavior

- Every feature at decision time `T` uses only source data timestamped no later than `T`. Target labels may look forward only for scoring after the event; an A0 prior may use a target label only when its entire target interval ended no later than `T`.
- Preserve exact listed contracts; no continuous-contract stitching. Reset persistence and transition state at each exact contract and session boundary. Missing cadence/invalid target reference breaks transition adjacency.
- ES/NQ cross-market features require exact session and timestamp alignment; never forward-fill one market into another. Reject unmatched or ambiguous alignment under frozen data-quality rules.
- Use the frozen 60-second cadence, sequence length 8, feature contracts, target definitions, 5/15/30-minute horizons, WFs, seeds, and dates. There is no WF2/30-minute special case.
- **V4 boundary choice:** a full model-input dependency can reach 37 minutes before an anchor (30-minute feature lookback plus seven minutes from an eight-row one-minute sequence). Require the first scored/calibration/early-stopping validation anchor after each evaluation partition boundary to be at least 37 elapsed minutes after that boundary. Purge any prior-partition training label whose full information interval reaches the next partition boundary. Apply the same rule at every WF boundary and to ES/NQ. The 37-minute figure is derived from frozen dependency geometry, not protected readiness/performance. Any change to this rule needs a new protocol version.
- Target horizons remain unchanged; the boundary rule only controls eligibility. The underlying source dataset remains unchanged; row eligibility is derived and hashed under V4.

## 7. State machine: inference, calibration, abstention, scoring

States are distinct, monotone, and recorded per row, model/seed and pair group:

1. `STRUCTURALLY_ELIGIBLE` / `STRUCTURALLY_INELIGIBLE` from `U` only.
2. `PAIR_ELIGIBLE` / `PAIR_INELIGIBLE_MODEL_UNAVAILABLE` from the frozen pre-inference pair mask only.
3. `INFERENCE_NOT_RUN` → `INFERENCE_ATTEMPTED` → `PREDICTION_AVAILABLE` or `INFERENCE_ERROR`.
4. For calibrated candidates, `CALIBRATION_NOT_APPLICABLE` (native A0 output) or `CALIBRATION_AVAILABLE` / `CALIBRATION_ERROR`.
5. `ABSTAINED_NO_MATURED_PRIOR` is the A0 pre-inference availability state. `ABSTAINED_ENTROPY` is a post-calibration, validation-threshold state for forecasts with a valid probability vector. They are not interchangeable.
6. `SCOREABLE_PRIMARY` is determined by pair eligibility plus valid required outputs. `SCOREABLE_SELECTIVE` is determined only by the frozen selective rule for secondary coverage analysis.
7. Cell dispositions: `EXPECTED`, `STRUCTURAL_BLOCKED`, `READY_FOR_INFERENCE`, `INFERENCE_ERROR`, `COMPLETED`, `COMPLETED_INCONCLUSIVE`. Every expected identity has exactly one terminal disposition. A0 unavailability alone is not a cell failure. Runtime/output/provenance faults block; they never shrink a denominator. Empty pair populations or frozen statistical-support failure are inconclusive, not dropped or promoted.

## 8. Calibration and abstention protocol

- Calibration occurs after raw probability output. Use the frozen validation-only scalar temperature procedure and grid/objective/tie behavior, with calibrator records bound to candidate, seed, root, head, horizon, partition, and exact fit-row IDs/hash/count. No OOS/test label or performance result may fit/alter calibration.
- V4 applies the same frozen temperature method separately to each candidate/seed probability stream. A0 applies it to its native probability forecasts only where a prediction exists; an A0 abstention is not imputed for calibration. A1/A2 use their available validation probability rows. Because fit-row availability can differ, disclose it; the validation fit masks are frozen before fit and cannot be selected by validation loss. Validation loss may select temperature according to the frozen grid and may select the strongest A0 only under the frozen rule.
- Calibration cannot change `U`, pre-inference pair eligibility, or primary row IDs. If a required fit artifact is missing or inconsistent, fail closed.
- Apply the frozen normalized-entropy thresholds after calibration, chosen using validation only at nominal coverage 100%, 90%, 75%, and 50%; retain full cutoff tie groups and use the frozen timestamp/instrument/contract tie ordering. No threshold is refit on test/OOS or selected by P&L.
- Entropy abstention never retroactively removes a row from the primary pair set. Primary nonselective metrics score the available calibrated probabilities on every `PAIR_ELIGIBLE` row. Separately report selective coverage/metrics at each predeclared point; for pairwise selective metrics, denominator is the predeclared intersection of the paired participants' retained IDs within that fixed primary pair set, and is explicitly labeled conditional. It cannot replace or be pooled with primary results.

## 9. Metric denominators, support, and reporting

- Primary macro-F1 and categorical log loss use exactly the same pair-specific pre-inference row IDs for both participants. For A1/A2 seed aggregation, all three frozen seeds must produce valid probabilities for every planned row; average their probabilities per observation as already specified. Missing/invalid output blocks the pair; no denominator shrinkage.
- Preserve frozen metrics, per-root/window nine-cell equal-weight primary aggregation, paired session-cluster bootstrap, multiplicity, and acceptance criteria for the two confirmatory selected-A0 comparisons. Additional comparisons are secondary and cannot create a new acceptance claim without a separately versioned multiplicity plan.
- Calibration metrics and other frozen secondary metrics use the same primary pair rows. Selective secondary metrics use the selective pair set described above and report their distinct denominators. Regression metrics are not applicable to these categorical targets. P&L/returns/Sharpe are not acceptance metrics and cannot choose protocol rules.
- Apply existing statistical support: at least 20 eligible session clusters per root/window and at least two distinct sessions containing each class per cell; otherwise label that test/cell inconclusive. This support rule changes no row identity and is never relaxed based on results.
- Report, per pair and cell: complete candidate count, `|U|`, each model's pre-inference availability/abstention count and rate, exact pair count/hash, inference/output errors, calibration fit rows/hash, entropy-accepted rows and realized coverage, exact metric denominators, class/session support, exclusions and reasons. Coverage is availability, not skill.

## 10. Reason codes, hashes, provenance, and reconciliation

Reason codes are machine-readable, versioned, mutually exclusive for primary row disposition, and reconciled to exact IDs:

- Structural: `SOURCE_ID_INVALID`, `CONTRACT_SESSION_MISMATCH`, `FEATURE_SEQUENCE_INCOMPLETE`, `FEATURE_LOOKBACK_UNAVAILABLE`, `TARGET_INTERVAL_INVALID`, `PARTITION_PURGE`, `PARTITION_EMBARGO_37M`, `CROSS_MARKET_TIMESTAMP_MISMATCH`.
- A0 availability: `A0_TRAIN_LABEL_SET_EMPTY`, `A0_UNAVAILABLE_NO_MATURED_PRIOR`, `A0_TRANSITION_TRAIN_PAIR_SET_EMPTY`, `A0_PRIOR_SCOPE_OR_DUPLICATE_INVALID`.
- Execution/artifacts: `INFERENCE_RUNTIME_ERROR`, `PREDICTION_OUTPUT_MISSING`, `PREDICTION_OUTPUT_INVALID`, `CALIBRATION_ARTIFACT_MISSING`, `CALIBRATION_PROVENANCE_MISMATCH`, `ABSTENTION_ARTIFACT_INVALID`.
- Comparison/statistics: `PAIR_SET_EMPTY`, `FROZEN_SUPPORT_INSUFFICIENT`, `MATRIX_IDENTITY_MISSING`, `MATRIX_IDENTITY_DUPLICATE`, `MATRIX_IDENTITY_UNKNOWN`.

The pre-inference ledger records full candidate source universe ID/hash, `U` ID/hash, every pair-group ID/participant/seed list, per-model availability masks and hashes, pair ID list/hash, protocol/manifest/data/code/environment hashes, schema and canonical-order version. A detached provenance record binds post-inference predictions/calibration/abstention/metrics back to that frozen ledger. Reconciliation must prove every expected identity appears once, every source row is either in `U` or has a reason, every `PAIR_ELIGIBLE` row is in the exact pair hash, every metric denominator equals that hash (or the separately predeclared selective-pair hash), and all counts match. No caller-supplied blindness flag substitutes for builder provenance.

## 11. Prohibited post-hoc changes

No row/group/participant/seed can be added or removed based on correctness, target class, confidence, probabilities, calibration effect, loss, P&L, return, Sharpe, metric, model rank, coverage result, readiness count, or which comparison has the largest sample. No output or runtime failure may shrink a primary denominator. No A0 prior may be fabricated, forward-filled, sourced across session/contract, or replaced by another baseline. No OOS result can choose baseline, threshold, cell status, metric, or protocol. All cells/pairs are reported, including inconclusive/failing ones.

## 12. Unchanged scientific surfaces

V4 does not redesign the learned models. A2 remains input shape `[8,24]` with 7,417 parameters; architecture, features, targets, horizons, seeds, training, checkpoints, and ablations stay frozen. A1 is unchanged. The new A0 probability/availability definitions and pairwise evaluation semantics are explicitly V4 changes. The dataset itself is unchanged. No implementation, manifest, or trading/execution behavior changes in this proposal.

## 13. Approval and effective protocol binding

V4 is **not adopted**. Before implementation or any protected inference, a new independent reviewer (not one of S1–S5 and not the coordinator) must review scientific completeness, causal and paired validity, denominators/abstention/calibration, selection resistance, neutrality, executability, and performance blindness. Protocol owner must approve the prospective choices. Then a new immutable manifest must bind this proposal SHA, its machine companion SHA, original v3 protocol/manifest hashes, dataset identity, code/data schemas, and all eligibility/group definitions. Clean implementation, independent engineering review, complete provenance, and separate explicit scoring authorization remain required. Approval never implies trading or Phase 6 authority.

**Stop:** no V4 adoption, implementation, tests, protected archive run, protected OOS score, Phase 5C-Z resumption, tie-break fix, or Phase 6 start in this pass.
