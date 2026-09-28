# BOT 2.0 Phase 5C-Z — A0 Abstention / Comparison-Protocol Review

**Conclusion: PROTOCOL AMBIGUITY CONFIRMED — FORMAL CLARIFICATION REQUIRED**

This is a read-only protocol analysis. It does not amend or adopt scientific rules, change implementation, authorize scoring, or approve the Z candidate.

## 1. State and scope

- Branch: `bot2-phase5c-z-review-remediation`
- HEAD: reviewed Y parent `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`
- Worktree: dirty and uncommitted from earlier Phase 5C-Z work. Partial authorization-builder files exist, remain **unreviewed, untested, and unapproved**; B and C remained stopped throughout this review. No shared-pipeline file was integrated.
- Frozen manifest was not edited. No implementation, eligibility rule, model, or test was edited in this protocol pass; this report is the only new file.
- Protected scoring counts from the latest no-score receipt `outputs/phase5cz_protected_preflight_no_score_v7.json`: inference 0; predictions 0; probabilities 0; metrics 0; P&L 0; signals/trades 0; scores 0. No protected performance or outcome distributions were inspected in this review.
- Previously observed structural ledger: 5,184 expected identities, 5,112 READY, 72 BLOCKED. The 72 are 36 ES and 36 NQ, all 30-minute WF2 paths for A0 previous-label persistence and TRAIN-transition. This known distribution was supplied as context; it was not used to choose a semantic interpretation.
- Neural freeze: A2 remains `[8,24]`, 7,417 parameters. No neural, feature, target, calibration, metric, or training setting was changed.

## 2. Independent review findings

Four logically independent read-only analyses were completed before coordinator reconciliation. Agents were instructed not to inspect protected outcomes/performance or communicate their conclusions to one another. Their findings converge:

| Review | Finding |
|---|---|
| P1 — Protocol historian | Historical authority does not decide whether an A0 abstention removes a row from common metrics, counts as an abstention outcome, or makes a whole cell incomplete. Earlier tests do not fill that gap. |
| P2 — Baseline semantics | Majority is TRAIN-only and requires no row-specific prior. Persistence requires a same-head/root/horizon prior target whose information interval has matured by decision time and explicitly abstains if none exists. Transition probabilities are TRAIN-only with Laplace α=1 but also require an eligible prior state; no fallback is authorized. Neither the manifest nor history says one such row abstention invalidates the whole cell. The lookup partition used by current code is not specified in the frozen baseline text. |
| P3 — Comparison fairness | “Identical intersection of valid observations” is the closest existing language to a common evaluable-row set, and code has a generic per-model set-intersection utility. Neither establishes that A0 abstention equals observation invalidity, nor that metrics are recomputed on that exact intersection. Conditional intersection can be fair only with a fixed, outcome-independent rule and explicit coverage reporting; the frozen text does not specify those details. |
| P4 — Adversarial methodology | Each plausible interpretation has material bias/fairness risks. A fixed denominator needs a frozen abstention scoring rule; removing abstentions creates a conditional estimand whose population depends on availability; whole-cell exclusion may overstate model-specific ineligibility. No interpretation is justified solely by the current manifest. |

## 3. Historical authority and semantics

### A0 definitions and causal information

The first explicit frozen A0 definitions are in `config/bot2_phase5c_experiment_manifest_v1.json`, introduced at commit `6a79f53e653944620fe582be33caccdd370269f9`:

- **A0_TRAIN_MAJORITY:** TRAIN-only per root/head/horizon majority with lexical tie-break. It requires no row-specific prior label.
- **A0_PREVIOUS_LABEL_PERSISTENCE:** carry the latest prior label whose *full information interval* ends no later than decision time `T`; otherwise abstain.
- **A0_TRAIN_TRANSITION_MATRIX:** TRAIN-only first-order transitions with Laplace α=1, conditioned on the latest eligible past target. The prior state must be causally available by `T`; the frozen wording supplies no alternative/default state when it is absent.

The same semantics are in the frozen v2 manifest, commit `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94`, and are restated in v3, commit `9a1ecfaf08077252049dd187d44f8641da1186aa`. The Phase 5B target-remediation record defines the target information interval; the v3 session/contract policy prohibits bridging sessions or contracts. No future-overlapping label, forward fill, synthetic label, cross-session prior, or majority fallback for the prior-dependent A0 paths is authorized.

The manifest does **not** name a separate partition from which the prior must be retrieved. The current implementation looks within `VALIDATION_AND_CALIBRATION`, matching contract/session and requiring timestamp `< T` and `label_end <= T`; this is implementation behavior, not an explicit frozen partition rule. The whole-run exception `A0_PRIOR_LABEL_INELIGIBLE` is likewise not an authoritative cell-terminal-state definition.

**Separate implementation-consistency observation (not resolved or changed here):** the frozen majority rule specifies a lexical tie-break, while the reviewed implementation uses class-index `argmax`. In the volatility class order `LOW, NORMAL, HIGH`, class-index order is not lexical order. This appears to be a potential mismatch requiring a separate no-score protocol/implementation review; this pass did not test or modify it and did not inspect outcomes.

### Identical evaluation intersection

The frozen v2 protocol, `docs/BOT2_PHASE5C_V2_PROTOCOL.md`, says the primary comparison uses the identical intersection of valid observations for each candidate/seed within root/head/horizon/window and reports exclusions and reasons. The v2 and v3 machine manifests encode `purge_embargo.identical_evaluation_intersection: true`. The v3 protocol repeats the requirement without a complete row-construction rule.

The v2 draft includes a stronger phrase about freezing one identical eligible OOS observation set, but that draft is explicitly not the frozen authority. The v2 supersession record says v2 was superseded before evaluation; v3 uses a new identity. Phase 3 and Phase 5A/B materials do not define A0 abstention denominators. The generic matrix test for row intersection and the prior-label input test do not test how abstention changes evaluation rows, denominators, or cell completeness.

**Established:** causal availability of prior labels; persistence abstains if unavailable; TRAIN-only origin of majority and transition probabilities; an identical valid-observation comparison requirement.  
**Not established:** whether a missing A0 prior is a model-specific abstention, an exclusion from all models’ common rows, a fixed-denominator scored abstention, or a cell-level terminal failure; whether and how denominators/coverage/completeness change; how the common intersection is applied during calibration and metrics.

## 4. Coordinator decision table

| Option | Historical support | Causal validity | Fairness / leakage implications | Post-hoc-selection risk | Identical-intersection compatibility | Changes frozen semantics? |
|---|---|---|---|---|---|---|
| **1. Entire cell structurally ineligible** | No explicit rule says one or more A0 prior abstentions invalidates the whole cell. A0 input failure is not automatically model-neutral row invalidity. | Safe only if the cell truly has no lawful evaluable rows under a predeclared, model-neutral rule; that is not established here. | May conceal A0 coverage failure and suppress otherwise valid A1/A2 rows. Can favor a baseline or neural method depending on the chosen cell policy. | High if chosen after seeing where it occurs or to simplify completion. | Could omit a cell from paired comparisons, but no frozen terminal status or group-completeness rule authorizes that. | **Yes / unresolved** unless exact prior authority is found. |
| **2. Remove unavailable A0 rows from the common intersection for every model** | The “identical intersection of valid observations” wording is partial support; it does not define A0 abstention as invalidity or specify construction. | Can be causal if row availability is determined only by information available at `T`, never future outcomes. | Gives identical denominators but produces conditional metrics on rows where every required model can predict. Without separate coverage/abstention reporting it can hide cold-start or boundary cases and favor high-availability subsets. | Material if the inclusion rule is selected after inspecting protected structure; must be disclosed and outcome-blind. | Plausibly compatible, but the exact intersection and calibration/metric use are not frozen. | **Yes / clarification needed.** |
| **3. Retain abstention as an outcome under a fixed full denominator** | “Otherwise abstain” supports an explicit abstention state, but no metric treatment is specified. | Causal if abstention is emitted from information available by `T`. | Preserves full eligible-row coverage, but accuracy/log loss require a frozen penalty, abstention class, or coverage/utility metric; inventing one now changes metrics. | Low only if a scoring rule was frozen in advance; otherwise high. | A fixed denominator is compatible only after the protocol says how an abstention enters each metric. | **Yes / amendment required.** |
| **4. Other historically supported rule** | V2 supports a common valid-row intersection and exclusions/reasons; it does not resolve whether A0 abstention makes a row invalid, counts as an outcome, or invalidates a cell. No other binding alternative was found. | Depends on the rule. | Same risks apply; no hidden fallback is permitted. | Same concern if selected post hoc. | The general intersection requirement remains binding, but its abstention semantics are open. | No complete rule to apply. |

**Coordinator reconciliation:** historical intent establishes the common-intersection principle but not its interaction with model-specific abstention. Options 2 and 3 remain scientifically plausible; option 1 is not supported as an automatic consequence of row abstention. This review cannot select among them without a protocol owner’s prospective decision. **Historical authority does not resolve the ambiguity.**

## 5. Bias and safety analysis

- **Post-hoc selection / survivorship:** after archive structure reveals where abstentions arise, defining cell/row treatment can alter the evaluated population. Choosing by ready-cell count, coverage, or convenience would be invalid. No metric or outcome may inform the clarification.
- **Baseline favoritism:** dropping rows because a prior-dependent A0 cannot predict can condition the comparison on A0 availability and hide its abstention rate. Substituting majority, a synthetic prior, or a later label is not authorized.
- **Neural-model favoritism:** scoring A1/A2 on more rows than A0 would create unequal denominators; forcing neural rows onto an A0-restricted subset without coverage reporting can also change the estimand. All models/seeds must use the same explicitly frozen comparison rows for each reported paired metric.
- **Leakage:** the A0 prior must have a full information interval ending by `T`, and remain within the same permitted root/head/horizon, session, and contract. OOS target values may not determine row eligibility or comparison-set membership.
- **Metric denominators:** “identical” requires the exact common row identities and denominator to be auditable. Existing language does not state whether abstentions are excluded, penalized, or make a cell/group incomplete.

## 6. Non-executable protocol clarification proposal — NOT ADOPTED

This is a review draft only. It does not change the manifest, authorize scoring, or establish a scientific rule. Protocol owner / independent review is required before any adoption.

**Original ambiguous language:**

1. A0 persistence carries the latest target whose information interval ends no later than `T`; otherwise abstain.
2. The primary comparison uses the identical intersection of valid observations for every candidate/seed in each root/head/horizon/window; excluded counts and reasons are reported.

The protocol does not define whether an A0 abstention makes that row invalid for all methods, remains in a fixed denominator as an abstention, or makes a cell incomplete.

**Candidate explicit rule for owner review (conditional-intersection interpretation):**

1. Before any predictions or outcome metrics, define the target/data-eligible decision-row universe `U` solely by the frozen feature, target, session/contract, timestamp, partition, purge, and embargo contracts. No future target value, prediction, score, or metric may determine membership.
2. For each frozen comparison group (root/head/horizon/WF), define each model/seed's prediction-eligible set from only its frozen inputs and information available at `T`. Prior-dependent A0 emits an explicit abstention with a reason when no matured same-scope prior is available; no fallback or imputation is allowed.
3. Define the paired primary-metric rows as the exact intersection of `U` with prediction-eligible rows for every required candidate/seed in that group. If an A0 abstains, omit that row from the metric denominator for **all** models/seeds in that paired group; never omit it only for A0. Recompute every paired metric on those exact row identities.
4. Preserve and report the full `U` count, common-intersection count, per-model/seed coverage, every abstention/exclusion count and reason, and exact paired row identity hash. Conditional paired metrics must be explicitly labeled as conditional on the common intersection. No coverage threshold is proposed here; any acceptance threshold or behavior for empty/insufficient intersections must be decided and frozen separately before evaluation.
5. An A0 abstention does not by itself erase a frozen matrix identity. Cell/group terminal states for empty or insufficient common rows must be explicitly defined using a pre-existing support rule where available; any new status or comparison-completeness rule requires prospective owner approval. No identity may be silently omitted.

**Rationale:** this rule is outcome-blind and preserves causal prior availability while keeping denominators identical across the compared models. Separate coverage reporting prevents the conditional metric from being presented as full-population performance. However, it is a post-freeze clarification and could change the evaluation estimand; the frozen text alone does not authorize it.

**Impacts if this candidate were later approved:**

- A0: persistence and transition abstain on rows lacking a matured permitted prior; majority remains its TRAIN-only baseline. No fallback is added.
- A1/A2: model definitions, inputs, training, and predictions are unchanged; paired metrics use the same explicit common rows as A0 and all seeds.
- Common-row intersection: becomes explicitly the intersection of data/target-eligible rows and all required prediction-eligible model/seed rows per comparison group.
- Metric denominators: exact common-row count; report target-eligible universe count and coverage/exclusions alongside conditional metrics. No penalty/probability is invented for an abstention.
- Cell terminal states: identities stay present; no silent dropping. The treatment of empty/insufficient groups must be explicitly frozen before execution.
- 5,184 experiment identities: unchanged; only eligibility/intersection/completeness semantics would be clarified. A separate protocol version/manifest identity and hash would be required if adopted.
- A2 architecture, features, targets, training settings, calibration, abstention policy, metrics, ablations: no change proposed. (The comparison-row rule would still need to specify its interaction with the existing calibration subset before adoption.)
- Protected information: the need for the clarification was surfaced by a structural preflight, but this proposal was not selected to improve readiness or results. No protected predictions, scores, metrics, P&L, or performance comparisons informed it. No OOS target values or outcomes were inspected for this review.

> The need for this clarification was discovered during protected structural preflight after observing that some frozen experiment cells encounter A0 prior-label ineligibility. No protected model predictions, scores, metrics, P&L, or performance comparisons were inspected.

## 7. Final disposition

- Historical authority resolves A0's causal prior-label rule and requires a shared valid-observation intersection, but leaves abstention's row/cell/denominator treatment unresolved.
- The 72-cell issue remains unclassified as a data defect or eligible-cell status; no scientific status is invented.
- Partial B authorization files remain untouched, unreviewed, and untested. B/C remain stopped. No implementation tests were run in this pass.
- No manifest, code, test, model, eligibility rule, external anchor, or commit was changed. No protected performance was inspected; no real authorization was created; no protected OOS was run; trading authority remains `NONE`.

**Final conclusion: PROTOCOL AMBIGUITY CONFIRMED — FORMAL CLARIFICATION REQUIRED.** Stop Phase 5C-Z implementation until an authorized protocol owner resolves this question prospectively and the clarification is separately versioned and independently reviewed.
