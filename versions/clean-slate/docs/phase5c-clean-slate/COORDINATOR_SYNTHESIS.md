# Phase 5C clean-slate coordinator synthesis

**Status:** proposed synthesis only; not adopted, not executable.  
**Inputs:** frozen factual inventory and the five independently authored, hashed first drafts listed in `INITIAL_DRAFT_HASHES.md`.  
**No protected evidence:** no protected archive, outputs, scores, P&L, predictions, probabilities, or inference was opened or generated for this synthesis.

## Synthesis principles

1. Scientific evaluation is reset; technical architecture and trading authority are not changed.
2. Retain the identified ES/NQ object, 3 existing A0s, A1, A2, 3 horizons, target heads, and declared ablations as identities only.
3. Use a chronological, forward-only evaluation, because the deployment information set is past-to-future. Never infer missing cadence, target intervals, WF dates, source availability, or calendar rules.
4. Require every fit-time label to be fully matured and available before that fit origin. This is the exact training-label purge for forward chaining. Prohibit post-test observations from training; therefore no universal post-test embargo value is needed. If the design later allows non-forward folds, stop and redesign the split with target-support interval purging and separately justified embargo. No historical minute count is adopted.
5. Distinguish historical feature overlap from future-label leakage. A later forecast may reuse legitimately available past features; it may not use labels or transforms unavailable at the corresponding training/prediction cutoff.
6. Freeze one model-independent eligible universe, common comparison keys, explicit statuses, and complete denominators before prediction. Never let confidence, errors, scores, predictions, or model rank alter eligibility.
7. Report predictions, calibration, abstention, and coverage as separate concepts. Do not select a coverage target or a primary metric by looking at protected results. The independent drafts propose different defensible estimands; no scientific source or technical identity dictates one.
8. No unseen logistic baseline, new target, composite trading portfolio, trading rule, or architecture change is added in this reset.
9. All WF × instrument × horizon × head × model × declared ablation × seed cells must remain visible. Seeds are repeat fits, not independent market observations. Any inferential claim requires prespecified dependent-data and multiplicity handling.

## Provenance classification

| Rule/proposition | Provenance class | Status |
|---|---|---|
| Event/input must be available by the prediction anchor; a training label must mature before fit cutoff | `MATHEMATICALLY_DERIVED` | Adopt in prose candidate; exact timestamps and maturity semantics are a gate |
| Forward-only, chronological out-of-sample origins | `STANDARD_METHODOLOGY` | Prospective candidate choice supported by R01–R03 |
| No post-test training; no fixed post-test embargo for strictly forward-only fit | `MATHEMATICALLY_DERIVED` | Candidate rule; if split architecture changes, re-review |
| Label-support interval purge for any non-forward split | `MATHEMATICALLY_DERIVED` | Conditional rule; non-forward splits prohibited in present candidate |
| Separate train/calibration/threshold-selection/evaluation periods | `PROSPECTIVE_DESIGN_CHOICE` | Candidate; requires actual fold boundaries and data adequacy before executable use |
| Shared pre-inference sample population and full denominator accounting | `STANDARD_METHODOLOGY` | Candidate, with typed row states |
| Keep current A0/A1/A2 identities; add no new baseline or trading portfolio | `TECHNICAL_CONSTRAINT` | Candidate scope guard |
| Exact primary metric, probability metric eligibility, alpha, multiplicity family, seeds, abstention q, fold dates, session resets, contract pooling, ES/NQ tolerance | `PROSPECTIVE_DESIGN_CHOICE` / missing technical prerequisite | Unresolved; none may be inferred or selected from outcomes |

No normative rule is attributed to prior Phase 5C science.

## Residual disagreement and blockers

The fourteen-issue matrix is in `DISAGREEMENT_MATRIX.md`. The broad methodological convergence is enough for a useful prose candidate, but not enough for a machine-readable executable protocol. Specifically, the inventory does not supply: a non-null dataset identity; the 24 feature definitions and raw support windows; target construction, endpoint, maturity and label revisions; true as-of receipt/availability semantics; bar/anchor cadence; WF1–WF4 dates and split semantics; session calendar and roll handling; model output/probability contract; training hyperparameters/seed set; primary estimand; calibration and threshold operating point; or confirmatory inferential family. The missing values are all resolvable without protected results from engineering contracts, project owner choices, and public methodology; they must be frozen before protected evaluation.

The inventory was supplemented after P1–P5 submitted: read-only code inspection established the current 24 feature names, one-minute feature cadence, exact v3 target class formulas/support, and the limitation that exchange-time joins do not prove receipt-time availability. The frozen first drafts remain based on the original inventory hash, as recorded by the report authors; the addendum was not retroactively treated as their input.

Two independent reviewer pairs assessed two successive prose revisions. The first pair returned NO on the initial candidate. After the technical inventory addendum and prose corrections, the second pair also returned NO (reviewed proposal SHA-256 `628B2DBE046304B219E18C47C3497E170061FA0318D9D08ABAAC254E2DB2EF32`, inventory SHA-256 `EFDCF58689AC452A5D5A519A900F9A31EE759B338387F3879F6DD585253ED745`). Their reports are in `reviews/prose_completeness_v2_reviewer_a.md` and `reviews/prose_completeness_v2_reviewer_b.md`.

The remaining blockers are now narrower but still material: missing immutable source dataset identity/coverage, receipt-time and correction/finalization provenance, actual WF dates and split semantics, synchronized input freshness/unmatched policy, session/contract deployment policy, exact A0/A1/A2 output and training/seed contracts, deterministic canonical keys/state transitions/count denominators, and primary metric/aggregation/multiplicity/inference and abstention choices. The prose candidate intentionally refuses to invent these. No JSON translation, freeze, parity review, or final R1–R5 review is permitted after the NO completeness gate.
