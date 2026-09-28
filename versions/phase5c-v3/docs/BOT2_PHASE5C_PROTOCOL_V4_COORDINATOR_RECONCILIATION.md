# BOT 2.0 Phase 5C — V4 Prospective Protocol Coordinator Reconciliation

**Conclusion: NEW PROTOCOL PROPOSAL READY FOR INDEPENDENT REVIEW.**  
**Status:** V4 and its machine-readable companion are proposals only—not adopted, executable, or authorized for inference/scoring. Phase 5C-Z remains paused; B/C remain stopped.

## 1. Identity, repository, and integrity

1. **Original protocol disposition:** `NON_EXECUTABLE_AS_WRITTEN_DUE_TO_PROTOCOL_AMBIGUITY`; this is not a finding that the historical experiment failed.
2. **Original protocol hash:** `docs/BOT2_PHASE5C_V3_PROTOCOL.md`, raw SHA-256 `23905DBD4215669477645313B931243A644E83755577C4ABF7AC57A0ADC62667`.
3. **Original manifest hash:** canonical SHA-256 `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`; exact v3 manifest-file SHA-256 `FB12989A0E4062EA63B0A335D62B718BA02AD3082C42E63372CABC2F035A1FA5`.
4. **Branch / HEAD:** `bot2-phase5c-z-review-remediation` / `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`.
5. **Worktree:** pre-existing dirty source/tests and untracked Phase 5C-Z work remain. This pass added only V4 proposal documents and digest sidecars; no implementation or frozen artifact was modified.
6. **V4 proposal:** `docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md`; 23,182 bytes; SHA-256 `3F697EE8FB2E802A9E9F0332F27504D6D8CDAA9220C32745D930BB34FA598630`; verified against detached sidecar `docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md.sha256`.
7. **Machine-readable companion:** `config/bot2_phase5c_v4_protocol_proposal.json`; 9,175 bytes; SHA-256 `32345143AF5BC9E4021FBBD18AA39EA064ACA33DB040873B073F9F2AD79D75B0`; JSON syntax parsed; verified against `config/bot2_phase5c_v4_protocol_proposal.json.sha256`. It declares `executable:false`, scoring/OOS authorization false, and trading authority `NONE`.
8. **Original files preserved:** yes. V1 clarification and its verified hash are also preserved; V4 is a distinct proposed protocol identity. V3 was not rewritten.

## 2. Design-board conclusions

| Agent | Independent conclusion |
|---|---|
| **S1 — Baseline methodology** | The V3 authority defines TRAIN-majority/lexical tie, persistence/latest matured label/otherwise abstain, and TRAIN-only Laplace-1 transition probabilities with a mature prior. It does not settle prior source partition, transition no-prior behavior, A0 forecast probabilities for log loss, or abstention denominators. Those require explicit V4 choices, not claims about V3. |
| **S2 — Paired-comparison statistics** | Use predeclared pair-specific row sets: A1/A2 vs selected A0, component A0 contrasts, and A1 vs A2. A missing A0 prior may affect only its own pair, not A1-vs-A2. Preserve identical IDs within each reported pair, coverage and conditional labels. Component contrasts should not be chosen by sample size or result. |
| **S3 — Calibration/abstention** | Calibration is validation-only, temperature scaling; entropy thresholds are validation-only and applied after probabilities. Frozen authority does not fully define per-model/seed fit rows, A0 calibration, or how abstentions affect scoring. Keep primary pair membership fixed before inference and define selective coverage separately. |
| **S4 — Causal/temporal integrity** | Features/targets are causal and no WF2 exception is justified. A0 reset/transition-edge boundaries need explicit new rules. The sequence plus rolling feature can reach 37 minutes into raw history; the frozen 30-minute embargo does not explicitly cover all early-stopping/calibration rows. V4 proposes a uniform 37-minute guard. |
| **S5 — Adversarial design** | V3's boolean identical-intersection requirement is insufficient to prevent post-result row manipulation. Need explicit U, pair masks, reason reconciliation, denominator hashes, and fail-closed output behavior. Frozen authority leaves A0 source/probability/no-prior behavior and calibration/group rules open. |

The board did not claim these rules were already frozen. The coordinator selected explicit, conservative options for a new protocol only; disagreements and bias/causal/statistical consequences are stated in V4. The old V3 remains historical evidence and is not retroactively repaired.

## 3. Coordinator decision record

These are new V4 choices made without consulting protected performance. A later independent reviewer may reject them; none is operative now.

| Scientific decision / options considered | Chosen V4 rule | Methodological rationale | Bias and causal/statistical implications |
|---|---|---|---|
| **A0 missing prior:** (A) abstain; (B) drop cell; (C) majority/marginal fallback; (D) common-row exclusion. | A0 persists/transitions abstain with explicit reason; pair-specific pre-inference availability omits that row only from comparisons containing that A0; preserve it in U and coverage. No cell deletion or fallback. | Avoids fabricated information and baseline substitution; makes coverage visible. | A0 pair metrics are conditional on A0 availability and cannot be described as full-universe performance. Other pairs retain their own fixed population. |
| **Prior stream:** TRAIN-only vs all matured causal history vs session reset. | V4 uses all strictly prior, fully matured labels available by T within exact instrument/contract/session/root/head/horizon/target version; reset at session/contract. Prior OOS labels become usable only after their interval ends. Transition counts remain TRAIN-only. | Matches a realistic streaming persistence baseline while enforcing time causality; explicit V4 choice, not V3 authority. | Gives no future/cross-session leakage; may create availability-conditioned populations. Review must specifically approve this new baseline definition. |
| **Transition no-prior and edges:** marginal fallback, synthetic state, abstention; edge construction unspecified. | Abstain without prior; train transitions only on valid consecutive one-minute same-scope TRAIN labels, no gaps/boundary crossing, Laplace α=1. | Preserves conditional transition identity and avoids opportunistic fallback. | Startup rows become unavailable for that pair; coverage reported; no row is relabeled as globally invalid. |
| **Majority probability for log loss:** one-hot vs TRAIN frequency distribution. | Add-one-smoothed TRAIN class frequencies `(n_c+1)/(N+K)` as forecast distribution; hard class is count-majority, tied classes lexical. | Defines a proper categorical forecast without using evaluation labels; avoids zero TRAIN class mass. | Smoothing is a new V4 baseline detail, so A0 is explicitly versioned; probabilities still derive only from TRAIN. |
| **Comparison groups:** one all-model intersection vs pair-specific vs only strongest A0. | Confirmatory A1/A2 vs validation-selected strongest A0 preserved; secondary A2-vs-each-A0 and A1-vs-A2 all fixed; optional three-way sets are sensitivity-only. | Keeps original confirmatory family while exposing component behavior without cherry-picking. | Every pair has its own pre-inference hash/denominator; coverage/population differs across pairs, disclosed. Secondary results do not create post-hoc acceptance claims. |
| **Calibration:** A0 only, neural-only, or same method for every forecast. | Apply frozen scalar temperature procedure to each candidate's native probabilities where available; fit rows/hashes are validation-only; no calibration can change eligibility. | Symmetric predeclared transform and complete A0/A1/A2 comparison pipeline. | Model-specific fit coverage is reported; no OOS fit. Independent reviewer must verify this choice does not create unintended A0 tuning. |
| **Abstention denominator:** remove from primary, score as error, or separate selective analysis. | Primary nonselective metrics use all fixed pair-eligible rows with valid probabilities; entropy abstention is a distinct secondary coverage analysis with predeclared pairwise retained-set rule. A0 no-prior availability is pre-inference and affects only the relevant pair set. | Does not conflate availability with confidence-based rejection; no invented penalty. | Selective results have their own conditional denominator and may not replace the primary result. |
| **Partition dependency guard:** keep 30m vs account for full model input. | Uniform 37m embargo from feature lookback 30m + sequence offset 7m; purge uses full target information interval. | Prevents cross-boundary raw input dependence under an eight-row sequence. | Conservative uniform row exclusion across roots, symbols, horizons, and WF windows; not selected from protected counts. |

## 4. Requested protocol decisions

9. **A0 majority:** TRAIN-only per root/head/horizon; Laplace-one class-frequency probabilities; max-count class; lexical label tie-break; no eligible TRAIN labels => structural block.
10. **A0 persistence:** latest fully matured label strictly before T in same exact instrument/contract/session/root/head/horizon/target version; one-hot output; no prior => pre-inference unavailable/abstain; no fallback.
11. **A0 transition:** TRAIN-only adjacent valid one-minute same-scope transition pairs, Laplace α=1; conditioning state is latest mature permitted prior; no prior => pre-inference unavailable/abstain; no marginal/majority/synthetic fallback.
12. **Missing prior:** preserve row in U, report A0 unavailability; exclude only from that A0's pair set, before inference. A1/A2 availability and A1-vs-A2 pair remain independent.
13. **Tie-break:** lexical frozen class label for A0 majority. The known code defect `np.argmax` lowest-index remains separate and unfixed; the proposed future protocol specifies expected behavior but does not claim code conforms.
14. **Structural eligibility:** manifest-bound source/schema/instrument/contract/session/time, feature/target interval metadata, sequence integrity, fixed partition, purge, embargo; never target class/value or performance.
15. **Pre-inference universe:** canonical `U`, source rows fully reconciled to `U` or one deterministic exclusion reason, hashed before any inference.
16. **Pair eligibility:** deterministic `U` intersected with frozen input/prerequisite availability for exact predeclared participant/seed set; the only output is row membership/reasons, not predictions.
17. **Common comparison:** pair-specific exact ID set; same IDs for all model metrics within a pair; no single global intersection chosen by sample size. Three-way intersection is sensitivity-only.
18. **Calibration ordering:** inference probabilities → validation-only temperature scaling → frozen entropy threshold → scoring/reporting.
19. **Calibration partition:** validation/calibration partition only, original grid/objective retained, fit-row identities/hash/count bound; no test/OOS fitting.
20. **Abstention ordering:** after calibration; entropy abstention does not alter primary pair membership. A0 missing-prior unavailability is separate and pre-inference.
21. **Abstention denominator:** primary metrics score available probabilities on fixed pair rows; selective metrics use predeclared accepted-row pair intersection and are distinctly labeled/secondary; no penalty is invented.
22. **Metrics:** primary macro-F1/log loss, frozen aggregation/bootstrap/support/multiplicity retained for the existing confirmatory selected-A0 family; each comparison uses the exact same pair IDs for both sides. Secondary pairs are descriptive, not acceptance claims.
23. **Coverage reporting:** expected candidates, U, pair IDs/count/coverage, per-model/seed availability and A0 abstentions, entropy-retained rows, reasons, fit rows, exact denominators, and support; coverage is not performance.
24. **Pairwise comparisons:** A1 vs selected strongest A0 and A2 vs selected strongest A0 confirmatory; A2 vs each A0 variant and A1 vs A2 predeclared secondary; optional three-way intersection sensitivity. All reported; no sample/result-based choice.
25. **Cell states:** `EXPECTED`, `STRUCTURAL_BLOCKED`, `READY_FOR_INFERENCE`, `INFERENCE_ERROR`, `COMPLETED`, `COMPLETED_INCONCLUSIVE`; exactly one terminal disposition per expected identity. A0 unavailability is not a cell error; runtime/provenance errors block; empty/unsupported sets are inconclusive.
26. **Row-set hashing:** canonical source row ID serialization, schema/version, universe hash, and per-exclusion reason ledger hash.
27. **Comparison-set hashing:** protocol/manifest/data/code hashes + group axes/participants/seeds + U hash + availability-mask hashes + exact pair ID hash; post-run artifacts bind back to this receipt.
28. **Post-hoc protection:** all groups and masks frozen before inference; failures do not shrink denominators; full matrix reconciled; no outputs, outcomes, calibration results, P&L, or rankings may alter membership.
29. **Causal integrity:** T-only features, mature prior labels only, exact session/contract resets, no future/forward fill, exact ES/NQ alignment, 37-minute input-dependency embargo, target interval purge; generic all WF/horizon rule.
30. **A0 favoritism:** pairwise conditional availability may hide cold starts; mitigate by reporting coverage versus U and all fixed comparisons, never characterize as full-U performance.
31. **A1 favoritism:** fixed A1-vs-A2 and A1-vs-A0 IDs/denominators; no selection based on its outputs; all seeds required.
32. **A2 favoritism:** no confidence/correctness filtering in primary set; selective outputs are secondary under fixed thresholds and separate denominators; no A2-specific row rules.
33. **A2 shape:** `[8,24]`.
34. **A2 parameters:** `7,417`.

## 5. Protected boundary and review incident

35. **Protected archive rerun count:** 0.
36. **Protected inference count:** 0 per existing no-score receipt.
37. **Protected predictions:** 0 per existing no-score receipt.
38. **Protected metrics:** 0 per existing no-score receipt.
39. **Protected P&L:** 0 per existing no-score receipt.
40. **Protected scores:** 0 per existing no-score receipt.

These counters were not generated by this pass; the protected archive was not rerun. **Review-integrity note:** an initial S4 attempt accidentally used a broad search that surfaced a serialized artifact under `outputs/`. That reviewer was immediately interrupted and excluded; the artifact contents were not analyzed by the coordinator. A replacement S4 reviewer was restricted to named frozen protocol/configuration documents only. The accidental attempt's findings are not used. This is disclosed rather than claiming no artifact was ever surfaced to an agent.

## 6. Proposed artifacts and stop condition

41. **V4 proposal path:** `docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md`.
42. **V4 proposal SHA-256:** `3F697EE8FB2E802A9E9F0332F27504D6D8CDAA9220C32745D930BB34FA598630` (detached digest verified).
43. **Machine companion path:** `config/bot2_phase5c_v4_protocol_proposal.json`.
44. **Companion SHA-256:** `32345143AF5BC9E4021FBBD18AA39EA064ACA33DB040873B073F9F2AD79D75B0` (detached digest verified; JSON parses; `executable=false`).
45. **Original artifacts preserved:** yes; V3 protocol/manifest hashes unchanged, V1 remains preserved. Dataset contents were not changed.
46. **Implementation unchanged:** yes. No code/tests/manifest writes, no tie-break fix, no inference/scoring.
47. **Remaining blockers:** independent scientific review by a person/agent not among S1–S5 or the coordinator; protocol-owner approval of the explicitly new A0 source/probability/transition rules; independent validation of 37-minute boundary treatment; then a separately versioned manifest binding originals + V4 hashes; clean implementation and engineering review; separate scoring authorization. No scoring/trading authority exists.
48. **Final conclusion: NEW PROTOCOL PROPOSAL READY FOR INDEPENDENT REVIEW.** Stop here. Do not adopt V4, implement, resume B/C, fix the tie-break, run protected OOS/archive, seal Z, or start Phase 6.
