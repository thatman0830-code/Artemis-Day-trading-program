# BOT 2.0 Phase 5C-Z — Protocol Clarification Coordinator Review

**Final conclusion: CLARIFICATION PROPOSAL READY FOR INDEPENDENT REVIEW**  
**Adoption/execution: NOT AUTHORIZED.** B/C remain stopped. Do not run protected OOS, inspect protected performance, seal Z, or start Phase 6.

## 1. Repository and worktree state

- Branch: `bot2-phase5c-z-review-remediation`
- HEAD: `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`
- The worktree was already dirty before this clarification pass. Existing source/test modifications and partial authorization-builder files remain unreviewed/unapproved; they were not changed by this pass. New files from this pass are the proposed clarification, this report, the detached clarification digest, and the separate A0 tie-break remediation specification.
- No code, tests, model, frozen protocol, manifest, eligibility artifact, or external anchor was modified in this pass. No tests or protected archive/preflight were run.

## 2. Independent Q1–Q4 findings

| Review | Conclusion |
|---|---|
| **Q1 — Abstention semantics design** | A0 causal abstention is row-level model availability, not data-row invalidity and not automatically a cell failure. Distinguish `U` (frozen model-neutral target/data eligible rows), pre-inference causal availability masks, common paired comparison rows, cell execution/completion, and metric denominators. Use the common prediction-availability intersection for paired metrics; retain abstention on `U`. Frozen minimum statistical support is the existing 20 eligible session clusters per root/window and two distinct sessions per class per cell; no raw row-count or coverage threshold is frozen. |
| **Q2 — Tie-break forensics** | `IMPLEMENTATION_DEFECT`. Earliest frozen A0 majority rule requires lexical tie-break; implementation uses `np.argmax(counts)`, i.e. minimum class index. Synthetic volatility counts `LOW=1, NORMAL=0, HIGH=1` yield frozen `HIGH`, implementation `LOW`. Requirement predates implementation. No protected tie frequency was inspected. A separate defect-only remediation specification is provided. |
| **Q3 — Statistical comparison review** | Exact common intersection supports a conditional paired comparison with equal denominators, but does not estimate full-`U` performance. Availability-based exclusions can alter the population. Publish per-model coverage/abstentions, `U`, common count, hashes, reasons, support and denominators. No new raw-row/coverage floor is justified; use existing session/class support and label insufficient groups inconclusive. |
| **Q4 — Protocol red team** | Draft must bind explicit `U`, group, masks and hashes before inference; never derive `U` from the union of model rows; reject duplicate/unknown/noncanonical IDs; reconcile per-row reasons; fail closed on model output/runtime errors rather than shrinking denominators; recompute metrics on the exact common IDs; separate entropy abstention; freeze A0 validation-selection participants; and bind calibration/threshold/provenance. Current helper/test behavior does not prove these guards. |

The four reviews used protocol/source/history only. They did not inspect protected predictions, probabilities, metrics, P&L, outcomes, or tie frequencies and did not rerun the protected archive.

## 3. Proposed semantics

- **A0 abstention:** persistence abstains when no fully matured prior label exists at `T`; transition A0 likewise abstains if no lawful prior state exists. No forward fill, fabricated prior, fallback baseline, future label, or cross-session/contract lookup. Majority remains TRAIN-only and uses the frozen lexical rule.
- **Row and comparison eligibility:** freeze model-neutral `U` from source/data/target-interval metadata and split/purge/embargo rules without using realized target classes or model results. Separately precompute each participant/seed's causal availability mask from frozen inputs and decision-time state. For each predeclared comparison group, define `C(G) = U ∩ ⋂ P(model, seed)`. Bind/hash exact participants, U, masks, and common IDs before inference. A0-abstention rows remain in U and coverage reports; if unavailable for one participant they are omitted symmetrically from that group's paired metrics, not from the underlying dataset or unrelated comparisons.
- **A0 selection:** validation selection compares all frozen A0 candidates on their shared predeclared validation intersection. After the selected baseline is frozen, test/OOS comparisons use only the selected A0 and the specified A1/A2 participants; unselected A0 candidates cannot reduce that test/OOS denominator.
- **Cell-state proposal:** preserve every matrix identity. Legitimate row abstentions may end in `EXECUTED_WITH_ABSTENTIONS`; infrastructure/output/provenance failures are `BLOCKED_ERROR`; empty or below-frozen-support common groups remain `COMPLETED_INCONCLUSIVE`, not silently deleted or promoted. No scoring can occur until separate existing gates authorize it.
- **Denominators:** every paired metric uses exactly the hashed common comparison IDs and reports that denominator. All required seeds must have valid output for every planned available row; missing/invalid output blocks rather than shrinking the set. For paired selective metrics, apply already-frozen validation entropy thresholds inside C and use the exact intersection of retained IDs; report each model's realized coverage and the conditional selective denominator separately.
- **Coverage:** report source count, `|U|`, per-model/seed coverage and abstention reasons, common count/coverage, exclusion/failure counts and row hashes, class/session support, and each metric's denominator. These are diagnostics, not performance or ranking.
- **Minimum support:** no numeric common-row or coverage minimum is invented. Apply existing frozen support: at least 20 eligible session clusters per root/window and at least two sessions containing each class in every cell; otherwise inconclusive.

The proposal fixes a prospective conditional estimand and explicitly discloses its availability selection. It preserves original protocol and manifest bytes. It does **not** make the proposed rule effective or resolve any current implementation blocker.

## 4. Tie-break finding and separate remediation

- Frozen requirement: per root/head/horizon TRAIN-only class majority, lexical tie-break (first present in v1 manifest commit `6a79f53e653944620fe582be33caccdd370269f9`, repeated in v2/v3 and Phase 5B).
- Current implementation: lowest class index on tied maximum counts (`np.argmax` in `_a0_predictions`). Frozen probability-decoding lowest-index argmax is a different rule and does not supersede the majority tie-break.
- Frozen class order: direction `DOWN=0, FLAT=1, UP=2`; volatility `LOW=0, NORMAL=1, HIGH=2`; structure `RANGE=0, TRANSITION=1, TREND=2`.
- Synthetic reproducer: `LOW=1, NORMAL=0, HIGH=1`; lexical result `HIGH`, current index result `LOW`.
- Separate proposed remediation: [BOT2_PHASE5C_Z_A0_TIE_BREAK_REMEDIATION_SPEC_V1.md](BOT2_PHASE5C_Z_A0_TIE_BREAK_REMEDIATION_SPEC_V1.md). No code fix or test was run.

## 5. Version hashes and effective identity

- Original frozen protocol ID: `BOT2-PHASE5C-V3`.
- Original frozen protocol Markdown raw SHA-256: `23905DBD4215669477645313B931243A644E83755577C4ABF7AC57A0ADC62667`.
- Original manifest's canonical SHA-256 (as declared by the frozen protocol): `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- Original v3 manifest exact file SHA-256: `FB12989A0E4062EA63B0A335D62B718BA02AD3082C42E63372CABC2F035A1FA5`.
- Proposed clarification ID: `BOT2-PHASE5C-V3+Z-CLARIFICATION-V1-PROPOSED`.
- Proposed clarification exact-byte SHA-256: `EB9E08338C20EAD395E0915078CAEB80BDD600FD39F4791F8BFB3FD640296B4F` (detached digest: `BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1.md.sha256`).
- If approved later, effective ID: `BOT2-PHASE5C-V3+Z-CLARIFICATION-V1`; it must bind both original protocol/manifest and exact approved clarification hash. It is **not effective now**.

## 6. Protected counters and guardrails

The latest existing no-score receipt, as documented in the prior review, reports:

| Counter | Value |
|---|---:|
| Protected inference | 0 |
| Protected prediction | 0 |
| Protected probability | 0 |
| Protected metric | 0 |
| Protected P&L | 0 |
| Protected score | 0 |

This pass did not reopen the receipt, rerun the archive/preflight, or inspect protected performance. A2 remains frozen at input shape `[8,24]` and 7,417 parameters. No features, targets, horizons, seeds, training, calibration, abstention thresholds, metrics, ablations, model behavior, broker behavior, or trading authority were changed.

## 7. Remaining blockers and disposition

1. A new independent reviewer must review the exact proposal and detached hash for performance blindness, causality, paired fairness, post-hoc selection, model-family neutrality, and implementable precision. This coordinator pass is not that review.
2. Existing code does not yet prove pre-inference immutable U/masks, exact common-row metric recomputation, per-row reason reconciliation, threshold recomputation, or terminal-state behavior. No implementation work was authorized here.
3. The tie-break is a separate implementation defect; its proposed patch requires a separate defect-only authorization and review.
4. Original frozen files remain immutable. Proposal adoption requires prospective owner approval, a newly versioned manifest/protocol binding both original and clarification hashes, independent implementation review, and all pre-existing scoring/authorization gates.

**Confirmation:** no protected archive rerun; no protected predictions/scores/metrics/P&L inspected; no implementation modified; no tests run; A2 unchanged; no scoring or trading authority granted.

**Final conclusion: CLARIFICATION PROPOSAL READY FOR INDEPENDENT REVIEW. STOP HERE.** Do not adopt it, resume B/C, seal Z, run protected OOS, or start Phase 6 in this pass.
