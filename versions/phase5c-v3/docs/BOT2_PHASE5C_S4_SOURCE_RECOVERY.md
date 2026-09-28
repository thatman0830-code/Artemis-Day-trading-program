# BOT 2.0 Phase 5C S4 Clean-Source Recovery

**Result: STOP — CLEAN SOURCE RECOVERY FAILED**  
This is a forensic-provenance report only. No Phase 5C design, adoption, implementation, or protected evaluation was performed.

## Summary

Four fresh read-only roles reviewed Git/filesystem timeline (F1), agent/context lineage (F2), document derivation (F3), and adversarial red-team review (F4). They establish a real V1→V2→V3 Git lineage and exact blob identities for tracked sources. They do **not** establish when the S4 artifact exposure occurred or which contexts received content. Byte identity to an old Git blob is not proof that the blob existed before S4 because the incident cutoff is absent. The recovered `CLEAN_CONFIRMED` source set is empty.

The prior 15-source list plus V1/V2/V3 records, named contracts, and S1–S5 source identities yields 30 enumerated candidate records in the machine-readable record. This is not an exhaustive inventory of all possible repository authorities; unknown provenance remains fail-closed.

## Classification totals

| Classification | Count |
|---|---:|
| `CLEAN_CONFIRMED` | 0 |
| `CONTAMINATED_CONFIRMED` | 0 |
| `QUARANTINED_UNCERTAIN` | 29 |
| `NON_SCIENTIFIC_AUDIT_ONLY` | 1 |

No source is classified contaminated because no evidence proves protected content entered a document or downstream agent context. No source is classified clean because there is no S4 cutoff or complete source/context lineage. This distinction is intentional: unknown is not equivalent to contaminated, but it is not eligible as design authority.

## Required final report

1. **Branch:** `bot2-phase5c-z-review-remediation`.
2. **HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`.
3. **Worktree:** dirty at audit start (modified Phase 5C implementation/tests and untracked Y/Z/V4/V5 material); forensic artifacts are new untracked files. Existing changes preserved.
4. **S4 exposure classification:** `UNKNOWN`.
5. **Last provably clean event:** None established relative to S4. HEAD `fe9a9aa` is the latest provable committed snapshot but incident-relative status is unknown.
6. **First possibly contaminated event:** Reported initial S4 broad-search surfacing of an unidentified serialized artifact under `outputs/`; exact time unknown.
7. **Exact incident time established:** No.
8. **Causal ordering established:** Partial Git commit/ref ancestry yes; no causal ordering between S4 exposure and those commits/documents.
9. **Original S4 agent/context:** Roster identifies `/root/s4_causal_temporal` as interrupted; context ID, task transcript, prompt, and tool log unavailable.
10. **Coordinator received contaminated content:** Unknown (full context vs summary vs none cannot be determined).
11. **S1 exposure:** Unknown.
12. **S2 exposure:** Unknown.
13. **S3 exposure:** Unknown.
14. **S5 exposure:** Unknown.
15. **Replacement S4 exposure:** Unknown; `/root/s4_causal_temporal_clean` is listed completed, but transcript/task inputs are unavailable.
16. **Candidate source records:** 30 enumerated; not exhaustive.
17. **`CLEAN_CONFIRMED`:** 0.
18. **`CONTAMINATED_CONFIRMED`:** 0.
19. **`QUARANTINED_UNCERTAIN`:** 29.
20. **`NON_SCIENTIFIC_AUDIT_ONLY`:** 1 (the prior V4 independent review, limited to the rejection/audit history).
21. **V3 classification:** `QUARANTINED_UNCERTAIN`; byte-identical committed blob, S4-relative status unknown.
22. **Original manifest classification:** `QUARANTINED_UNCERTAIN`; byte identity to V1/V2/V3 commits does not establish pre-S4 status.
23. **A0 contract:** `QUARANTINED_UNCERTAIN`; identified within V3 source set, but not cleanly recovered.
24. **A1 contract:** `QUARANTINED_UNCERTAIN`; identified within V3 source set, but not cleanly recovered.
25. **A2 contract:** `QUARANTINED_UNCERTAIN`; committed source and current modified worktree differ; no incident cutoff.
26. **Feature contract:** `QUARANTINED_UNCERTAIN`; committed registry identity exists, but S4 cutoff is missing and the manifest-pinned registry digest differs from observed raw digest.
27. **Target contract:** `QUARANTINED_UNCERTAIN`; target identity is carried by V3 manifest, no separate clean target-spec file located in the referenced set.
28. **Walk-forward contract:** `QUARANTINED_UNCERTAIN`; identity in V3 manifest, no S4 cutoff.
29. **Calibration contract:** `QUARANTINED_UNCERTAIN`; identity in V3 manifest, no S4 cutoff.
30. **Abstention contract:** `QUARANTINED_UNCERTAIN`; identity in V3 manifest, no S4 cutoff.
31. **Ablation contract:** `QUARANTINED_UNCERTAIN`; committed doc/config blobs identified at `b0a889b`, but relation to S4 is unknown.
32. **Dataset-manifest classification:** `QUARANTINED_UNCERTAIN` (V3 manifest and lock identities exist; clean cutoff not established).
33. **Clean A2 identity recovered:** No.
34. **A2 shape if cleanly established:** N/A—not established from a `CLEAN_CONFIRMED` source.
35. **A2 parameters if cleanly established:** N/A—not established from a `CLEAN_CONFIRMED` source.
36. **Protected artifact opened:** NO.
37. **Protected archive reruns:** 0.
38. **Protected inference:** 0.
39. **Protected predictions:** 0.
40. **Protected metrics:** 0.
41. **Protected P&L calculations:** 0.
42. **Protected scores:** 0.
43. **Forensic artifact paths:** `docs/BOT2_PHASE5C_S4_INCIDENT_TIMELINE.md`; `docs/BOT2_PHASE5C_S4_AGENT_LINEAGE.md`; `docs/BOT2_PHASE5C_S4_DOCUMENT_DERIVATION_GRAPH.md`; `docs/BOT2_PHASE5C_S4_SOURCE_RECOVERY.md`; `docs/BOT2_PHASE5C_S4_FORENSIC_RED_TEAM.md`.
44. **Machine-readable classification:** `config/BOT2_PHASE5C_S4_SOURCE_CLASSIFICATION.json`.
45. **Remaining uncertainties:** S4 incident time, exact artifact identity and exposure level, original/replacement S4 transcripts/tool logs, coordinator transfer, S1/S2/S3/S5 contexts, V4 authoring derivation, and separate contract/source paths.
46. **Red-team conclusion:** F4 found no affirmative clean source; Git ancestry/blob equality is insufficient without a cutoff; no evidence of transitive exposure, but non-exposure is also unproven. One filtered `git ls-files` path-metadata enumeration is documented; no protected artifact content was accessed.
47. **Final conclusion:** **STOP — CLEAN SOURCE RECOVERY FAILED**.

## Git and contract evidence

- V1 manifest: commit `6a79f53e653944620fe582be33caccdd370269f9`, blob `6f2be7c0985c09ca65744f3cf18bf2d507d2e4d9`.
- V2 manifest/protocol: commit `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94`, blobs `65c091c960422f36567ec52499268142bf67ce8c` / `6b2f3013909004dfa4ffb453b8411e96e93bd27f`.
- V3 protocol/manifest: commit `9a1ecfaf08077252049dd187d44f8641da1186aa`, blobs `166bfc9b9044f39de5b6a96153171b491249ad4a` / `23281011ea68d85a9289291d002d56a39a409f7a`.
- V3 provenance/lock: commit `66caddf995af9c6e78e8852055bae25459b57b18`, blobs `99a602a771ba9e534770a0d757f3065d3bbb64ad` / `49d1f9aab5e70c44f1ffbf897cadf93e1944c967`.
- V3 ablation doc/config: commit `b0a889bce8d70bd9553b5118429c0f291c1e493f`, blobs `68da78b39ead21f5dd1a95fa91a6ac7a4b7e2759` / `29b3d9ae1b4e065f56791968c7fae75b941517a4`.
- These are **identity/ancestry facts**, not CLEAN_CONFIRMED classifications.

## Stop condition

The task's success condition requires a non-empty `CLEAN_CONFIRMED` scientific-source set. That count is zero. Do not reopen V5 or start design; a later, separately authorized independent forensic review would be required even if additional provenance arrives.
