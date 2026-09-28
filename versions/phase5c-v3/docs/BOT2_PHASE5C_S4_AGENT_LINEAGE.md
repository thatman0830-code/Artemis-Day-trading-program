# BOT 2.0 Phase 5C S4 Agent / Context Lineage

**Method:** fresh read-only F2 review of the available agent roster, task summaries, and provenance/audit summaries. No `outputs/` artifact or result content was accessed. No scientific interpretation was performed.

## Contexts

| Context | What is available | Proven exposure / transfer finding |
|---|---|---|
| Initial S4 reviewer `/root/s4_causal_temporal` | Roster identifies the agent as interrupted. Prior coordinator history reports its broad repository search surfaced a large serialized evaluation artifact under `outputs/`. No transcript, tool log, prompt, or access log is available. | The artifact is reported as surfaced, but whether only a path/reference, non-performance metadata, or protected contents entered context is **UNKNOWN**. |
| Replacement S4 reviewer `/root/s4_causal_temporal_clean` | Roster provides a completed summary that it used explicitly named protocol/config sources. No transcript/tool log, independent task identity, or input manifest is available. | Claimed restriction is not independently verifiable; exposure status **UNKNOWN**. |
| Coordinator context | Prior reconciliation asserts the initial reviewer was interrupted/excluded, the coordinator did not analyze the artifact, the replacement was restricted, and first-attempt findings were not used. | Whether coordinator received the initial agent's full context, a summary, or nothing is **UNKNOWN**. Assertions are not transfer logs. |
| S1, S2, S3, S5 | No distinct report paths, task identities, transcripts, or context IDs were available in inspected provenance records. | Each exposure status **UNKNOWN**; absence of a record is not proof of non-exposure. |
| Later V4 independent reviewer `/root/v4_independent_review` | Its review report states no protected work was performed and concludes contamination cannot be bounded. Its actual task/context/tool footprint is unavailable. | Independence and non-exposure **UNKNOWN**; use its report only as a rejection/audit record. |
| F1–F4 forensic reviewers | Fresh disjoint agents in this forensic pass. F1 reports one metadata-only path enumeration caveat; F2–F4 did not access `outputs/`. | No protected content was accessed by these reviews. They are audit records, not scientific authorities. |

## Information-flow reconstruction

The evidence supports only this limited chain:

```text
initial S4 broad search
    └─ reported artifact surfacing under outputs/ (level UNKNOWN)
         ├─ coordinator transfer: UNKNOWN
         ├─ replacement S4 inputs: UNKNOWN beyond a claimed named-doc restriction
         ├─ S1/S2/S3/S5 exposure: UNKNOWN
         └─ V4 authoring/reconciliation influence: UNKNOWN
```

Contamination is **not** assumed to propagate to every agent merely because they shared a project. Conversely, non-transmission cannot be certified without the missing transfer records. The file-level V3→Z→V4 reference graph does not prove which task context supplied any scientific recommendation.

## Missing evidence

- Initial and replacement S4 task prompts, transcripts, context IDs, and tool logs.
- Exact initial search command/output and whether any serialized values were rendered to the model context.
- Incident start/end timestamps and file/access logs.
- Coordinator messages showing what content was received and subsequently passed onward.
- S1/S2/S3/S5 prompts and transcripts.
- V4 authoring prompts and input/derivation manifest.
- Verified reviewer identity/provenance for replacement S4 and the later V4 review.

## Finding

**S4 exposure classification: `UNKNOWN`.** The strongest supported statement is that a protected artifact was reportedly surfaced to an initial S4 context. Exposure cannot be classified as `REFERENCE_ONLY`, `METADATA_ONLY`, or `CONTENT_EXPOSED` from available evidence. Coordinator, S1/S2/S3/S5, replacement S4, and later reviewer exposure all remain unknown.
