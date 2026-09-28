# BOT 2.0 Phase 5C S4 Document Derivation Graph

**Scope:** metadata and explicit source references only. No `outputs/` files were accessed. Hashes identify bytes; they do not establish S4-relative cleanliness.

## Supported graph

```text
V1 manifest [6a79f53]
  └─ V2 manifest + V2 protocol [ff81aa3]
       └─ V3 protocol / V3 manifest [9a1ecfa]
            ├─ V3 provenance + lock [66caddf]
            ├─ feature registry [c47eb3c]
            └─ ablation contract/config [b0a889b]
                 └─ later committed review chain [f867bf4 → fe9a9aa]

V3 references ──> untracked Z proposals/reviews/coordinator records
S1–S5 (named in reconciliation; separate paths/transcripts unavailable)
        └─> V4 proposal + JSON companion (untracked)
              ├─> V4 coordinator reconciliation (untracked)
              └─> V4 independent rejection review (untracked)
                    └─> V5 clean-source audit records (untracked)

initial S4 context ──> reportedly surfaced unknown serialized artifact
                       under outputs/; information transfer to any node unknown
```

Solid chronology for committed nodes is Git ancestry. Arrows for untracked documents reflect explicit/documented references and task sequence only; they are not complete task-input provenance. No S4 cutoff ties the two branches.

## Document identity and incident classification

| Source group | Identity evidence | S4-relative classification | Derivation / uncertainty |
|---|---|---|---|
| V1 manifest | Blob `6f2be7c0985c09ca65744f3cf18bf2d507d2e4d9`; commit `6a79f53e653944620fe582be33caccdd370269f9`; raw SHA-256 `1bf23da166271ae23beec9eaf4f3681415c6dcd4df1c7591676bab506a3c37c8` | `QUARANTINED_UNCERTAIN` | Byte-identical committed object; no S4 event cutoff. |
| V2 manifest/protocol | Manifest blob `65c091c960422f36567ec52499268142bf67ce8c`, protocol blob `6b2f3013909004dfa4ffb453b8411e96e93bd27f`; commit `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94`; raw hashes in machine record | `QUARANTINED_UNCERTAIN` | Committed ancestry to V3; pre-V4 is not proof of pre-S4. |
| V3 protocol | Blob `166bfc9b…`; commit `9a1ecfaf08077252049dd187d44f8641da1186aa`; raw SHA-256 `23905dbd4215669477645313b931243a644e83755577c4abf7ac57a0adc62667` | `QUARANTINED_UNCERTAIN` | Committed byte identity established; incident time unknown. |
| V3 manifest | Blob `23281011ea68d85a9289291d002d56a39a409f7a`; commit `9a1ecfaf08077252049dd187d44f8641da1186aa`; raw SHA-256 `fb12989a0e4062ea63b0a335d62b718ba02ad3082c42e63372cabc2f035a1fa5` | `QUARANTINED_UNCERTAIN` | Includes manifest identities for model/target/WF/calibration/abstention; no S4 cutoff. |
| V3 provenance/lock | Provenance blob `99a602a7…`, commit `66caddf…`; lock blob `49d1f9aab5e70c44f1ffbf897cadf93e1944c967`, commit `66caddf995af9c6e78e8852055bae25459b57b18`; lock SHA-256 `7cb99e0862aad63d28896ab888f9422e99737f923a0f8ded8b3dc3238dbc4a32` | `QUARANTINED_UNCERTAIN` | Hash/commit identity does not resolve incident chronology. |
| Feature registry / feature-label registry | Feature registry blob `7857540cd74533f66814a914577989013d550986`, commit `c47eb3c…`; raw SHA-256 `60631310aed0f558dc99ca8c920a4832975efe55786784b731403abbb73b86a2`. Feature-label blob `c2e66a2f3f59e92f3155a7df3414515a28b8fb96`, commit `fb0f0dd…`; SHA-256 `4d76977850d63776d8c8a7b4a02ac81b9d13e0586337d676466397b7729ee954` | `QUARANTINED_UNCERTAIN` | Committed identities; V3 manifest-pinned registry digest `a0c32f66…` differs from observed raw SHA; digest procedure unresolved. |
| A0/A1 contracts | Roles reside in the V3 protocol/manifest source set above | `QUARANTINED_UNCERTAIN` | No separate clean contract artifact established; no S4 cutoff. |
| A2 identity/implementation | V3 manifest/protocol and tracked model files; current worktree model files are modified after HEAD | `QUARANTINED_UNCERTAIN` | Historical clean A2 source cannot be certified relative to S4. |
| Target/WF/calibration/abstention contracts | Version/hash fields carried in the V3 manifest and protocol | `QUARANTINED_UNCERTAIN` | Manifest identity known; target is not separately located in the inspected contract set; S4 timing unknown. |
| Ablation contract/config | Doc blob `68da78b39ead21f5dd1a95fa91a6ac7a4b7e2759`, config blob `29b3d9ae1b4e065f56791968c7fae75b941517a4`; commit `b0a889bce8d70bd9553b5118429c0f291c1e493f` | `QUARANTINED_UNCERTAIN` | Committed identity; no incident cutoff. |
| Z documents (7) | Exact per-file SHA-256 recorded in machine record; all untracked/no Git blob or author | `QUARANTINED_UNCERTAIN` | File references identify V3 inputs, but task/source lineage and S4 cutoff absent. |
| V4 proposal/companion/reconciliation | Proposal SHA-256 `3f697ee8…598630`; JSON `32345143…9d75b0`; reconciliation `f4f6e5a2…7dd6b8`; untracked | `QUARANTINED_UNCERTAIN` | S1–S5 synthesis asserted; whether S4 findings flowed in is unknown. |
| V4 independent review | SHA-256 `7c2ee1718ad19dcd94997bcd537139e99abd0a14a55382d6712ecbdd9c5259ce`; untracked | `NON_SCIENTIFIC_AUDIT_ONLY` | May describe V4 rejection and defect categories only; cannot supply design rules or clean-source proof. |
| S1–S5 separate reports | Exact paths, hashes, commits, prompts, and transcripts not found in safe named records | `QUARANTINED_UNCERTAIN` | The labels occur in reconciliation, but separate source identities/lineage are absent. |

## Important identity caveats

- The clean V3 manifest raw hash is `fb12989a0e4062ea63b0a335d62b718ba02ad3082c42e63372cabc2f035a1fa5`; its blob is `23281011ea68d85a9289291d002d56a39a409f7a`. Its canonical digest is separately recorded as `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`.
- The manifest's feature-registry digest and the observed registry raw digest differ; no resolution was inferred.
- Working-tree A2/model-related files are modified relative to HEAD. The forensic record distinguishes working bytes from committed blobs and does not treat mutable working files as historical proof.
- All listed commits predate the untracked V4 proposal by observed chronology, but the S4 incident time is not established. **Pre-V4 does not imply CLEAN_CONFIRMED.**

## Conclusion

The V1/V2/V3 lineage is a real Git ancestry chain; however, without a provable S4 cutoff or context derivation logs, no source in that chain can be affirmatively classified `CLEAN_CONFIRMED`. The V4 independent review is audit-only; other uncertain documents remain quarantined.
