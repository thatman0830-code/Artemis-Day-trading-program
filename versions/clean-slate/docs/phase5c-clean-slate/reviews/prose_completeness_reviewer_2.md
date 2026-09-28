# BOT2 Phase 5C — Independent Prose Completeness Review 2

**Date:** 2026-09-24  
**Inputs reviewed (and only inputs reviewed):**

| File | SHA-256 |
|---|---|
| `w/docs/BOT2_PHASE5C_CLEAN_SLATE_PROTOCOL_PROPOSAL.md` | `C6E4EA97883A03497EFEDB93AE785409E01D021F2CDE00D001390786C6294AC8` |
| `w/docs/BOT2_PHASE5C_TECHNICAL_INVENTORY.md` | `B8E0585AB0A97B80F7CB141284EC20983A273CAF464CF809677BB9322C958811` |

## Verdict

**NO.** Two competent engineering teams cannot implement this prose alone and reliably produce the same complete evaluation populations, comparisons, denominators, states, and ordering. The document explicitly leaves the protocol non-executable and makes many of the missing decisions prerequisites for a later adoption gate. Reaching the same result would require supplying those inputs from outside this specification or making choices the prose does not fix.

## Concrete blockers

- **The source population is not identifiable.** Section 2 requires a non-null dataset ID, source and normalized hashes, exact contracts, coverage, and schema, but the inventory says `source_dataset.dataset_id` is null and supplies no evaluation coverage or active contract membership. The proposal does not select values for those gates. Section 8 requires a model-independent frozen universe and labelability rule, but does not define that rule or the source rows/sample keys to which it applies. Teams therefore cannot construct the same eligible key set.

- **The WF populations and chronology are not defined.** Sections 2 and 4 leave WF1–WF4 dates, interval boundaries, memberships, chronological role cutoffs, window type, fit-history policy, and refit schedule unresolved. The inventory expressly records WF identifiers only. These choices determine both training populations and evaluation rows; section 13 confirms split dates and chronology remain unresolved.

- **Feature and target row membership cannot be reproduced.** Sections 2, 3, and 6 require exact feature definitions/support, availability and tie ordering, target support/endpoints/thresholds/maturity, calendar, contract-roll, synchronization, and missingness rules, but provide none of the object-specific values. Section 5 gives a maturity predicate once maturity times and target-support intervals exist; it does not establish them. The inventory identifies schemas and counts, not their row-construction semantics. Different valid choices change feature availability, train-label eligibility, and scoreable evaluation rows.

- **The exact comparisons and endpoints are not selected.** Section 7 names the comparison systems and ablation identities, but says outputs may be hard labels or probability vectors and does not specify A0 probability behavior. Section 9 expressly leaves the metric hierarchy and primary endpoint unselected; it describes alternative hard-label and probability metrics with different populations and interpretations. Sections 2, 9, and 10 also leave calibration/abstention applicability, claim family, uncertainty procedure, and multiplicity plan open. Teams cannot produce the same defined comparison or inferential claim without choosing among these alternatives.

- **Several denominator and state rules remain underdetermined.** Section 8 calls for one current state per key and append-only transitions, but `SCORED` is terminal “for that record and metric” while a row may have several heads, horizons, metrics, probabilities, and an abstention decision. It does not define whether state is per key, per system, per output type, or per metric, nor the exact allowed transition graph and precedence when failures, pending outcomes, abstention, and scoreability coexist. The instruction to retain target-invalid predictions in population/coverage accounting does not specify a distinct target-invalid state or its placement in the table. Teams could report different state counts even with identical predictions. The denominator labels (“valid predictions,” “prediction availability,” “scoreability,” and “full eligible”) also lack a complete per-metric operational mapping.

- **Ordering and comparison alignment are not canonicalized.** Sections 3 and 8 call for a stable source sample key and a “sorted canonical key set,” respectively, but do not define key construction, sort fields, null handling, or tie-break ordering. Section 2 says tie ordering must be gated, and section 7 says class tie ordering must be verified, but neither freezes it. These gaps prevent identical row order, key hashes, and potentially tie outcomes.

- **The declared candidate identities do not fill the missing recipes.** The inventory supplies code-level model identities, shapes, and target names, while section 2 still requires the exact frozen training recipe/configuration, deterministic seeds, output schema, and failure handling. Section 7 leaves insufficient-history behavior typed but does not define each baseline’s complete statistic, minimum history, or transition/tie behavior. Consequently, even the candidate outputs being compared are not fully specified by these two documents.

Section 13 itself states that the exact evaluation population, primary endpoint, probability contract, thresholds, split dates, training recipe/seeds, target maturity, calendar/contract policy, synchronization tolerance, and statistical/multiplicity plan remain unresolved. Those are direct blockers to the reproducibility question, not implementation details that can be uniquely inferred from the prose.
