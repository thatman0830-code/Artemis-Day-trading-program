# BOT 2.0 Phase 5C S4 Forensic Red-Team Review

**Role:** F4 fresh, read-only independent challenge of F1 timeline, F2 context lineage, and F3 document graph. No scientific design and no protected artifact access.

## Challenges applied

1. **Could committed bytes be called clean merely because they predate V4?** No. Git confirms ancestry and blob identity, but the S4 exposure timestamp and source acquisition time are absent. The linear V1/V2/V3 history does not establish its position relative to S4.
2. **Could an old blob have been recreated after exposure?** Git object identity proves byte equality to the committed snapshot. It does not prove that the snapshot itself was acquired before the incident or that the commit content was not influenced by S4; a cutoff/transcript is needed.
3. **Could timestamps establish a cutoff?** No. Untracked filesystem timestamps are not reliable causal evidence here and some reported dates are anomalous. Reflog records branch/ref operations, not the S4 task start or artifact access.
4. **Could absence of an S4 branch/worktree prove isolation?** No. Current refs/worktrees contain no S4-specific entry, but that does not establish which context read or received information.
5. **Could contamination be assumed transitive?** No. There is no evidence proving protected-content transfer to S1/S2/S3/S5 or coordinator. But absence of transfer logs also cannot establish non-exposure.
6. **Could a coordinator summary establish exclusion?** No. It is an assertion without the original agent transcript, coordinator messages, input manifest, or derivation map.
7. **Can the V4 review serve as clean design authority?** No. It is an untracked post-incident report with self-reported reviewer provenance and explicitly unresolved exposure. It can be retained only as a non-scientific audit record of V4 rejection.

## F1 enumeration note

F1 reports one `git ls-files` command piped through a filter that displayed only paths outside `outputs/`. No `outputs/` pathname was emitted to the reviewer, and no protected file was opened, read, hashed, or stat'ed. The command may have traversed Git index path metadata internally. The user's attachment bars opening/reading the protected result artifact and enumerates content-level prohibitions; it does not explicitly bar non-content path-metadata enumeration. Therefore F4 finds **no evidence of protected content access or a violation of the user's literal restriction**, while recording a **process-scope deviation from the coordinator's stricter delegation instruction** (“do not list/search/hash any outputs path”). This path-metadata command does not resolve or worsen the historical S4 exposure.

## Red-team disposition

- S4 exposure: `UNKNOWN`; no support to distinguish reference-only, metadata-only, or content-exposed.
- Recovered `CLEAN_CONFIRMED` scientific sources: **0**.
- The 29-source candidate classification set (machine record) is not complete evidence of all repository content; unlocated report paths and source contracts remain unknown.
- F1–F3 consistently stop short of claiming that all historical documents are contaminated. Their quarantine is due to missing affirmative cleanliness evidence.
- Required missing evidence: S4 original and replacement task transcripts/tool logs, exact exposure time/output, coordinator transfer records, S1/S2/S3/S5 task contexts, and V4 derivation/input history.

**F4 conclusion:** the clean-source recovery success condition is not met. **STOP — CLEAN SOURCE RECOVERY FAILED.**
