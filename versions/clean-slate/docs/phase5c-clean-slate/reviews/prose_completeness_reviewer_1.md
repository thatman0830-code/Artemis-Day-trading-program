# BOT2 Phase 5C prose completeness review — Reviewer 1

**Date:** 2026-09-24  
**Verdict:** **NO**

## Inputs reviewed

- `w/docs/BOT2_PHASE5C_CLEAN_SLATE_PROTOCOL_PROPOSAL.md` — SHA-256 `C6E4EA97883A03497EFEDB93AE785409E01D021F2CDE00D001390786C6294AC8`
- `w/docs/BOT2_PHASE5C_TECHNICAL_INVENTORY.md` — SHA-256 `B8E0585AB0A97B80F7CB141284EC20983A273CAF464CF809677BB9322C958811`

## Reproducibility finding

Two competent teams cannot implement this prose and independently produce the same evaluation populations, comparisons, denominators, states, and ordering. The proposal itself says it is “NON-EXECUTABLE” and Section 13 names unresolved inputs. The missing values are not routine implementation details: many determine which examples exist, which labels can be used, what each system predicts, what gets compared, and how results are counted. Assigning values to those inputs would invent protocol choices.

## Concrete blockers

1. **The population and its chronological partitions are not constructible.** Section 2 requires a non-null dataset ID, source and normalized hashes, coverage, schema, and code commit, but the inventory records a null dataset ID and does not supply the other runtime gate values. Section 2 also leaves feature definitions and support, target construction and maturity, clock semantics, and WF boundaries and roles as required gates. The inventory supplies WF1–WF4 identifiers only and target horizons/class names, not the dates, membership, support intervals, endpoint conventions, or maturity rules. Sections 4–5 consequently cannot determine identical fit/evaluation rows or label-maturity eligibility without invented dates and target semantics.

2. **Key eligibility and row ordering are underdefined.** Section 8 requires a frozen model-independent eligible universe and a sorted canonical key set, but does not define the exact data-quality/labelability eligibility predicate, key serialization, sort fields/directions, or tie-break for otherwise equal keys. Its instruction that those rules “must be encoded and versioned” defers their content to a later protocol. Section 2 separately requires clock and tie-order semantics; Section 6 leaves synchronization anchor, staleness limit, unmatched streams, and tie ordering open. Different lawful choices change eligible keys and their ordering.

3. **The model inputs and comparable outputs are not fixed.** Section 2 requires the 24 feature definitions, availability semantics, sequence assembly, preprocessing, training recipe, seeds, output schema, and failure handling. The inventory establishes feature and model identities/shapes, but not those evaluation-time rules. Section 7 explicitly says the systems’ probability-vector versus hard-class outputs and A0 probability definitions are unknown, and bars probability comparisons until a contract exists. Thus teams cannot guarantee the same candidate outputs or even the same available comparison set by head/horizon.

4. **The denominator and state model does not resolve all row lifecycles.** Section 8 leaves the frozen eligibility predicate open and requires exactly one current state while also making `SCORED` terminal “for that record and metric,” allowing abstained rows to remain scoreable for probability metrics, and retaining predictions with post-forecast invalid/unavailable targets. It does not specify whether states are per row, metric, head, or output type, the transition/precedence rules, or a single state for a row with both scoreable probabilities and an abstained class decision. `MODEL_INPUT_UNAVAILABLE`, typed outcome-unscoreability, and `FAILURE:<reason>` can also describe overlapping events without a precedence rule. It names counts and a full-eligible coverage denominator, but leaves the eligibility and metric-specific scoreability predicates to future definition. Teams could therefore count the same lifecycle differently.

5. **The comparison estimand and aggregation are intentionally unset.** Sections 9–10 leave the primary endpoint, metric hierarchy, claim family, uncertainty method and parameters, multiplicity control, and aggregation order/weights for formal review. Section 7 identifies candidate systems and ablations but does not settle the output contract or which claims are confirmatory. Teams could produce different comparisons and pooled summaries while complying with the prose. An explicit instruction to report component cells does not determine the comparison or aggregation rule.

## Conclusion

The proposal is useful as a fail-closed checklist for a later protocol, but it is not a deterministic implementation specification. Teams can agree to stop before protected-data access when prerequisites are missing; that is not the same as being able to generate the same evaluation populations, comparisons, denominators, states, and ordering. Verdict: **NO**.
