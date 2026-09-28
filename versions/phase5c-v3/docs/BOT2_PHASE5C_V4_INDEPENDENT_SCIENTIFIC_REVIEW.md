# BOT 2.0 Phase 5C V4 Independent Scientific Review

**Review disposition: NOT APPROVED — REVIEW CONTAMINATION CANNOT BE BOUNDED**

**Scope:** Independent, performance-blind review of the exact proposed V4 protocol and machine-readable companion. This report does not adopt V4 or authorize implementation, inference, scoring, OOS, training, trading, or Phase 6.

## 1. Reviewer, repository, and provenance

- Reviewer: fresh reviewer for this review; did not design V4, participate in S1–S5, coordinate the V4 design, author V3/V1/V2, implement Phase 5C-Z or A0/A1/A2, or participate in the reported S4 exposure.
- Branch: `bot2-phase5c-z-review-remediation`.
- HEAD: `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`.
- Worktree: dirty at review time. Existing modified source/tests and untracked Phase 5C-Z/V4 material were present. They were left untouched except for this report.
- No protected archive was rerun. No protected inference, prediction, probability, metric, P&L, or score was produced by this review. No scoring was performed.
- Evidence was limited to the named protocol/configuration/report files and repository metadata. Nothing under `outputs/` was enumerated, searched, opened, hashed, or otherwise inspected.

## 2. Artifact identities

| Artifact | Full path | Bytes | Independently computed SHA-256 | Detached sidecar result |
|---|---|---:|---|---|
| V4 proposal | `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3\docs\BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md` | 23,182 | `3f697ee8fb2e802a9e9f0332f27504d6d8cdaa9220c32745d930bb34fa598630` | Match: `docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md.sha256` |
| V4 companion | `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3\config\bot2_phase5c_v4_protocol_proposal.json` | 9,175 | `32345143af5bc9e4021fbbd18aa39ea064aca33db040873b073f9f2ad79d75b0` | Match: `config/bot2_phase5c_v4_protocol_proposal.json.sha256` |

The detached sidecars contain the same respective digests. The JSON parses successfully. Its keys mark `status=PROPOSED_NOT_ADOPTED`, `executable=false`, `scoring_authorized=false`, `protected_oos_authorized=false`, and `trading_authority=NONE`; the prose says “PROPOSED — NOT ADOPTED” and denies implementation/inference/scoring/OOS/trading authority (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:3,147-149`; JSON keys `status`, `executable`, `scoring_authorized`, `protected_oos_authorized`, `trading_authority`). Artifact identity passes.

## 3. V3 preservation and prospective separation

The V3 protocol file is 3,724 bytes with raw SHA-256 `23905dbd4215669477645313b931243a644e83755577c4abf7ac57a0adc62667`, matching the hash in the V4 companion. The V3 manifest file is 21,841 bytes with raw SHA-256 `fb12989a0e4062ea63b0a335d62b718ba02ad3082c42e63372cabc2f035a1fa5`; its declared canonical SHA-256 and the V3 lock both give `c9ae6da9f8d73708c3ca17a28788c80722c5852c48ca658f8ffad75ecb56dc19`. The lock also retains protocol anchor `9a1ecfaf08077252049dd187d44f8641da1186aa` (`docs/BOT2_PHASE5C_V3_PROTOCOL.md:1-8`; `config/bot2_phase5c_v3_manifest.lock.json`). The observed files therefore match the recorded V3 identities at review time. This snapshot check does not establish historical immutability by itself.

V4 explicitly labels itself a new prospective design, preserves V3's disposition as `NON_EXECUTABLE_AS_WRITTEN_DUE_TO_PROTOCOL_AMBIGUITY`, and says new prior, abstention, calibration, pair, and boundary rules are V4 choices, not historical V3 rules (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:14,22,46-50,54-64`; JSON keys `relationship`, `a0`, `comparison`, `calibration`, `time_integrity`). The prospective/historical distinction is adequately disclosed.

## 4. Scientific review findings

1. **Identity and provenance:** Pass. Both V4 identities and detached sidecars match; JSON is parseable. V3 protocol and manifest file/canonical identities match their recorded values. The dirty worktree means these are current file identities, not clean-commit identities.

2. **V3 separation:** Pass for explicit separation. V4 declares prospective changes and does not claim that missing-prior, probability, pair, denominator, calibration/abstention, or 37-minute rules were in V3. The original V3 files remain present and hash-consistent.

3. **Performance blindness:** The stated rule-selection rationale is performance-blind on its face: V4 discloses the 5,184 / 5,112 / 72 structural counts, says the pattern was not a criterion, and forbids using readiness, outputs, correctness, losses, P&L, rankings, or coverage results for membership (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:18-22,70-89,141`; JSON keys `disclosure`, `eligibility.prohibited_membership_inputs`, `prohibited`). The 37-minute rule has a dependency-geometry rationale. However, this conclusion is limited by the unresolved S4 contamination provenance in section 5; I cannot independently establish that no contaminated recommendation entered V4.

4. **A0 majority:** The prospective rule is explicit: TRAIN-only counts by root/head/horizon; add-one-smoothed class probabilities; max-count hard label; lexical smallest frozen label on ties; empty TRAIN labels block the cell (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:58`; JSON keys `a0.majority`). This is deterministic and does not use evaluation outcomes.

5. **A0 persistence:** Uses the latest strictly earlier, fully matured label within the exact instrument/contract/session/root/head/horizon/target-version scope; reset at session/contract boundaries; one-hot forecast; no prior means explicit unavailability with no fallback, forward-fill, or imputation (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:59,62`; JSON keys `a0.scope_key`, `a0.prior_availability`, `a0.persistence`). The prospective stream may include labels from earlier evaluation/test windows only after target maturity. This is causally defensible as an online baseline, but changes test interpretation to sequential evaluation and must remain disclosed as such.

6. **A0 transition:** TRAIN-only first-order valid adjacent one-minute same-scope edges, Laplace α=1, no gap/session/contract/partition crossings; same matured prior stream as persistence; no prior or fallback means A0 unavailability. Probability ties use frozen lowest-class-index argmax, separately from the lexical majority tie (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:60`; JSON keys `a0.transition`). No-prior and empty-transition cases have named codes. The exact smoothed conditional probability denominator is not written out in the companion, although α=1 and the transition definition are present.

7. **Missing prior:** Deterministic, pre-inference unavailability. It does not fabricate labels, carry labels across sessions/contracts, or use future labels. It is excluded only from pairs requiring that A0 and remains in U and other pairs (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:59-64,76-83`).

8. **Tie-break:** V4 explicitly uses lexical label order for A0-majority and lowest class index for probability argmax. The existing V3 implementation's lowest-class-index behavior for majority is the documented historical implementation defect; V4 does not conceal or purport to repair it. The new majority rule is deterministic and label-order neutral only insofar as the frozen lexical label vocabulary/order is accepted as the predeclared convention.

9. **Pre-inference eligibility:** U and all named pair masks are defined before inference from source, schema, timestamp, sequence, interval, partition, purge/embargo and frozen input/prerequisite availability. Target values/classes, predictions, correctness, confidence, calibration output, metrics, P&L, rankings and runtime success are excluded from membership (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:68-89`; JSON keys `eligibility`, `comparison.eligibility_frozen_before`). This is conceptually sufficient to build row sets without inference, but the proposal itself notes the deterministic inference-disabled ledger check has not been implemented (`:89`).

10. **Pair-specific comparisons:** Confirmatory pairs are A1 vs validation-selected A0 and A2 vs validation-selected A0; fixed secondary pairs are A2 vs each A0 and A1 vs A2; three-way intersection is sensitivity-only. Each pair has a participant-specific availability intersection with identical row IDs and denominators for both sides; all results must be reported (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:74-83,122-126`; JSON keys `comparison.primary_confirmatory_pairs`, `secondary_predeclared_pairs`, `pair_set_formula`). The validation A0 selection set is common across A0s. This avoids allowing a missing A0 prior to shrink A1-vs-A2.

11. **Output-independent selection:** Pass as a written rule. Rows cannot disappear for any model's error, abstention, low confidence, calibration effect, loss, target inconvenience, or P&L. Output/runtime faults block rather than shrink primary denominators (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:70-89,110,122,141`).

12. **Calibration:** Frozen scalar temperature scaling is validation-only, after raw probabilities, tied to model/seed and exact fit-row IDs/hash/count. It cannot alter U, pair membership, or primary row IDs; OOS fitting/tuning is prohibited (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:114-118`; JSON `calibration`). The fit population for A0 differs when matured priors are absent; V4 requires those masks be fixed before fit and reported. The companion omits temperature fitting's full probability transform and any explicit A0 one-hot treatment beyond “where probability exists”; it appears to rely on “frozen method” from V3. Exact normative parity is therefore incomplete, especially for persistence's one-hot forecast where temperature scaling is inert after normalization.

13. **Abstention and state distinctions:** The prose separates structural unavailability, prediction availability, calibration availability/error, no-prior abstention, entropy abstention, pair eligibility, scoreability, selective scoring, and cell disposition (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:100-118`). No-prior is pre-inference; entropy abstention is post-calibration. Cell failures do not shrink denominators. Primary metrics use the fixed pair rows and available probabilities; selective results use separately labeled paired retained intersections. Coverage and counts are required per pair/cell (`:118,126`).

14. **Metric denominators:** Primary macro-F1 and log loss use identical exact pair row IDs for both participants; all three A1/A2 seeds must be available for all planned rows, otherwise the pair blocks. Other frozen nonselective metrics use the same primary pair rows; selective metrics use their declared intersection and distinct denominator. Regression metrics do not apply. Existing support and multiplicity rules are retained (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:120-126`; JSON `metrics`). Denominators are predeclared and output failure cannot shrink them.

15. **Coverage versus performance:** Explicitly separate. V4 requires reporting availability/abstention and realized selective coverage separately from conditional selective performance and primary nonselective performance; it says coverage is not skill (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:118,126`; JSON `abstention`, `metrics`).

16. **37-minute boundary:** The arithmetic is coherent for frozen 60-second, length-8 input with a 30-minute feature lookback: earliest sequence feature is at T−7, whose raw dependency reaches T−37. The proposal applies 37 elapsed minutes uniformly to scored/calibration/early-stopping validation anchors after evaluation partition boundaries and purges labels by their full target interval (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:93-98`; JSON `time_integrity`). No evidence inspected indicates the value was chosen from the 72-cell pattern; both documents state the dependency derivation and uniform application. Remaining blocker: “partition boundary” and the relevant first anchor are not operationally pinned to a canonical timestamp/calendar rule (including session gaps and inclusive date partitions); companion says partition-start embargo but does not encode the prose's exact scored/calibration/early-stopping scope. Thus two teams could differ on which rows are checked/excluded. The value is justified geometrically, but its implementation boundary semantics are not complete.

17. **Causal integrity:** The protocol requires T-only features, mature labels, exact session/contract resets, no stitching or forward fill, exact ES/NQ timestamp alignment, TRAIN-contained transition edges, chronological partitions, purge and embargo, validation-only calibration/threshold selection, and fixed checkpoints/training inherited from the frozen design (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:59-62,91-98,114-118,145`; JSON `time_integrity`, `a0.prior_availability`). No direct future-leak path is specified. Exact boundary semantics above remain a blocker to executable assurance.

18. **WF neutrality:** Rules explicitly cover WF1–WF4 generically and declare no WF2 exception (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:18,96-98`; JSON `fixed_dimensions.walk_forward_windows`, `time_integrity.same_rule_for_all_wf_windows_roots_instruments_and_horizons`). No tailored WF2 rule found.

19. **Horizon neutrality:** The same rules apply to 5/15/30 minutes, with no special 30-minute workaround stated (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:18,96-98`; JSON `fixed_dimensions.horizons_minutes`). The 37-minute bound follows maximum feature dependency, not target horizon. No horizon-specific exception found.

20. **Instrument neutrality:** ES and NQ use the same rules, with exact same-session/timestamp cross-market matching and no forward fill (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:18,95,97`; JSON `fixed_dimensions.instruments`, `time_integrity`).

21. **Machine-readable parity:** Core identities, prospective A0 choices, eligibility, pairs, calibration ordering/fit partition, abstention coverage points, 37-minute value, metric denominators, prohibitions, authority flags, A2 shape `[8,24]`, and parameter count `7,417` agree across prose and JSON. Material gaps remain: (a) prose defines `INFERENCE_NOT_RUN`, `INFERENCE_ERROR`, `CALIBRATION_NOT_APPLICABLE`, and `CALIBRATION_ERROR`, but JSON `states.row` omits these while adding `SCORED`; (b) prose specifies the 37-minute rule for particular scored/calibration/early-stopping validation anchors, while JSON gives a generalized `evaluation_partition_start_embargo_minutes`; (c) prose specifies entropy tie ordering by timestamp, instrument, exact contract, while JSON specifies full cutoff tie groups but omits the ordering; and (d) calibration/probability transformations and A0 transition smoothing are less completely specified in JSON. These are normative companion omissions, not proof of a contradictory constant, but they undermine independent machine execution/parity.

22. **Executability:** Not established. The spec has substantial deterministic structure, but unresolved operational boundary semantics, machine-companion omissions, and an unimplemented inference-disabled ledger verification leave room for different implementations to construct eligibility/state/reason/denominator artifacts (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:89,97,128-137`). A clean implementation and engineering review are also explicitly future gates (`:149`).

23. **A0 favoritism red-team:** Fixed conditional pairs can hide cold starts if presented as universal A0 performance. V4 mitigates this with U coverage, explicit unavailability counts, all component comparisons, and a ban on describing pair-conditional metrics as full-universe performance (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:78-83,126,141`). This is defensible only if all required denominators and coverage reports are retained.

24. **A1 favoritism red-team:** Fixed A1-vs-A2 and A1-vs-selected-A0 sets, identical IDs per pair, all seeds required, no output-based removal, and full reporting reduce discretionary advantage. No A1-specific eligibility escape was found (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:76-83,122,141`).

25. **A2 favoritism red-team:** Confidence/correctness cannot filter primary rows; selective A2 results are secondary and use a distinct predeclared denominator. No A2-specific row rule is stated. A2 remains shape `[8,24]`, 7,417 parameters, with architecture/features/targets/training/checkpoints/seeds/ablations unchanged (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:141-145`; JSON `fixed_dimensions`).

26. **A2 freeze:** Pass. V4 does not redesign the model or its training surfaces. Shape `[8,24]`; parameter count `7,417` (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:145`; JSON `fixed_dimensions.a2_input_shape`, `a2_parameter_count`).

## 5. S4 artifact exposure and contamination bound

The coordinator reconciliation states that an initial S4 attempt used a broad search that surfaced a serialized artifact under `outputs/`; it says the reviewer was interrupted/excluded, the coordinator did not analyze it, replacement S4 work was restricted to named frozen documents, and the first attempt's findings were not used (`docs/BOT2_PHASE5C_PROTOCOL_V4_COORDINATOR_RECONCILIATION.md:82`). I treated these as coordinator assertions, not independently verified audit events.

No allowed named report or log identifies the surfaced artifact by path, content class, digest, exact exposure, initial reviewer/task identity, interruption transcript, or the replacement reviewer's identity and independent provenance. No audit evidence establishes whether protected performance information was in the serialized artifact, what the initial context observed, or whether any recommendation derived from it entered reconciliation/V4. The `outputs/` artifact itself was not inspected. Consequently:

- **S4 contamination classification:** `UNRESOLVED`.
- **Whether contaminated findings entered V4:** Cannot be independently determined. The coordinator says no; provenance is insufficient to bound that claim.
- **Contamination bound:** Not established. This alone requires the exact contamination-specific final conclusion.

## 6. Requested counters, blockers, and next steps

The review itself performed no protected work: archive reruns **0**; inference **0**; predictions **0**; probabilities **0**; metrics **0**; P&L calculations **0**; scores **0**. The prior receipt/proposal reports protected inference, predictions, probabilities, metrics, P&L, scores, and trades as **0** (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:20`; coordinator reconciliation `:75-82`). Those historical counters were not recomputed or independently verified in this review.

Remaining scientific blockers, apart from the unbounded S4 contamination, are exact operational semantics for the 37-minute partition boundary and the prose/JSON omissions that affect states, tie ordering, calibration, and boundary interpretation. The proposal also lacks the future inference-disabled engineering check it says is required. V4 is not adopted; the allowed next steps in the proposal remain owner approval of prospective choices, resolution of review provenance and specification discrepancies, a separately versioned manifest, clean implementation, independent engineering review, and separate explicit scoring authorization. No such step was taken here (`docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md:89,147-149`).

## 7. Required 50-field review record

1. **Reviewer independence:** Fresh reviewer; none of the excluded design, implementation, authorship, coordination, or initial S4 roles applied (section 1).
2. **Branch:** `bot2-phase5c-z-review-remediation` (section 1).
3. **HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb` (section 1).
4. **Worktree status:** Dirty at review time; existing changes preserved (section 1).
5. **V4 proposal path:** `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3\docs\BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md`.
6. **V4 byte length:** 23,182.
7. **V4 SHA-256:** `3f697ee8fb2e802a9e9f0332f27504d6d8cdaa9220c32745d930bb34fa598630`.
8. **Companion path:** `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3\config\bot2_phase5c_v4_protocol_proposal.json`.
9. **Companion byte length:** 9,175.
10. **Companion SHA-256:** `32345143af5bc9e4021fbbd18aa39ea064aca33db040873b073f9f2ad79d75b0`.
11. **Detached digests:** Both sidecars match independently computed file digests; JSON parses and declares `PROPOSED_NOT_ADOPTED`, `executable=false` (section 2).
12. **V3 preservation:** V3 protocol remains present and its raw hash matches its recorded identity; V4 describes V3 as unchanged/historical (`docs/BOT2_PHASE5C_V3_PROTOCOL.md:1-8`; V4 proposal `:10-14`).
13. **Manifest preservation:** V3 manifest raw digest, declared canonical digest, and lock record match at review time (section 3; `config/bot2_phase5c_v3_manifest.lock.json`).
14. **Prospective status:** Verified in both artifacts; V4 rules are new prospective choices, not retroactive V3 semantics (sections 2–3; V4 proposal `:14,22,46-50`).
15. **Performance blindness:** Written prohibitions/rationale do not select for protected outcomes or readiness; certification is limited by unresolved S4 provenance (section 4 item 3; section 5).
16. **A0 majority:** TRAIN-only, add-one smoothed probabilities, max-count label, lexical tie, explicit empty-TRAIN block (section 4 item 4; V4 proposal `:58`).
17. **A0 persistence:** Latest strictly earlier fully matured same-scope prior, one-hot output, session/contract reset, no prior fallback (section 4 item 5; V4 proposal `:59,62`).
18. **A0 transition:** TRAIN-only adjacent valid same-scope one-minute edges, Laplace α=1, no boundary/gap crossing, mature conditioning prior (section 4 item 6; V4 proposal `:60`).
19. **Missing prior:** Explicit deterministic pre-inference unavailability; no invented label, forward fill, fallback, or cross-session/contract use (section 4 item 7; V4 proposal `:59-64,76-83`).
20. **Tie-break:** V4 lexical majority tie is explicit; historical V3 lexical-vs-implementation-index defect remains disclosed and unfixed (section 4 item 8).
21. **Pre-inference eligibility:** U and pair masks are defined without inference or outcomes; engineering verification is still future work (section 4 item 9; V4 proposal `:68-89`).
22. **Pair-specific comparisons:** Two confirmatory and four fixed secondary pairs; pair participant masks determine identical IDs/denominators; three-way set is sensitivity only (section 4 item 10; V4 proposal `:74-83`).
23. **Output-independent selection:** Membership cannot depend on any model result, confidence, calibration effect, loss, P&L, run success, or target outcome (section 4 item 11; V4 proposal `:70-89,141`).
24. **Calibration:** Validation-only scalar temperature after inference and before entropy abstention; exact fit-row provenance required; cannot alter eligibility; companion has material omissions (section 4 item 12; V4 proposal `:114-118`).
25. **Abstention:** Structural prior absence, entropy abstention, prediction/calibration availability, pair eligibility, scoreability, selective coverage, and cell states are distinguished; selective metrics use a separate conditional denominator (section 4 item 13; V4 proposal `:100-118`).
26. **Metric denominators:** Primary metrics use exact pair IDs; all three neural seeds required; failure blocks rather than shrinks; selective denominators are separately fixed (section 4 item 14; V4 proposal `:120-126`).
27. **Coverage:** Reported separately from skill and conditional selective performance; V4 prohibits substitution of selective results for primary results (section 4 item 15; V4 proposal `:118,126`).
28. **37-minute boundary:** Derived as 30-minute lookback plus seven-minute length-8 sequence offset; applied uniformly, but exact operational partition-anchor semantics remain a blocker (section 4 item 16; V4 proposal `:93-98`).
29. **Causality:** T-only inputs, mature targets, reset boundaries, exact market alignment, no forward fill, partition purge, validation-only calibration/thresholds; operational boundary semantics remain unresolved (section 4 item 17).
30. **WF neutrality:** WF1–WF4 use general rules; no WF2-only exception found (section 4 item 18; V4 proposal `:18,96-98`).
31. **Horizon neutrality:** 5/15/30-minute horizons share governing rules; no 30-minute-specific workaround found (section 4 item 19; V4 proposal `:18,96-98`).
32. **Instrument neutrality:** ES and NQ share the same rules; cross-market inputs require exact session/timestamp match (section 4 item 20; V4 proposal `:18,95,97`).
33. **Machine-readable parity:** Core constants/status match; discrepancies include omitted prose states, entropy cutoff ordering, calibration details, and boundary scope (section 4 item 21).
34. **Executability:** Not established; boundary ambiguity, companion omissions, and absent inference-disabled ledger verification leave implementation choices (section 4 item 22; V4 proposal `:89,97,128-137`).
35. **A0 favoritism red-team:** Conditional A0 comparisons can conceal cold starts; fixed reporting of coverage/U and all comparisons mitigates this if retained (section 4 item 23).
36. **A1 favoritism red-team:** Fixed A1 pairs/IDs, all seeds, and no output-driven exclusions constrain advantage (section 4 item 24).
37. **A2 favoritism red-team:** No confidence/correctness filtering in primary rows; selective results are secondary; no A2-specific row rule found (section 4 item 25).
38. **S4 exposure classification:** `UNRESOLVED`; the incident is documented but independently bounded provenance is absent (section 5; coordinator reconciliation `:82`).
39. **Whether contaminated findings entered V4:** Cannot be independently determined. Coordinator says they were not used, but the evidence does not bound that assertion (section 5).
40. **A2 shape:** `[8,24]` (V4 proposal `:145`; JSON `fixed_dimensions.a2_input_shape`).
41. **A2 parameter count:** `7,417` (V4 proposal `:145`; JSON `fixed_dimensions.a2_parameter_count`).
42. **Protected archive rerun count:** 0 for this review (section 1 and section 6).
43. **Protected inference count:** 0 for this review; prior receipt also reports 0, not independently recomputed (section 6).
44. **Protected prediction count:** 0 for this review; prior receipt also reports 0, not independently recomputed (section 6).
45. **Protected probability count:** 0 for this review; prior receipt also reports 0, not independently recomputed (section 6).
46. **Protected metric count:** 0 for this review; prior receipt also reports 0, not independently recomputed (section 6).
47. **Protected P&L count:** 0 for this review; prior receipt also reports 0, not independently recomputed (section 6).
48. **Protected score count:** 0 for this review; prior receipt also reports 0, not independently recomputed (section 6).
49. **Remaining blockers:** S4 contamination cannot be bounded; 37-minute operational boundary and prose/JSON normative discrepancies remain; ledger reproducibility check and other stated owner/engineering gates remain future work (sections 4–6).
50. **Final conclusion:** **NOT APPROVED — REVIEW CONTAMINATION CANNOT BE BOUNDED** (section 8).

## 8. Final conclusion

**NOT APPROVED — REVIEW CONTAMINATION CANNOT BE BOUNDED**

Artifact identity and the explicit prospective status pass. Several V4 design elements are scientifically well specified on paper, but this review cannot certify performance blindness because the reported S4 exposure lacks independent provenance sufficient to establish what was surfaced and whether its findings were excluded. This conclusion is not an adoption decision and grants no execution or scoring authority.
