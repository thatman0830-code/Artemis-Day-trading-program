# BOT 2.0 Phase 5C S4 Incident Timeline

**Scope:** read-only Git/filesystem provenance; no scientific design.  
**Protected result artifact:** not opened, read, deserialized, parsed, hashed, or stat'ed.  
**Exposure classification:** `UNKNOWN`.

## Established Git chronology

The following identities/times come from Git commit ancestry and object metadata. They establish that the listed bytes existed in those commits; they do not by themselves establish that a commit predates the S4 incident.

| Event | Commit/ref | Recorded time (local, -07:00) | Provenance significance |
|---|---|---|---|
| V1 manifest | `6a79f53e653944620fe582be33caccdd370269f9` | 2026-09-21 17:26:16 | V1 manifest blob exists in committed history. |
| Feature-label registry | `fb0f0dd5607d466a0e59573beddcb5b7af226fe7` | 2026-09-21 17:07:47 | Committed identity; incident-relative order unknown. |
| Feature registry v3 | `c47eb3c62aebc3bb7500125f1988377d67b52e70` | 2026-09-21 17:54:09 | Committed identity; incident-relative order unknown. |
| V2 manifest/protocol | `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94` | 2026-09-21 18:20:22 | V2 blobs are committed ancestors of V3. |
| V3 protocol and A2 implementation snapshot | `9a1ecfaf08077252049dd187d44f8641da1186aa` | 2026-09-21 19:45:21 | V3 protocol and model source blob identities established. |
| V3 provenance and lock | `66caddf995af9c6e78e8852055bae25459b57b18` | 2026-09-21 21:04:52 | Provenance/lock blobs established. |
| Intermediate ancestry | `4f1d706`, `bc2af76` | Sep. 21, 21:25:55; 22:19:02 | Git ancestry only; exact source relation in F1 notes. |
| Ablation contract/config | `b0a889bce8d70bd9553b5118429c0f291c1e493f` | 2026-09-21 22:47:46 | Ablation contract blobs committed. |
| Later ancestry | `f867bf4` | 2026-09-22 00:25:43 | Ancestor in the linear history. |
| Current branch HEAD | `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb` | 2026-09-22 22:06:28 | Last tracked snapshot at the audit; branch `bot2-phase5c-z-review-remediation`. |
| Y branch reflog | branch created from `b0a889b`; Y commit at `fe9a9aa` | Sep. 21 23:10:13; Sep. 22 22:06:28 | Branch/ref chronology; no S4 time binding. |
| Z branch reflog | created from `fe9a9aa`; checkout | Sep. 23 00:10:27; 00:11:01 | Branch/ref chronology; no S4-specific ref/worktree. |

The named commits form a single-parent chain as inspected by the forensic roles. Git author identity is the synthetic `Repository Owner Baseline <owner-baseline@local.invalid>`; it does not identify the human or agent that acquired or reviewed a source.

## S4 window

The prior audit record reports that an initial S4 broad search surfaced an unidentified serialized artifact beneath `outputs/`. No direct incident transcript, command output, access log, exact artifact path, artifact hash, task start/end time, or exposure time was available to this audit. The replacement S4 and its claimed restricted scope are also not evidenced by a transcript or task record.

- **Last provably clean event relative to S4:** none established. `fe9a9aa` is the latest provable committed snapshot, but its position relative to S4 is unknown.
- **First possibly contaminated event:** the reported initial S4 broad-search surfacing; exact time and exposure level unknown.
- **Exact incident time established:** no.
- **Causal Git ordering established:** yes, for commit ancestry/ref events; not for any S4 exposure versus those events.
- **Exposure class:** `UNKNOWN` (cannot distinguish reference-only, metadata-only, or content-exposed).

Filesystem metadata for untracked Y/Z/V4/V5 files is recorded by F1 only as observations and is not used to prove incident order. F1 noted that the earliest observed untracked Y-review timestamp was Sep. 23 00:07 local and that V4 files showed Sep. 23 local/Sep. 24 UTC metadata, but those dates do not establish acquisition or S4 ordering.

## Worktree and handling notes

The branch and HEAD at forensic start were `bot2-phase5c-z-review-remediation` / `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`. The worktree was already dirty. F1 reports a single `git ls-files` command piped through a filter that displayed only non-`outputs/` paths. No protected file content was emitted, opened, read, hashed, or stat'ed; the command may have internally traversed index path metadata. This is recorded as a process-scope deviation from the coordinator's stricter delegation instruction, not evidence that the protected artifact was accessed.

## Timeline conclusion

Git identity and partial order are recoverable; the incident cutoff and source acquisition lineage are not. No candidate can be marked `CLEAN_CONFIRMED` on this timeline alone.
