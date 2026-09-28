# BOT 2.0 Phase 5C Clean-Slate Reset — Final Status

**Conclusion: BLOCKERS REMAIN — CLEAN-SLATE PROTOCOL INCOMPLETE.**  
**Date:** 2026-09-24  
**Scope:** evaluation-science reset only; no adoption, implementation, protected evaluation, trading or Phase 6.

1. **Branch:** `bot2-phase5c-clean-slate-protocol`.
2. **Parent commit:** `f867bf4ee42a852b9a8cbea3901171811cd85cdc`.
3. **HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`.
4. **Worktree:** isolated at `C:\Users\fjone\Documents\Codex\2026-08-21\referenced-chatgpt-conversation-this-is-an\w`; branch contains only new untracked documentation artifacts from this work. Original dirty worktree was not changed. No commit was created.
5. **Historical protocol status:** preserved as `HISTORICAL_NONAUTHORITATIVE`; not used as scientific authority.
6. **Protected-data firewall:** held. No protected outputs/data opened, no runs/inference/scores produced.
7. **Technical inventory:** created at `docs/BOT2_PHASE5C_TECHNICAL_INVENTORY.md`; includes factual addendum from read-only code inspection. Current SHA-256: `EFDCF58689AC452A5D5A519A900F9A31EE759B338387F3879F6DD585253ED745`.
8. **A2 technical identity:** `A2_LEARNED_CAUSAL_TCN`, architecture code ID `bot2-phase5c-a2-causal-tcn-v3`.
9. **A2 input shape:** `[8,24]`.
10. **A2 parameters:** 7,417, recorded as the implementation's static assertion; model not instantiated/executed.
11. **P1 conclusion:** use forward chronological origins; train labels must mature before fit origin. No extra post-test embargo is mathematically required for strictly forward-only training; exact cuts and actual maturity remain prerequisites.
12. **P2 conclusion:** existing three A0s are meaningful separate comparators; history-based baselines require matured labels and deterministic ties. P2 also proposed a new logistic baseline and conditional flat reference; neither is added to the frozen object. No portfolio baseline.
13. **P3 conclusion:** proposed macro-recall endpoint, paired synchronized time-block bootstrap, and Holm-adjusted A2-vs-three-A0 family (including proposed alpha 0.05). These are proposals only, not adopted.
14. **P4 conclusion:** proposed separate calibration and threshold partitions, scalar temperature scaling, maximum-probability abstention, and a candidate nominal coverage `q=0.80`. The q value and method are not selected/adopted.
15. **P5 conclusion:** identified favorability paths across eligibility, missingness, abstention, metrics, aggregation, timing, boundaries, seeds, ablations and post-selection. P5's suggested max-horizon embargo is not adopted; see the temporal dependency resolution below.
16. **Material methodological disagreements:** 14, recorded in `docs/phase5c-clean-slate/DISAGREEMENT_MATRIX.md`.
17. **Unresolved:** at least 5 material groups remain; reviewers identified more operational sub-blockers. See item 51.
18. **Temporal dependency derivation:** feature support is the union of each feature's actual raw support over 8 sequence rows; equal one-minute anchors span 7 minutes, but session aggregates reach to session open. Label support is target-specific: future H one-minute closes plus a prior 30-return reference required by the current target generator. For forward training at origin `o`, require `m[i,h] < o`; this label-maturity purge is timestamp-derived. Sequence feature overlap alone is not leakage when all data were available then.
19. **Was 37 minutes used?** No. No historical buffer was used or adopted. No fixed-minute embargo was adopted.
20. **Eligibility methodology:** propose one model-independent canonical eligible population fixed before prediction, keyed by WF/instrument/contract/session/anchor/horizon/head, with reasons and no output-dependent selection. Exact key encoding and quality rules remain unresolved.
21. **Baseline methodology:** keep current A0 persistence, train-majority, and transition matrix as separate baselines; train statistics from matured history only; no silent fallback. Do not add a new baseline or portfolio in this reset.
22. **Calibration methodology:** P4 proposed temperature scaling on separate past-only calibration data; not selected because model probability interfaces/support remain unresolved.
23. **Abstention methodology:** distinct `PREDICTION_AVAILABLE`, `ABSTAINED`, `SCORED` states; coverage shown against the full eligible denominator. Numerical q/threshold and baseline treatment unresolved.
24. **Comparison methodology:** same eligible keys/truths; no silent complete-case advantage; failures and coverage remain visible. Exact common output contract and confirmatory paired population are unresolved.
25. **Coverage methodology:** report eligible, input-available, predicted, abstained, pending, failed and scored counts separately; full-denominator coverage is distinct from selective risk.
26. **Multiple-comparison methodology:** all planned models/heads/horizons/WFs/ablations/seeds must be visible; no post-selected winner. Claim families and correction remain unresolved; P3's Holm proposal is not adopted.
27. **Seed methodology:** freeze and report every seed, never select best; seeds are repeated fits, not independent market observations. Exact seed set/training recipe unavailable.
28. **Ablation methodology:** preserve declared ablations as explanatory secondary analyses, not a performance search. Exact claim families remain unresolved.
29. **Failure-state methodology:** proposal uses explicit structural-unavailability, pending, input-unavailable, prediction, abstention, scored and typed-failure states. Independent reviewers found state precedence, per-metric lifecycle and denominator formulas insufficiently operational.
30. **External methodological references:** 23 entries in `docs/phase5c-clean-slate/METHODOLOGY_REFERENCE_LEDGER.md`.
31. **Prose protocol path:** `docs/BOT2_PHASE5C_CLEAN_SLATE_PROTOCOL_PROPOSAL.md`.
32. **Prose SHA-256:** `628B2DBE046304B219E18C47C3497E170061FA0318D9D08ABAAC254E2DB2EF32`. This is the candidate hash reviewed, not a freeze hash.
33. **Prose completeness:** NO. Two independent reviewers on the revised candidate both returned NO; their reports include the matching input hashes. The prior candidate pair also returned NO.
34. **JSON path:** not created. The two-reviewer YES gate failed.
35. **JSON SHA-256:** not applicable.
36. **Prose/JSON parity:** not run; no JSON exists.
37. **Material parity discrepancies:** not applicable; translation was correctly stopped before beginning.
38. **R1 conclusion (A0-favorability adversary):** not run; frozen-prose gate failed.
39. **R2 conclusion (A1-favorability adversary):** not run; frozen-prose gate failed.
40. **R3 conclusion (A2-favorability adversary):** not run; frozen-prose gate failed.
41. **R4 conclusion (temporal-leakage adversary):** not run as a final-review role; P5 initial draft covered leakage risks, but is not a substitute.
42. **R5 conclusion (post-selection adversary):** not run as a final-review role; P5 initial draft covered selection risks, but is not a substitute.
43. **Protected archive runs:** 0.
44. **Protected inference:** none.
45. **Protected predictions:** none generated or opened.
46. **Protected probabilities:** none generated or opened.
47. **Protected metrics:** none generated or opened.
48. **Protected P&L:** none accessed.
49. **Protected scores:** none generated or accessed.
50. **Implementation changes:** none to code, models, risk controls, data pipeline, or trading behavior. Documentation-only artifacts were created on the isolated branch; no tests were run.
51. **Remaining blockers:** immutable dataset identity and coverage; proof of event receipt/clock/late-correction and label-finalization semantics; actual WF dates/membership/fit schedule; session calendar, contract/roll and cross-market freshness/missingness policy; A0/A1/A2 training/config/seed and probability-output contracts; canonical key encoding/order, eligibility, state transitions and exact denominator formulas; primary metric, aggregation, calibration/abstention operating point; dependence-aware inference parameters and multiple-comparison families. Two reviewers specifically found populations, states, denominators and ordering non-reproducible from the candidate.
52. **Final conclusion:** `BLOCKERS REMAIN — CLEAN-SLATE PROTOCOL INCOMPLETE`.

## Safest next step

Do not access protected results or create the JSON companion. Resolve the remaining source/technical facts from versioned, non-protected contracts and obtain prospective owner decisions for the scientific choices. Then revise the prose and repeat two fresh independent completeness reviews. Adoption and protected evaluation remain separate gates.
