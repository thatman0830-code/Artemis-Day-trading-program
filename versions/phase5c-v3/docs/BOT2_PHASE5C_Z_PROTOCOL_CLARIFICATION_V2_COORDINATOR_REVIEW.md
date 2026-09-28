# BOT 2.0 Phase 5C-Z — V2 Blocker Remediation Coordinator Review

**Final conclusion: BLOCKERS REMAIN — V2 NOT YET DEFENSIBLE.**  
**Action:** no V2 clarification was drafted because independent reviews did not support a defensible solution under the frozen A0 contract. V1 remains preserved and not adopted. Phase 5C-Z remains paused; B/C remain stopped.

## Repository and artifact identity

1. **Branch:** `bot2-phase5c-z-review-remediation`.
2. **HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`.
3. **Worktree status:** dirty before this pass. Existing modifications in `bot2/neural/model.py`, `bot2/phase5c_v3/{calibration,data_integrity,experiment_matrix,experiment_runner,model}.py`, and tests remain; partial authorization/preflight files and prior review documents are untracked. None were modified by this pass. This pass adds only this coordinator report.
4. **R1 conclusion:** `A0_CONTRACT_AMBIGUITY` for prior-source partition and transition no-prior behavior. V2 may reference frozen semantics unchanged, but cannot invent missing A0 rules.
5. **R2 conclusion:** a structural ledger is possible, but the comparison membership for an A0 structural-unavailability row is not determined by frozen authority. Record that membership as unresolved; do not treat an unadopted V1 rule as authority.
6. **R3 conclusion:** calibration is validation-only, but its fitting-row granularity and interaction with A0 availability are underspecified. Frozen abstention is post-calibration entropy selection; scoring/denominator treatment for abstentions is not fully authorized by frozen text.
7. **R4 conclusion:** unresolved A0 availability plus calibration/abstention and reason/provenance rules leave manipulation and unequal-denominator paths. No V2 can close them without prospective scientific decisions or implementation controls beyond this pass.

## Frozen A0 contract reconciliation

| A0 component | Frozen authority | Required inputs | Source partition | Causal availability | Prediction availability | Existing abstention | Tie-break | V2 changes it |
|---|---|---|---|---|---|---|---|---|
| Previous-label persistence | Frozen v2 protocol/manifest; repeated in v3 | Latest matching root/head/horizon target and its full information interval; frozen session/contract scope | **Unspecified**; current validation/calibration lookup is implementation behavior, not authority | Target anchor `< T`; information interval end `<= T`; no future or immature label | Repeat the latest authorized prior label | Explicitly abstain if unavailable | Latest authorized prior; duplicate/tie resolution not fully stated | **NO** |
| TRAIN majority | Frozen v2 protocol/manifest; repeated in v3 | TRAIN labels by root/head/horizon and frozen class vocabulary | TRAIN for counts | TRAIN-only counts | Constant majority output for eligible rows; no row-specific prior | No prior-related abstention defined | Lexical class-label tie-break frozen; probability-decoding tie rule is separately lowest class index | **NO** |
| TRAIN transition matrix | Frozen v2 protocol/manifest; repeated in v3 | TRAIN adjacent transitions, Laplace `α=1`, and latest eligible prior state | Transition counts are TRAIN-only; prior-state source partition **unspecified** | Prior label must be mature by `T` | Transition probability conditioned on authorized prior state | No-prior behavior not explicitly frozen; no fallback authority | Probability output tie treatment is distinct; no separate majority tie-break | **NO** |

The source-partition and missing-transition-prior ambiguities must remain flagged as `A0_CONTRACT_AMBIGUITY`. Current code behavior does not resolve frozen authority. A0 majority's lexical-vs-index behavior remains the separately identified `IMPLEMENTATION_DEFECT`; this pass did not fix it.

## Required V2 design decisions

8. **Whether V2 changes A0:** no scientific A0 component may change. However, the V1-derived proposal added a prior-stream rule and a no-prior transition abstention rule absent from frozen authority. Those are not safe to carry into V2 as mere evaluation clarifications.
9. **Pre-inference eligibility definition:** conceptually, structural eligibility may use only manifest-bound source/data integrity, instrument/contract, timestamp/session, frozen partition, feature-sequence completeness, target-interval metadata, and purge/embargo rules. No realized target class/value, prediction, confidence, loss, correctness, P&L, return, metric, or ranking may affect it. Every permitted predicate needs exact frozen-source binding.
10. **Pre-inference ledger definition:** row ID; ES/NQ instrument; timestamp; exact contract/session; root/head/horizon/WF window; manifest/data/source hashes; structural-eligibility status and reason; per-model/seed input-availability status; frozen model-definition hash; A0 matured-prior status and scope status; comparison group; comparison-membership status; calibration/abstention rule identifiers; explicit `NOT_RUN` downstream states; canonical row/group hashes. Do not store outputs/labels/performance in the pre-inference ledger.
11. **Whether eligibility requires inference:** no. A structural ledger should be reproducible without A0/A1/A2 inference, calibration transformation, metrics, or P&L. This alone does not settle the policy for an A0 prior that frozen authority cannot source.
12. **Structural A0 unavailability:** prior-dependent A0 lacks a causally matured state under a source/scope rule expressly permitted by the frozen contract. The current source partition is unspecified, so the exact structural test is not determinable for every row.
13. **Inference-time abstention:** output-stage abstention is a result of the frozen model/threshold after inference (for example, entropy threshold after calibrated probabilities). It is distinct from pre-inference input unavailability. Existing A0 persistence explicitly abstains if no prior; transition's no-prior action is unspecified.
14. **Common paired-set definition:** for a fully frozen participant group, a candidate design is the intersection of U with all participants' pre-inference model-definition-available rows. But if A0 structural availability is unresolved, the exact membership for those rows cannot be set without adding A0 semantics. Do not freeze this as final in V2 absent an authorized decision.
15. **Calibration ordering:** original procedure is validation-only calibration after model probability output, before applying frozen entropy threshold; it cannot affect structural or pre-inference membership.
16. **Calibration isolation:** no OOS targets, future information, protected metrics, or one model family’s outcomes may select another model’s calibration or eligibility. However, fitting-row identity and interaction with A0 abstentions must be explicitly resolved without changing calibration parameters/rule.
17. **Abstention ordering:** model inference → validation-fitted calibration transform where frozen → frozen validation-selected entropy threshold → scoring/reporting. The abstention output must not retroactively change pre-inference eligibility. Frozen authority does not fully specify how abstentions enter all direct comparison metrics.
18. **Metric denominator rule:** no adopted V2 denominator. Any later rule must bind exact row IDs/hash, use a common paired denominator for every metric claimed as a direct comparison, and fail closed on runtime/output faults rather than shrinking the set.
19. **Output-dependent selection:** prohibited. Current implementation path still needs a separate engineering review to prove it cannot build row sets from successful output artifacts.
20. **Performance-dependent selection:** prohibited; no correctness, target agreement, loss, confidence, P&L, return, Sharpe, metric or rank may determine eligibility, masks, status, or denominator.
21. **Post-hoc selection:** unresolved until participant enumeration, row masks, reason reconciliation, calibration/abstention interaction, and deterministic cell terminal rules are fully frozen and mechanically evidenced.
22. **A0 favoritism:** a conditional intersection can hide cold-start/availability gaps and should never be described as full-universe performance; no coverage threshold is authorized.
23. **A1 favoritism:** unequal denominators or selecting groups/rows after output can favor A1; require identical predeclared paired row identities and report availability separately.
24. **A2 favoritism:** output/entropy-driven filtering can select easier A2 rows; require pre-inference eligibility and prohibit post hoc removal. The V1 selective-intersection proposal does not satisfy a strict same-ID rule across all comparative metrics.

## Blocker decisions

25. **Blocker 1 — A0 prior-source behavior:** **UNRESOLVED.** Frozen source partition is unspecified; choosing one would define/change A0 behavior, which V2 is prohibited from doing.
26. **Blocker 2 — output-dependent/selective row selection:** **UNRESOLVED.** A pre-inference structural ledger is a sound direction, but ambiguity in A0 availability prevents final paired membership. V1's output-dependent selective metric intersection remains disallowed under the strict invariant. Existing implementation provenance/recomputation controls are not proven.
27. **Blocker 3 — calibration/A0 abstention:** **UNRESOLVED.** Calibration fit rows and abstention scoring/membership are not sufficiently defined by frozen authority; V2 may not invent new scoring or calibration semantics.

## V2 artifact status

28. **V2 path:** not created. The four reviews did not support a fully defensible V2; creating one would violate the instruction not to send unresolved work as approval-ready.
29. **V2 byte length:** N/A — no V2 artifact.
30. **V2 SHA-256:** N/A — no V2 artifact.
31. **Detached digest verification:** N/A — no V2 artifact.
32. **V1 preserved:** yes. Exact bytes remain 22,381 bytes, SHA-256 `EB9E08338C20EAD395E0915078CAEB80BDD600FD39F4791F8BFB3FD640296B4F`; detached digest verified in the previous independent review and still matches on read-only check.
33. **Original protocol preserved:** yes. Raw SHA-256 remains `23905DBD4215669477645313B931243A644E83755577C4ABF7AC57A0ADC62667`.
34. **Manifest preserved:** yes. Exact-file SHA-256 remains `FB12989A0E4062EA63B0A335D62B718BA02AD3082C42E63372CABC2F035A1FA5`; canonical manifest identity remains `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
35. **Implementation unchanged:** yes, by this V2 remediation pass; no tests or source writes were made.
36. **Protected archive rerun count:** 0.
37. **Protected inference count:** 0, based only on the existing no-score receipt/report; not rerun or reopened.
38. **Protected prediction count:** 0, existing no-score record only.
39. **Protected metric count:** 0, existing no-score record only.
40. **Protected P&L count:** 0, existing no-score record only.
41. **Protected score count:** 0, existing no-score record only.
42. **A2 input shape:** `[8,24]`.
43. **A2 parameter count:** `7,417`.

## Remaining blockers and final disposition

44. Frozen A0 prior source and transition no-prior semantics are incomplete; V2 cannot invent them.
45. The current A0 row-abstention behavior, pre-inference masks, complete row-level reason mapping, exact metric recomputation on common IDs, calibration fit-row binding, and frozen abstention scoring require independent protocol and implementation decisions. The worktree is dirty, not a clean review candidate.
46. **Final conclusion: BLOCKERS REMAIN — V2 NOT YET DEFENSIBLE.** No V2 proposal, adoption, implementation, test, protected archive rerun, or scoring authorization was made. Phase 5C-Z stays paused; do not resume B/C, fix the tie-break, run protected OOS, seal Z, or start Phase 6.
