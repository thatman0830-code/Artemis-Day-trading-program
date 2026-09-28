# Independent prose completeness review — Reviewer B

**Date:** 2026-09-24  
**Inputs reviewed:**

- `docs/BOT2_PHASE5C_CLEAN_SLATE_PROTOCOL_PROPOSAL.md` — SHA-256 `628B2DBE046304B219E18C47C3497E170061FA0318D9D08ABAAC254E2DB2EF32`
- `docs/BOT2_PHASE5C_TECHNICAL_INVENTORY.md` — SHA-256 `EFDCF58689AC452A5D5A519A900F9A31EE759B338387F3879F6DD585253ED745`

## Could two competent engineering teams implement this specification and produce the same evaluation populations, comparisons, denominators, states and ordering?

**NO.** The proposal is an appropriate fail-closed design outline, but it intentionally leaves essential protocol choices and source-specific facts unresolved. Independent teams would have to supply those choices, and could therefore produce different populations, comparisons, denominators, state histories, and report ordering. The proposal itself reaches the same conclusion in §13 and correctly remains non-executable.

Concrete blockers:

1. **The evaluated population cannot be constructed.** Section 2 gate 1 requires a non-null dataset ID, hashes, coverage interval, and contract scope; the inventory says the declared dataset ID is null and provides no evaluation coverage. Section 2 gates 4–6 also leave clock/tie rules, WF dates and membership, refit schedule, contract/session reset policy, and ES/NQ synchronization unresolved. Section 4 says WF1–WF4 are identifiers only and exact boundaries are not specified. Section 8 requires a frozen eligible universe and complete data-quality/labelability rule but does not define or encode that rule. Thus teams cannot independently derive the canonical eligible key set in §8 or the exact population for each WF × instrument × horizon × head.

2. **Eligible-row accounting and state ordering are under-specified.** Section 8 names states and says each key has one current state plus append-only transition history, but supplies no permitted transition graph, event precedence, or rule for resolving simultaneous/pending/late events. `SCORED` is described as terminal “for that record and metric,” while the same key may participate in multiple metrics; the per-metric state identity and relationship between these state instances are not fixed. The row key in §3 identifies fields but does not define canonical key encoding or sort order. Teams can consequently produce different state histories and orderings, and ambiguous count assignments for pending, unavailable, failed, and scored records.

3. **Target maturity and train eligibility cannot be reproduced from this prose and inventory.** Section 5 defines a suitable maturity predicate but requires actual receipt/finalization times and correction policy; §2 gate 3 and the inventory addendum expressly say these are not established. WF fit origins are also unspecified (§4). The inventory’s exchange-time target endpoints and prior 30-return support do not supply the real-time maturity timestamps. Teams therefore cannot determine the same matured training rows or evaluation outcome availability.

4. **The system comparisons are not fully operationally defined.** Section 7 identifies the candidate names and requires matched eligible populations, but explicitly says probability outputs and A0 probability definitions are unknown. Section 2 gate 7 leaves training recipes, configs, seeds, software identity, and failure handling to be frozen later. A0 previous-label/history availability and tie behavior also depend on the unresolved target schema/output contract. Section 9 leaves the primary endpoint and claim family unselected, while §10 leaves the inferential method’s block units, block-length rule, replicate count, endpoint calculation, alpha, and multiplicity control unresolved. Teams might report the same candidate names but still implement materially different comparisons and claims.

5. **Several numbered rules are proposals for future choices rather than executable instructions.** Sections 4, 7, 9, and 10 repeatedly defer role omission, refit/cutoff choices, output contract, metric hierarchy, calibration/abstention, aggregation, and uncertainty details to a future adoption gate. The inventory is explicitly factual and nonnormative and cannot resolve them. Section 13 enumerates these remaining gaps, including source identity, split dates, training recipe/seeds, label maturity, synchronization tolerance, and multiplicity plan.

Accordingly, there is no unique implementation derivable by two teams from these two inputs. A fresh protocol must freeze the missing source and split definitions, eligibility rule, lifecycle/state and ordering contract, target maturity evidence/policy, model output/training contract, and comparison/metric/inference plan before implementation or evaluation. This review does not authorize either.
