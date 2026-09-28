# BOT 2.1 Phase R0-D — X1–X4 Freeze Record V2

Status: COMPLETE — RECOVERY PASS FROZEN. This document records recovered adversarial evidence and an unresolved cross-review comparison. It is not an R20 response, R1 protocol, architecture selection or authorization to use data or execute research.

Repository: `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`  
Research directory: `docs\bot21_research\`  
Branch: `bot2-phase5c-z-review-remediation`  
HEAD: `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`  
Record date: 2026-09-25, America/Phoenix (UTC−07:00).  
Baseline timestamp: 2026-09-25T00:15:48.4316707-07:00  
Post-X3/pre-V2 verification timestamp: 2026-09-25T00:42:22.4039750-07:00

## 1. ORIGINAL ATTEMPT

The original `BOT21_X1_X4_FREEZE_RECORD.md` remains preserved as historical evidence, with SHA-256 `3F87610B25B17075A78E45A3EB698487BD344E7F96087A652177ACF3DD99127A`.

That record states that X1 exhausted independent-agent capacity before producing a report. X2 and X3 reportedly completed in isolated contexts but their files were absent from the repository at freeze time. Their reported hashes and conclusions therefore did not constitute verified repository evidence. Only X4 was present and frozen.

The recovery did not reconstruct or paraphrase the inaccessible X2/X3 reports. This V2 supersedes the old record's incomplete batch status only; it neither overwrites historical evidence nor retroactively validates inaccessible artifacts. Historical X2/X3 counts and alleged source additions do not enter recovery totals.

## 2. RECOVERY PASS and independence

The coordinator reconfirmed branch, HEAD, R20, X4 and the original record before launching X1. The pre-existing DIRTY worktree was retained. All 38 existing research documents received a baseline SHA-256; frozen R01–R19 are explicitly included.

Three distinct specialists were launched with fresh contexts using `fork_turns=none`:

| Reviewer | Agent identity | Context and sequence | Status |
|---|---|---|---|
| X1 complexity skeptic | /root/x1_complexity | Fresh; first reviewer | COMPLETE, persisted and frozen |
| X2 capacity skeptic | /root/x2_capacity | Different fresh context; launched only after X1 freeze | COMPLETE, persisted and frozen |
| X3 temporal attacker | /root/x3_temporal | Third fresh context; launched only after X2 freeze | COMPLETE, persisted and frozen |
| X4 statistical attacker | Existing original report | Not regenerated; read by coordinator only after X1–X3 freeze | COMPLETE, original identity preserved |

Each recovery specialist was permitted R20, relevant frozen R01–R19, supporting R20 documents, registry material and public primary sources. Prompts prohibited X reports, original X freeze-record conclusions, inaccessible prior X conclusions, predecessor drafts, protected outputs/results/OOS, data, source code and credentials. The specialists attested that their first-pass conclusions were independent. They wrote no files; complete reports were returned to the coordinator.

X1's report was received, written as a new repository file, reopened and checked against the complete received text, hashed and frozen before X2 began. The same gate was completed for X2 before X3 began. X3 returned a clerical correction to its displayed R20 digest before any X3 persistence; it did not change scientific content or consult another X review. Its corrected complete report is the frozen artifact.

Windows command-length limits required segmented persistence for X2/X3. No partial file was treated as complete: both were fully reopened and compared against the entire received report before freezing. A rejected initial X1 command had a parsing error before execution; its successful create-new write was separately verified. No existing file was overwritten. These are document-persistence operations, not repository tests.

Only after all three gates closed did the coordinator read X4 and the original freeze record. Comparison below therefore did not feed back into any recovered reviewer. No frozen X report was edited after its gate.

“Frozen” means the verified bytes and digest are recorded and treated as immutable evidence in this workflow. No Git commit, filesystem read-only attribute or external anchor was created; this is not a claim of hardware-enforced immutability.

## 3. Artifact identities and persistence gates

| Artifact | Status | SHA-256 |
|---|---|---|
| R20_COORDINATOR_SYNTHESIS.md | Existing frozen input; MATCH | A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE |
| X1_COMPLEXITY_SKEPTIC.md | Recovered, COMPLETE and FROZEN | A869D0E35BD16CF5E14295D54F74AAC1C0662200FEE8DDCC5FD3C4DD7546246F |
| X2_CAPACITY_SKEPTIC.md | Recovered, COMPLETE and FROZEN | B90650EDD1E2790757C123D8F91E923AEEE06490F907042C72344A946CAB31CF |
| X3_TEMPORAL_CAUSALITY_ATTACK.md | Recovered, COMPLETE and FROZEN | 5CCFF03FE8A92CA90B88000C8DE6D62F22BB294BFDDA04BFF382036DCC6F1232 |
| X4_STATISTICAL_DATAMINING_ATTACK.md | Existing frozen report; MATCH | CA315086345B22E0839A548D488764D817237E7DE26E6B48C249F0D4142F45D4 |
| BOT21_X1_X4_FREEZE_RECORD.md | Original historical record; MATCH | 3F87610B25B17075A78E45A3EB698487BD344E7F96087A652177ACF3DD99127A |

| Gate | Bytes, UTF-8 without BOM | Required numbered sections | Exact full-text readback | Freeze timestamp |
|---|---:|---:|---|---|
| X1 | 29817 | 20 | PASS | 2026-09-25T00:23:18.8055169-07:00 |
| X2 | 33368 | 24 | PASS | 2026-09-25T00:32:38.2551721-07:00 |
| X3 | 32092 | 28 | PASS | 2026-09-25T00:41:43.8645520-07:00 |

Each report also includes its explicit completion marker. Hashes were calculated from local files, not inferred from agent claims. V2's own hash must be computed after its final write and reported externally to avoid a self-referential digest.

## 4. Counting method and historical discrepancy

Counts below are raw objection-ledger entries, not unique defects across reviewers, empirical discoveries or votes. X1 and X2 count newly established objections and carry R20's existing gates separately. X3 explicitly counts two inherited unmet prerequisites. X4 classifies consequences for affected claims; its scope is therefore different from an unconditional count of newly discovered R1 failures.

X4's section 4 contains five BLOCKER entries: O1, O2, O3, O13 and O15. O13 is explicitly limited to economic claims, and O15 is conditional on failed controls. Its other eleven ledger entries are MAJOR. The original freeze record instead reports six X4 blockers, and X4 section 15 lists six readiness conditions in prose. These are different counting bases; no frozen record is corrected or silently reconciled here.

For reproducible arithmetic, this V2 uses X4's enumerated severity ledger: **5 BLOCKER, 11 MAJOR**. The historical six-blocker figure remains an unresolved documentary discrepancy for later coordinator handling. It must not be represented as six enumerated X4 BLOCKER IDs.

| Reviewer | BLOCKER | MAJOR | Counting qualification |
|---|---:|---:|---|
| X1 | 0 | 4 | New objections; inherited prerequisites retained separately |
| X2 | 0 | 3 | New objections; inherited prerequisites retained separately |
| X3 | 2 | 6 | Both BLOCKERs explicitly inherited from unresolved R20 prerequisites |
| X4 | 5 | 11 | Enumerated section 4 ledger; includes claim-specific/conditional blockers |
| Total | **7** | **24** | Raw ledger sum; not seven independent new R1 defects |

Using the historical X4 count would instead yield eight raw blockers. That alternative is disclosed solely to prevent silent disagreement with the old record, not adopted as the ledger-based total.

## 5. Reviewer summaries without adjudication

### X1 — Complexity skeptic

- Strongest objection: optional families and capabilities can become default workload without a specific marginal-information admission rule; the mandatory ladder's recurrence rung conflicts with conditional priority language.
- Most important remediation: require each added family or fitted layer to identify its unanswered hypothesis, simpler comparator, confounding controls and bounded stopping interpretation.
- Strongest point supporting R20: no ES/NQ winner is established; strong simple controls and program-wide selection accounting are already required.
- Strongest point challenging R20: the mandatory ladder and “smallest” core language can outrun those caveats.
- Recommendation retained as evidence: task-matched nulls, a regularized linear comparator, one compact MLP and one tiny causal TCN for a single later-authorized contrast; recurrence and richer capability questions remain conditional. This is X1's proposal, not a coordinator selection.
- MAJOR IDs: X1-MAJ-01 admission ambiguity; 02 mechanism identification; 03 excessive representation/target menu; 04 initial multitask/selective-prediction necessity.
- No new BLOCKER IDs. Standing R20 prerequisites are not waived.

### X2 — Capacity / underfitting skeptic

- Strongest objection: requiring simple/additive cross-market success before richer interactions can exclude conditional information with no main effect; bounded model failure cannot establish universal absence of signal.
- Most important remediation: define admission and negative conclusions by capability and information domain, with an adequacy rationale for each admitted representative.
- Strongest point supporting R20: it explicitly distinguishes insufficient evidence from impossibility and already includes longer-context and joint-information questions.
- Strongest point challenging R20: the shortlist's simple-cross-market-success prerequisite is not logically necessary for conditional interaction.
- Recommendation retained as evidence: eligibility for bounded longer-history, completed multiresolution, joint conditional-information and capacity-adequacy questions; attention, SSM/Mamba, learned multiresolution and local self-supervision remain exploratory. External checkpoints/event expansion have insufficient evidence; unmotivated large hybrids/MoE are not justified. These are capability classifications, not a selected roster.
- MAJOR IDs: X2-MAJ-01 additive prerequisite; 02 negative-claim scope; 03 compact-model adequacy.
- No new BLOCKER IDs. R20 prerequisites remain applicable.

### X3 — Temporal leakage / causality attacker

- Strongest objection: an accurately ordered archive can still contain information unavailable at the claimed decision or update time.
- Most important remediation: independent source approval and a defensible availability-and-eligibility contract including revisions, selection decisions and artifact completion/activation.
- Strongest point supporting R20: UNKNOWN prerequisite means the affected gate remains closed; equal timestamps do not establish causal availability.
- Strongest point challenging R20: finalized-history fallbacks and documentary defenses can be overread as establishing admissibility that has not been demonstrated.
- BLOCKER IDs: X3-B01 unresolved independent scientific-source authority; X3-B02 unestablished temporal admissibility. Both are explicitly inherited, not newly observed archive corruption.
- MAJOR IDs: X3-M01 finalized-history claim boundary; M02 eligibility/missingness chronology; M03 artifact activation; M04 semantic knowledge vintages; M05 complete dependency support; M06 continuous-series transformation identity/invariance.

### X4 — Statistical / data-mining attacker

- Strongest objection: apparently persuasive performance can result from uncounted researcher choices, reused evaluation and dependent observations; favorable scores do not waive validity gates.
- Most important remediation: separately authorized frozen statistical governance covering estimands, chronological roles, complete search ledger, multiplicity, dependence-aware uncertainty, denominators, calibration, controls and stopping.
- Strongest point supporting R20: causal availability, matched simple baselines, source authority and separate predictive/economic claims are necessary.
- Strongest point challenging R20: the documentary package does not establish that these controls or a frozen R1 protocol have been accepted.
- BLOCKER IDs under ledger convention: O1 future information; O2 holdout selection; O3 uncounted multiplicity; O13 economic cost/fill omissions (economic claims only); O15 failed controls ignored (conditional).
- MAJOR IDs: O4 dependence; O5 selected population; O6 unfair comparisons; O7 reused validation; O8 test-period calibration; O9 post-hoc score; O10 pooling; O11 retrospective regimes; O12 overstated support; O14 omitted human choices; O16 significance promoted to deployment.
- This recovery verifies X4's byte identity, not its historical authorship or every factual/readiness assertion. Its original independence attestation is retained, not recreated.

## 6. Areas of agreement

All four support simple task-matched controls, defensible source and temporal authority, bounded claims and explicit uncertainty. None establishes an architecture winner, ES/NQ profitability, clean archive or permission to run R1.

X1, X2 and X4 distinguish family labels from a scientifically fair contrast. X1 and X2 both reject novelty as an admission reason and universal “no signal” claims from a narrow failed comparison. X3 and X4 emphasize that exact joins, missingness and retained origins can alter the population and causal meaning.

All retain evidence burdens outside model scores. Architecture capacity cannot repair unavailable inputs; more citations cannot establish local lineage. Failed or sparse evidence need not become a forced positive or negative answer.

## 7. Areas of disagreement and contradictory recommendations

The intentional X1/X2 tension remains unresolved. X1 narrows the minimum initial portfolio and would require explicit earned admission for many extensions. X2 retains several capability questions as supported for initial testing so that conservative choices do not exclude the structure being sought. These recommendations differ in initial breadth, admission burden and the interpretation of a constrained budget. No winner is selected.

Both criticize a simple-model-success gate, but for different reasons: X1 warns against both self-sealing deferral and endless rescue search; X2 identifies interaction-only structure as a concrete counterexample. Agreement on that logical point does not erase disagreement about how much capability exploration belongs initially.

X1 treats multitask/learned selection as extensions that need separate admission. R20/X4 discuss controls for each predictive head and calibration/selectivity. Whether those heads or selective mechanisms belong initially remains open; describing their governance is not adoption.

X3 distinguishes valid retrospective or delayed claims from unavailable real-time claims. X4 imposes claim-specific statistical/economic gates. The scope of each gate must remain attached to its claim; economic cost/fill readiness is not silently made a prerequisite for every narrowly predictive question.

Severity conventions differ. X1/X2 report zero new blockers without opening R1; X3 counts inherited unresolved gates; X4 includes hypothetical claim-invalidating conditions. Their totals cannot be treated as evidence that reviewers disagree on whether data are currently approved.

## 8. Common and reviewer-specific R1 blockers

Common retained prerequisites: independently authorized source/partition/exposure boundary; defensible availability and target maturity; separated chronological selection/calibration/evaluation; bounded and recorded search; and effective isolation from BOT 2.0 authority. X1/X2 retain these without assigning new BLOCKER IDs.

Reviewer-specific enumeration:

- X1: no new blocker; its four MAJOR scope/identification objections remain unresolved.
- X2: no new blocker; its three MAJOR capability/inference objections remain unresolved.
- X3: two inherited source and temporal blockers, with explicit attention to vintages, causal membership, semantic knowledge and activation chronology.
- X4: five claim-scoped ledger blockers, including statistical selection/holdout and economic/control conditions. Section 15's broader readiness list remains part of X4's frozen position.

There is overlap, especially X3 temporal admissibility and X4 O1. No deduplicated numerical total is asserted. No prerequisite is closed by this freeze.

## 9. Questions for later coordinator resolution

1. How should initial breadth balance X1's smallest contrast with X2's capability-coverage concern?
2. Which admission conditions incorrectly demand marginal success before testing interaction?
3. What exact claim can a negative compact-model result support?
4. What constitutes adequate representation/capacity without an open-ended rescue search?
5. Which finalized/revised histories can support which delayed or retrospective claims?
6. How will origin eligibility, missingness, semantic vintages and model activation enter temporal authority?
7. How should X4's conditional/economic ledger and historical six-blocker count be reconciled?
8. Which controls are valid for the eventual dependence structure? X1's warning about arbitrary shuffling and X4's proposed negative controls require an explicitly justified later interpretation.
9. Which objections must be resolved before any R1 authorization, and which apply only to later economic or operational claims?

These are recorded questions. This document provides no rebuttal, R20 revision, candidate selection, target selection or experiment design.

## 10. Public source additions

Recovery additions total **5 public sources**: X1 = 0, X2 = 4, X3 = 1. X4 retains its historical 0. Counts describe additions relative to the reviewed registry, not five independent ES/NQ replications. The source registry remains byte-for-byte unchanged.

| ID | Source | Evidence type / scope |
|---|---|---|
| X2-S01 | [TimeMixer++, ICLR 2025](https://proceedings.iclr.cc/paper_files/paper/2025/hash/2b187165e28fdfdc0ffb34d1bfff2b0c-Abstract-Conference.html) | Peer-reviewed generic multiscale modeling; transfer unproven |
| X2-S02 | [Slimming the Fat-Tail: Morphing-Flow, ICML 2025](https://proceedings.mlr.press/v267/liu25bq.html) | Peer-reviewed representation/adaptation; no endorsement of test-time adaptation |
| X2-S03 | [TimeDART, ICML 2025](https://proceedings.mlr.press/v267/wang25r.html) | Peer-reviewed self-supervised representation; financial transfer unproven |
| X2-S04 | [Transformers are SSMs / Mamba-2, ICML 2024](https://arxiv.org/abs/2405.21060) | Sequence efficiency/capability; not local performance evidence |
| X3-S01 | [pandas.merge_asof documentation](https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html) | Living official technical documentation; key matching is not availability certification |

Reviewers also revisited existing sources and recorded counterevidence and limitations within their reports. The coordinator preserves their source assessments without claiming an additional independent literature replication. X2's S52 wording concern and X1's S101 title distinction are later bibliographic questions; no frozen registry correction occurred.

## 11. Preservation and safety record

Pre-V2 verification found **all 38 pre-existing research files unchanged**, including R01–R20, X4, the original freeze record, support documents and source registry. The baseline and verification hashes are recorded in Appendix A.

Git branch and HEAD remained the expected values. Every baseline porcelain-status entry remained present and unchanged; the only added entries before V2 were the three X recovery reports. The worktree remained DIRTY. The final post-V2 check must allow only the fourth named new document, this V2 record. Git status was read with optional locks disabled and a command-local safe-directory setting; no Git configuration file, index, branch or commit was changed. The sandbox's inaccessible global-ignore warning was observed; preservation comparisons used the same status mode. Git status comparison is not a byte-level audit of every nonresearch file.

BOT 2.0: no source inspection or task write; all pre-existing dirty entries preserved. R01–R19: baseline byte hashes matched, and no intentional modifications. A0/A1/A2, Phase 5C, datasets, labels, features, manifests, risk, execution, brokers and operational systems: no task writes or execution.

Protected outputs/results accessed: NO. Protected OOS accessed: NO. Dataset/credential access: NO. Training, inference, scoring, benchmarking, experiments, repository tests, backtests, paper/live trading or broker connections: NONE. Installations or Python/PyTorch/CUDA/driver/environment changes: NONE. External anchor update: NONE.

No Git clean/reset/stash/checkout/switch/branch creation/commit/merge/rebase/pull/push/fetch/clone was performed. No existing file was deleted, renamed, moved or overwritten. Authorized filesystem writes were confined to the four new documents under `docs\bot21_research\`. Safety assertions concern this recovery's actions; they do not erase historical exposure uncertainty.

## 12. Freeze disposition and exact next recommended gate

X1, X2 and X3 are complete recovered repository artifacts with verified contents and recorded hashes. X4 remains the original frozen artifact. The original incomplete record is preserved. Scientific disagreements remain unresolved.

Exact next recommended gate: **separately authorized second red-team batch X5–X8 against the frozen evidence package**. Await the user's next authorization. Do not start X5–X8 now, an R20 response, R1, implementation, training, inference, tests, backtests or trading.

The coordinator will verify V2's complete readback, calculate its SHA-256 after writing, and perform a final identity/status comparison before the handoff. The V2 digest is returned outside this document.

## Appendix A. Existing research byte identities

All entries below matched the recovery baseline at the post-X3/pre-V2 check. They identify preserved bytes, not approval of underlying scientific claims or data.

| Existing document | Baseline and verified SHA-256 |
|---|---|
| BOT21_ARCHITECTURE_COMPARISON_MATRIX.md | A3E3D6FA81462BC4FFA5D1B0F3BE5BB6C958E637753A78B7611DF2A838A5B2DF |
| BOT21_FAKE_ALPHA_DEFENSE_MAP.md | 6545B341384AE1849E7B50AD0018A2DCDA9F65CA1BC3A6BCBAC4EE09C8C31BB1 |
| BOT21_PROVISIONAL_PROTOTYPE_SHORTLIST.md | C23CC4C776A4A60371AE88E1CE63A6937720E5BA26646A04715CE7A97D874323 |
| BOT21_R0_MASTER_RESEARCH_REPORT.md | 8DD681900F02388C0CCA2FA4ECC3C961E5FBF11F787B3D84BC2FC3AB66D6ADAB |
| BOT21_R0B_BATCH1_FREEZE_RECORD.md | 478EC103410E0DE38E6FEEEEB5AC5FEAA3E902C8C3057D92CF3A700D4EF763C6 |
| BOT21_R0B_BATCH2_FREEZE_RECORD.md | C90B3FD3DDD4A22A16A18AAD1321836F5D176D638FEF4351A095BD85AF7A07FB |
| BOT21_R0C_FREEZE_RECORD.md | F3D295541151A251401E6DED7062D655E2E390B58F0B15C40B87083E097D9553 |
| BOT21_RESEARCH_DISAGREEMENT_MATRIX.md | C3C3D3A6A9938579309C5583FF385D121AFBE397DFDAEF533183D75FDD5ACF2E |
| BOT21_RESEARCH_SOURCE_REGISTRY.md | E166354A18D1B503DB70938E0780608FD215EDEE57120CECCE0F72EEF7989B67 |
| BOT21_X1_X4_FREEZE_RECORD.md | 3F87610B25B17075A78E45A3EB698487BD344E7F96087A652177ACF3DD99127A |
| R01_NEURAL_ARCHITECTURES.md | D54719AB05F0E43F3BF66DC0CDA10809BA7EBFDB33CBDBBC11E1014D86B87721 |
| R02_2025_2026_FRONTIER.md | 0E7AFF96113DBD10F5EE540104BFA36D4897A96150F708658C9BBEA2D1E4C691 |
| R03_FINANCIAL_ML.md | EA903271702FC666D507A7A383042A60D76D8002B92A7D94BD50E9A1CC107421 |
| R04_ES_NQ_MICROSTRUCTURE.md | 32842EB4A22BA8B4D88C2AE8EB141041F48C04B95E0EC5C8590D253F51FE6E47 |
| R05_MARKET_REPRESENTATION.md | 9EED9426070E9F374E0754742A43C71591AC375BC10D16E23376DFFBB423C919 |
| R06_MULTI_TIMEFRAME.md | 3EC4703C07D3887CCE55D340241DA42499BEEE51A18ED8FC1521CB9BD9E63325 |
| R07_TARGETS.md | 3C97EF4EAD741E6BF41BB57CDE34093AC645083BEB8AA241D2411372A40A2DCF |
| R08_REGIMES.md | EC25739C877895FDD96CD247ABC2F678727AA6BC13A0C099798004B5FAE6A6DE |
| R09_UNCERTAINTY.md | A9CA1C3F6C1AE7439760C49A8F9408F62852C05E5FEBE19B01848E7426518972 |
| R10_VALIDATION.md | 84B50653796003218A3C8B27569C7079C7F779FEE719198C6258BD9AD0E68FFA |
| R11_LEAKAGE.md | 0D350D044356BCA49DCFE14D9DEA6E686FADBF9E791BD8B5ABC6FF4B20FED5F4 |
| R12_LOSS_OPTIMIZATION.md | B3B9469F0FB55694A8B3FAAB86B0B2D098BA451EDD17C24719347400D20E303E |
| R13_NONSTATIONARITY.md | 955E576244E4947F1C790298F912C96740327A925B57BB0EF5F674E34562DE6A |
| R13_PRE_RECOVERY_COORDINATOR_DRAFT.md | 1D3256DCC39E391648A0C1C2AD63771E26619722A012485D458F7C34E44303DE |
| R14_ENSEMBLES.md | A77B7B38BBD4716E9DA061885280C15CF2674852005AF1A19780627988ADC22C |
| R14_PRE_RECOVERY_COORDINATOR_DRAFT.md | 5CE0C44827258324696A5B581055FEE47A902D46660FA1E03E149197069A2A9B |
| R15_GPU_ML_SYSTEMS.md | C02A624A29E1B6BB3C98FCC24A7DC7DB48B57F2700578D6E343C381E7B118D9A |
| R15_PRE_RECOVERY_COORDINATOR_DRAFT.md | C54EB1E676B401014006D2F360FB4DA49ADD3CB19E923AA0C859E74B508A976D |
| R16_PRE_BATCH2_COORDINATOR_DRAFT.md | CD82844DA9729BD7BD7EE76ABC4F497F335D6874C9FAECCEEC24E8E58F3C4B78 |
| R16_SESSION_SYNCHRONIZATION.md | 8CA2503D197A25FE9752029D94EF41F45EDC89E290753750C08CC7F0C6EC0A3E |
| R17_DECISION_ARCHITECTURE.md | CF1B2BA158DBE74436D2389EC6926B58C22EBDA3F0312D9E43CDE3810870B01F |
| R17_PRE_BATCH2_COORDINATOR_DRAFT.md | 6CA7D46F7BD825E719D86F0AF9544D8F9F7A6A3CB3C6D82CB7159089F34492A9 |
| R18_ADVERSARIAL_REVIEW.md | C3B1FF9103E1670A06D1E4B0E114C35EF3C3ACA33A1BE6421FA4AECC3F39DCC6 |
| R18_PRE_BATCH2_COORDINATOR_DRAFT.md | DFB21BB74173437A1754546659C2991568BA22F5E7B34FF6D1F5C50430732A1D |
| R19_BOT20_PRESERVATION.md | 4A259DCC761FF976D0799CC2041A0925AF85CDF9B3FB491A2D62A360B67895EC |
| R19_PRE_BATCH2_COORDINATOR_DRAFT.md | E702BC49C9AE455BC4F344990DBD98F77F6ACCAC65C34A1A6528C30223B73702 |
| R20_COORDINATOR_SYNTHESIS.md | A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE |
| X4_STATISTICAL_DATAMINING_ATTACK.md | CA315086345B22E0839A548D488764D817237E7DE26E6B48C249F0D4142F45D4 |

## Appendix B. Baseline Git status preserved

These are filename/status metadata from the read-only baseline; file contents were not inspected. Final comparison must preserve every line and add only X1, X2, X3 and V2.

```text
 M bot2/neural/model.py
 M bot2/phase5c_v3/calibration.py
 M bot2/phase5c_v3/data_integrity.py
 M bot2/phase5c_v3/experiment_matrix.py
 M bot2/phase5c_v3/experiment_runner.py
 M bot2/phase5c_v3/model.py
 M bot2/phase5c_v3/test_experiment_matrix.py
 M bot2/phase5c_v3/test_experiment_runner.py
?? bot2/phase5c_v3/authorization.py
?? bot2/phase5c_v3/no_score_boundary.py
?? bot2/phase5c_v3/protected_preflight.py
?? bot2/phase5c_v3/test_authorization.py
?? bot2/phase5c_v3/test_no_score_boundary.py
?? config/BOT2_PHASE5C_S4_SOURCE_CLASSIFICATION.json
?? config/BOT2_PHASE5C_S4_SOURCE_CLASSIFICATION.json.sha256
?? config/bot2_phase5c_v4_protocol_proposal.json
?? config/bot2_phase5c_v4_protocol_proposal.json.sha256
?? docs/BOT2_CURRENT_STATE_MASTER_AUDIT.md
?? docs/BOT2_PHASE5C_PROTOCOL_V4_COORDINATOR_RECONCILIATION.md
?? docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md
?? docs/BOT2_PHASE5C_PROTOCOL_V4_PROPOSAL.md.sha256
?? docs/BOT2_PHASE5C_S4_AGENT_LINEAGE.md
?? docs/BOT2_PHASE5C_S4_AGENT_LINEAGE.md.sha256
?? docs/BOT2_PHASE5C_S4_DOCUMENT_DERIVATION_GRAPH.md
?? docs/BOT2_PHASE5C_S4_DOCUMENT_DERIVATION_GRAPH.md.sha256
?? docs/BOT2_PHASE5C_S4_FORENSIC_RED_TEAM.md
?? docs/BOT2_PHASE5C_S4_FORENSIC_RED_TEAM.md.sha256
?? docs/BOT2_PHASE5C_S4_INCIDENT_TIMELINE.md
?? docs/BOT2_PHASE5C_S4_INCIDENT_TIMELINE.md.sha256
?? docs/BOT2_PHASE5C_S4_SOURCE_RECOVERY.md
?? docs/BOT2_PHASE5C_S4_SOURCE_RECOVERY.md.sha256
?? docs/BOT2_PHASE5C_V4_INDEPENDENT_SCIENTIFIC_REVIEW.md
?? docs/BOT2_PHASE5C_V5_CLEAN_SOURCE_ALLOWLIST.md
?? docs/BOT2_PHASE5C_V5_CLEAN_SOURCE_ALLOWLIST.md.sha256
?? docs/BOT2_PHASE5C_V5_CONTAMINATION_BOUNDARY.md
?? docs/BOT2_PHASE5C_V5_CONTAMINATION_BOUNDARY.md.sha256
?? docs/BOT2_PHASE5C_V5_COORDINATOR_RECONCILIATION.md
?? docs/BOT2_PHASE5C_V5_COORDINATOR_RECONCILIATION.md.sha256
?? docs/BOT2_PHASE5C_Y_INDEPENDENT_RUNNER_REVIEW.md
?? docs/BOT2_PHASE5C_Z_A0_ABSTENTION_PROTOCOL_REVIEW.md
?? docs/BOT2_PHASE5C_Z_A0_TIE_BREAK_REMEDIATION_SPEC_V1.md
?? docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_COORDINATOR_REVIEW.md
?? docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1.md
?? docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1.md.sha256
?? docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V1_INDEPENDENT_REVIEW.md
?? docs/BOT2_PHASE5C_Z_PROTOCOL_CLARIFICATION_V2_COORDINATOR_REVIEW.md
?? docs/BOT2_PHASE5C_Z_REVIEW_BLOCKER_REMEDIATION.md
?? docs/bot21_research/BOT21_ARCHITECTURE_COMPARISON_MATRIX.md
?? docs/bot21_research/BOT21_FAKE_ALPHA_DEFENSE_MAP.md
?? docs/bot21_research/BOT21_PROVISIONAL_PROTOTYPE_SHORTLIST.md
?? docs/bot21_research/BOT21_R0B_BATCH1_FREEZE_RECORD.md
?? docs/bot21_research/BOT21_R0B_BATCH2_FREEZE_RECORD.md
?? docs/bot21_research/BOT21_R0C_FREEZE_RECORD.md
?? docs/bot21_research/BOT21_R0_MASTER_RESEARCH_REPORT.md
?? docs/bot21_research/BOT21_RESEARCH_DISAGREEMENT_MATRIX.md
?? docs/bot21_research/BOT21_RESEARCH_SOURCE_REGISTRY.md
?? docs/bot21_research/BOT21_X1_X4_FREEZE_RECORD.md
?? docs/bot21_research/R01_NEURAL_ARCHITECTURES.md
?? docs/bot21_research/R02_2025_2026_FRONTIER.md
?? docs/bot21_research/R03_FINANCIAL_ML.md
?? docs/bot21_research/R04_ES_NQ_MICROSTRUCTURE.md
?? docs/bot21_research/R05_MARKET_REPRESENTATION.md
?? docs/bot21_research/R06_MULTI_TIMEFRAME.md
?? docs/bot21_research/R07_TARGETS.md
?? docs/bot21_research/R08_REGIMES.md
?? docs/bot21_research/R09_UNCERTAINTY.md
?? docs/bot21_research/R10_VALIDATION.md
?? docs/bot21_research/R11_LEAKAGE.md
?? docs/bot21_research/R12_LOSS_OPTIMIZATION.md
?? docs/bot21_research/R13_NONSTATIONARITY.md
?? docs/bot21_research/R13_PRE_RECOVERY_COORDINATOR_DRAFT.md
?? docs/bot21_research/R14_ENSEMBLES.md
?? docs/bot21_research/R14_PRE_RECOVERY_COORDINATOR_DRAFT.md
?? docs/bot21_research/R15_GPU_ML_SYSTEMS.md
?? docs/bot21_research/R15_PRE_RECOVERY_COORDINATOR_DRAFT.md
?? docs/bot21_research/R16_PRE_BATCH2_COORDINATOR_DRAFT.md
?? docs/bot21_research/R16_SESSION_SYNCHRONIZATION.md
?? docs/bot21_research/R17_DECISION_ARCHITECTURE.md
?? docs/bot21_research/R17_PRE_BATCH2_COORDINATOR_DRAFT.md
?? docs/bot21_research/R18_ADVERSARIAL_REVIEW.md
?? docs/bot21_research/R18_PRE_BATCH2_COORDINATOR_DRAFT.md
?? docs/bot21_research/R19_BOT20_PRESERVATION.md
?? docs/bot21_research/R19_PRE_BATCH2_COORDINATOR_DRAFT.md
?? docs/bot21_research/R20_COORDINATOR_SYNTHESIS.md
?? docs/bot21_research/X4_STATISTICAL_DATAMINING_ATTACK.md
```

END OF BOT21_X1_X4_FREEZE_RECORD_V2 — RECOVERY EVIDENCE FROZEN
