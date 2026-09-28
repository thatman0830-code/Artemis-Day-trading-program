# X3 — TEMPORAL LEAKAGE / CAUSALITY ATTACK

Fresh independent recovery review. Review date: 2026-09-25. Status: complete first-pass adversarial report, awaiting coordinator persistence and hashing. This report neither authorizes R1 nor certifies any dataset.

## 1. Target reviewed

The target is frozen `R20_COORDINATOR_SYNTHESIS.md`, particularly sections 1, 5–6, 8, 12–13, 16–18 and 22–23. Its independently recomputed SHA-256 is:

`A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE`

Supporting material reviewed comprised frozen R06, R07, R10, R11 and R16; relevant extracts of R13 and R19; the temporal portion and gate definitions of the R20 fake-alpha defense map; relevant disagreement-matrix extracts; and source-registry entries needed for citation identity. No predecessor drafts or X conclusions were read.

Evidence categories throughout are DOCUMENTED_INHERITED_PREREQUISITE, DOCUMENTED_SOURCE_FACT, METHODOLOGICAL_INFERENCE, CONTRACT_CLARIFICATION and CONDITIONAL_FUTURE_VIOLATION. None of the hypothetical examples below is a discovered dataset defect.

The central question is whether the future information set can be reconstructed as genuinely knowable at each claimed decision and update time. Architecture choice cannot answer that question.

## 2. Strongest R20 claim

R20's strongest claim is that causal availability, label maturity and independent source authority are prerequisites rather than score-dependent preferences. Its explicit rejection of timestamp equality as proof of availability is correct. Its refusal to declare current archives approved is equally important.

R20 also correctly distinguishes legitimate overlapping past context from leaked outcomes. A sequence beginning before a validation boundary is not automatically contaminated; the relevant questions are what was available, how state was fitted and whether held-out outcome information influenced the predictor.

These positions survive this attack. They make the proposed research conditionally intelligible while keeping execution closed. My strongest objection concerns proving those conditions, not replacing them with a different architecture or a universal numerical embargo.

## 3. Weakest R20 claim

The weakest temporal formulation is the possible fallback to a “finalized-bar hypothesis” with bounded availability uncertainty. That can be legitimate, but only after identifying what is finalized, when that vintage became available and which weaker claim remains.

An end-of-interval timestamp does not establish publication. A fixed delay does not cure a historical revision made substantially later. Conversely, genuinely documented conservative availability can support a slower forecasting question even without local receiver timestamps.

The defense map's F04 wording could be overread as allowing current cleaned history whenever a latency claim is dropped. R20 section 6 is stricter, but the two formulations need a single gate interpretation. Unknown revision provenance must not become acceptable historical information merely through a weaker label.

## 4. BLOCKER objections

**X3-B01 — Unresolved independent scientific-source authority.**  
Classification: DOCUMENTED_INHERITED_PREREQUISITE. R20 section 1 and the reviewed R19 extracts report unresolved S4 exposure/derivation, unsigned custody and no approved scientific-source authority for the inherited Phase 5C material. I did not independently inspect the underlying incident or affected assets. The objection is to beginning R1 through an unresolved inherited boundary, not a claim that every possible future source is contaminated. Closure requires separately approved source and partition authority with bounded derivation/exposure history. Renaming, copying or hashing cannot establish that authority.

**X3-B02 — Unestablished temporal admissibility of the intended information set.**  
Classification: DOCUMENTED_INHERITED_PREREQUISITE. R20 sections 6 and 25 leave historical availability and the future temporal contract unresolved. R16 explicitly does not establish actual archive timestamp lineage. Consequently no documented approval presently supports the proposed decision-time observations. Closure requires evidence adequate to the chosen claim, covering vintages, availability, session/contract identity, inclusion decisions and target/update timing. Complete local latency reconstruction is not universally mandatory; a narrower claim needs an independently defensible narrower contract.

**BLOCKER count: 2.** These are existing gate failures acknowledged by R20, not newly discovered corruption and not ordinary uncertainty about predictive performance.

## 5. MAJOR objections

**X3-M01 — Finalized-history escape clause lacks a precise claim boundary.**  
Classification: CONTRACT_CLARIFICATION. Define permissible vintages and the meaning of bounded uncertainty. A retrospective association study may remain valid while a historical forecasting claim does not. Applicable to any proposed fallback under F04.

**X3-M02 — Eligibility and missingness have their own availability times.**  
Classification: CONTRACT_CLARIFICATION / CONDITIONAL_FUTURE_VIOLATION. R20 tracks excluded origins but does not fully spell out when an origin's inclusion decision becomes knowable. Selecting “complete sessions,” eventual matched bars or eventually uncensored labels can reveal later events even if retained feature values pass timestamp checks.

**X3-M03 — Model eligibility needs artifact completion and activation chronology.**  
Classification: CONTRACT_CLARIFICATION. Mature labels and an earlier selection interval are necessary but insufficient if a checkpoint, calibrator or retrained model is used before it could have been selected and produced. R20 discusses production/state tracking without fully resolving this historical activation boundary.

**X3-M04 — Temporal semantics themselves need knowledge vintages.**  
Classification: CONTRACT_CLARIFICATION. Calendar effective dates, mapping validity and correction policy are not synonymous with when their contents became known. Final schedules may describe historical truth while conveying hindsight if used as prior knowledge.

**X3-M05 — Actual dependencies extend beyond nominal sequence length.**  
Classification: CONTRACT_CLARIFICATION. Warm starts, optimizer memory, seasonal references, imputers, calibration and recurrent state can extend support beyond visible lookback. R20 correctly names several dependencies; the gate needs their transitive closure rather than a checklist of nominal windows.

**X3-M06 — Continuous-series transformations need origin-specific identity or demonstrated invariance.**  
Classification: CONTRACT_CLARIFICATION. Future adjustment factors do not necessarily contaminate every derived feature, but cancellation cannot be assumed. Historical transformation vintage and any claimed invariance must be established for the actual input and target definitions.

**MAJOR count: 6.** These materially affect future validity. They can be resolved through later governance before their affected use; no present implementation violation is alleged.

## 6. MODERATE objections

**X3-D01 — “Same lookback” can hide unequal historical support.** An equal number of rows may represent different elapsed durations, active-market durations or stale repetitions. This affects the interpretation of matched information comparisons even when every value is causal. Record the relevant clocks separately.

**X3-D02 — Retrospective diagnostic truth can be mistaken for an available feature.** Final outage classifications and corrected market-status annotations can legitimately support later quality analysis. They cannot automatically enter historical inputs or determine an online-reproducible acceptance rule.

These concerns are meaningful but not independent reasons to prohibit every research formulation. Both connect to the major requirements above without increasing the BLOCKER or MAJOR counts.

## 7. MINOR objections

**X3-N01 — Ambiguous operational vocabulary.** Terms such as “close,” “complete,” “current,” “open,” “available” and “session” need qualified meanings in the eventual contract. The reports generally recognize this; abbreviated downstream references may lose it.

**X3-I01 — INFORMATIONAL: no source count establishes readiness.** Public documentation can establish how a feed is described. It cannot establish that the repository's archive came from that feed, used that version or retained the requisite metadata.

No additional severity IDs are implied elsewhere in this report. There are two MODERATE objections, one MINOR objection and one INFORMATIONAL observation.

## 8. Evidence supporting objections

The strongest local evidence is R20's own explicit non-certification, reinforced by R11 and R16. F01 and F04–F13 retain source, revision, availability, synchronization, calendar, feature and maturity obligations as open. These documents support withheld approval; they do not prove a particular archive violation.

Public primary documentation supplies concrete counterexamples to timestamp-name reasoning. Databento's OHLCV documentation specifies start-labelled intervals, receipt-time aggregation, omission of intervals without trades and UTC daily aggregation. It also identifies publication and retroactive-break handling as construction differences. These are provider facts, not established BOT lineage. [Databento OHLCV](https://databento.com/docs/schemas-and-data-formats/ohlcv)

The common-fields documentation distinguishes event, publisher-send, provider-receive and provider-send times. It also describes instrument-identifier scope and an index timestamp whose meaning depends on schema. Copying a convenient first timestamp column therefore cannot establish semantic equivalence. [Databento common fields](https://databento.com/docs/standards-and-conventions/common-fields-enums-types)

The following methodological deductions are mine: selection rules require causal support; a selected model cannot be available before its selection completes; and a historical calendar's truth differs from the information available before an unexpected change.

## 9. Evidence against objections

R20 is unusually explicit about its limits. It neither grants dataset authority nor claims that its defenses have been executed. It prohibits invented availability, recognizes exact-join selection, separates session origins, requires causal rolls and preserves mature-label constraints.

Thus this attack does not establish that R20's proposal is internally irreparable. It establishes that implementation cannot substitute convenient interpretations for the conditions already stated.

Several apparent objections also have legitimate narrow resolutions. Historical finalized observations can support an explicitly retrospective estimand. Documented latency bounds can support delayed origins. Causal warmup can carry across a split without leaking labels. Official retrospective calendar truth can support descriptive stratification without being a model input.

The burden is to name the narrower claim and its assumptions before interpreting results. None of those resolutions has been demonstrated here.

## 10. ES/NQ transferability considerations

Shared market hours and correlated economic exposure do not imply shared acquisition clocks, identical feed delays or equivalent missingness. Even equal-labelled bars may aggregate different arrival sets. An apparent ES lead can reflect publication timing rather than earlier economic information.

A hypothetical NQ record can have an earlier event label yet arrive after the ES-anchored decision. A backward event-time join would then be numerically backward but informationally forward. Conversely, waiting for both legs can be causal while changing the origin and reducing the remaining target horizon.

The appropriate transfer claim must distinguish instrument-isolated forecasting, contemporaneous shared information and asynchronous stale-state information. They are not interchangeable representations of one experiment.

No stable ES-leading-NQ or NQ-leading-ES advantage is established by the reviewed sources. This is an UNKNOWN transfer question, not a negative empirical finding.

## 11. Source-authority requirements

Before dataset use, an authorized reviewer must be able to identify provider, venue/publisher, product, actual contract, schema/version, acquisition route, transformation ancestry and allowed partitions. Source authority must address both permission and scientific provenance.

Preserve exposure uncertainty explicitly. A future independent source must be demonstrably independent enough for its intended claim; a vendor name or later acquisition date alone does not settle derivation or researcher exposure.

R20's hash evidence protects the identity of literature reports. It does not validate market observations. Likewise, a manifest identifies an asserted dataset but cannot prove its own custody statements.

X3-B01 closes only through approved evidence, never by opening protected outputs to determine whether the data “looks clean.” This review proposes no inspection of those assets and no repair of inherited manifests.

## 12. Timestamp-authority requirements

Every timestamp used in reasoning needs an identified clock location and semantic role: exchange event, send, capture, publication, application receipt, interval boundary, processing completion or forecast production.

Precision, accuracy and ordering are separate properties. Nanosecond encoding does not establish accuracy. Event order, receive order and corrected historical order can differ. Equal recorded values also require a tie policy where message sequence or computation order matters.

The future contract must preserve undefined timestamps, clock uncertainty and schema-specific meaning rather than filling unknowns with a convenient surrogate. Per-symbol monotonicity does not establish cross-instrument synchronization.

For bars, record interval inclusion conventions separately from the label. Renaming a start field “close_time” without a sourced transformation changes the string, not the underlying information chronology.

## 13. Availability-time requirements

For origin \(t\), all consumed values, fitted parameters, selection decisions and state must be supported by information usable by \(t\). A derived feature's availability cannot precede its latest required input or required computation.

The receiver must be named. Exchange availability, vendor availability and local application availability support different claims. An unavailable local receipt history does not automatically invalidate every slow bar-level question, but it prevents asserting a reconstructed local real-time information set.

Uncertainty must be bounded from evidence rather than a favorable score. If an admissible upper bound is later than the origin, the value is ineligible for that origin. If no defensible bound exists, retain UNKNOWN or narrow the estimand.

A correction vintage that arrived next day is not made contemporaneous by adding a short delay to yesterday's bar. Finalization and receipt uncertainty are distinct issues.

## 14. Synchronization requirements

Freeze the anchor origin, each leg's availability rule, interval semantics, contract pairing and missingness policy before claiming common information.

Exact matching needs causal availability of both legs. It can also restrict the population to jointly observed periods. The resulting claim must either address that selected population or provide justified coverage accounting.

Nearest matching is particularly dangerous because the closest key can be later. Backward matching only constrains its chosen key. Official pandas documentation describes backward matching as selecting a preceding or equal key, and nearest matching by key distance; it does not supply publication or revision semantics. [pandas merge_asof](https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html)

An available-as-of match therefore needs availability-qualified candidates before selection. Age, signed skew, duplicate resolution, reuse, tie handling and boundary crossing remain part of its meaning.

Do not wait retrospectively until a counterpart eventually appears and still label the forecast with the original anchor. That is a changed origin, not successful synchronization.

## 15. Session/calendar requirements

Distinguish scheduled session start, actual tradable start, cash-open reference, first trade, first observed row and opening-price availability. A missing opening row cannot redefine elapsed official session time.

DST conversion and exchange schedules are different authorities. Named timezone data encode civil offsets and their history; they do not define futures sessions. [IANA Time Zones](https://www.iana.org/time-zones)

CME explicitly presents changeable holiday schedules and separate operational phases. A currently correct schedule does not by itself identify what was announced at an earlier forecast origin. [CME trading hours](https://www.cmegroup.com/trading-hours.html)

Calendar truth may classify a past interval for evaluation. Using “minutes until early close” as a feature additionally requires that the close was known then. Unexpected halts need observed status chronology.

A first-observed-session feature is permissible if honestly named and available. It must not silently substitute for official age or an unavailable opening price.

## 16. Contract/roll requirements

Preserve actual listed contract identity and dated symbol mapping. A root symbol is insufficient to establish price continuity or a stable security identity.

CME's roll reference distinguishes customary roll and expiration; its June 2026 U.S. index entries show different dates for those events. That reference does not select a research provider's continuous-contract construction. [CME equity-index roll dates](https://www.cmegroup.com/trading/equity-index/rolldates.html)

Liquidity-based mapping requires contemporaneously available selection inputs. Final daily volume cannot choose the same day's earlier contract without hindsight.

Retroactive adjustments require careful reasoning. A constant additive adjustment might cancel in some within-contract differences, while failing to cancel in levels, percentage returns, thresholds or cross-contract windows. Multiplicative transformations have different invariances. No blanket clean/dirty ruling follows from the word “adjusted.”

Define target treatment across transitions and ES/NQ month pairing. A roll gap must not silently become a predicted market move.

## 17. Target-maturity requirements

Record target support, outcome resolution, publication/revision vintage and earliest usable label time separately. Horizon end is not necessarily label availability.

An origin before TRAIN's cutoff can have an outcome after it. Such a row is not fit-eligible merely because its input timestamp lies inside TRAIN. The same principle governs validation selection, calibrator fitting and drift-trigger evaluation.

For multitask learning, maturity may differ by target. A shorter task does not authorize using an immature longer task. Missing-label masks can themselves reveal future resolution unless their use is confined to the later fitting context.

Barrier/path targets add censoring and tie uncertainty. Excluding eventually unresolved events may condition the population on future paths.

Finally, a delayed input cannot be used to forecast a target segment that has already elapsed. If the origin moves, the target definition and claim must move with it.

## 18. Sequence/lookback requirements

A causal network does not make its input tensor causal. Establish the support of every element before discussing masks, receptive fields or recurrence.

Rolling statistics must use eligible trailing observations and an explicit update order. Current-window normalization can be causal when all window observations are available; globally fitted scale is different. Seasonal averages, imputers and feature selection carry fitted information beyond visible price lookback.

Recurrent, state-space and optimizer warm starts require provenance across sessions, contracts and folds. Resetting state at a boundary is a research choice, not a universal requirement. Continuing state is acceptable only under the declared historical process.

Do not reorder late arrivals into an earlier history unless the claim is explicitly event-time retrospective. Sequence padding, missingness indicators and later-known sequence lengths also require scrutiny.

X3-M05 asks for complete dependency support, not an arbitrarily long exclusion window.

## 19. Purge/embargo requirements

R20 correctly rejects a universal lookback-plus-horizon row count. Purging follows overlapping outcome information and fit-time maturity; additional gaps follow the actual dependence and update structure.

A chronological date split alone does not remove labels that mature afterward. Conversely, shared legitimate past observations are not automatically prohibited merely because windows overlap.

The closure must include transformed features, repeated stale observations, revised records, inherited state and model-selection inputs. Extending an embargo cannot repair unavailable inputs, retrospective rolls or exposed source authority.

Strictly forward fitting has no later training rows to embargo after the evaluated block. It can still require boundary exclusions for label maturity and artifact readiness.

No numerical purge, tolerance or embargo is selected here. Choosing one without actual admissible dependency evidence would substitute arithmetic for the unresolved contract.

## 20. Multi-timeframe causality requirements

A completed coarse interval requires more than its printed endpoint. Its underlying observations and the selected aggregate vintage must be available at the origin.

A five-minute bar labelled by its start cannot provide its final high, low, close and volume at the first minute. Forward-propagating those final fields into earlier fine rows would be a conditional future violation, not an observed BOT defect.

Partial aggregates are a different representation. They need the then-known partial state and elapsed/coverage identity, not a disguised copy of the completed bar.

Session-to-date VWAP and relative-volume measures also depend on opening coverage and contemporaneous denominators. Full-session volume is unavailable during the session.

A coarse branch can lengthen effective historical support, warmup and seasonal dependencies. Its validity cannot be inferred from the finest branch's row count or split alone.

## 21. Preconditions before R1 training

The following are approval conditions, not an experiment plan:

1. Independently approved source, lineage, partition and exposure boundary closes X3-B01.
2. A named scientific claim determines which receiver and availability evidence are necessary.
3. Timestamp and bar semantics are bound to the actual approved source/version.
4. Original/corrected vintages are distinguished, with defensible earliest usable times.
5. Forecast origins and causal inclusion decisions are defined independently of future outcomes.
6. ES/NQ matching, age, reuse, missingness and excluded-origin meanings are explicit.
7. Dated session, calendar, timezone and contract/roll semantics cover the intended domain.
8. Every input, target, transform and retained state has a traced dependency and maturity rule.
9. Training, selection, calibration and evaluation roles have chronological eligibility boundaries.
10. Checkpoint/retraining/calibration completion and activation cannot precede their required information.
11. Purge and any embargo follow those dependencies; arbitrary row gaps do not substitute.
12. Independent review records which claims are approved, narrowed or still UNKNOWN.

The documentation must exist before affected training, with evidence collection separately authorized. This report performs none of that collection.

## 22. Required remediation

First, retain the two inherited blockers visibly. Do not interpret completion of red-team reports as closing dataset authority.

Second, resolve X3-M01 through X3-M06 in a later authorized temporal-admissibility decision record. It should distinguish documented historical facts, explicit assumptions and unavailable facts; identify the supported claim; and connect each prerequisite to acceptable evidence and a responsible independent reviewer.

Third, make origin eligibility and artifact activation first-class chronology alongside feature and label timestamps. This is the most useful refinement beyond repeating “no future bars.”

Finally, preserve the frozen R20 and this review. Remediation belongs in subsequent separately authorized documentation. No source code, dataset, calendar adapter, model, split, numerical tolerance or training procedure is selected by this report.

## 23. Questions that remain unresolved

Which exact source and transformations would future R1 use? What authority can approve them without inherited protected exposure? Are original vintages available, or only current cleaned history? Which timestamp denotes bar publication? What receiver does the intended claim represent?

When is missingness declared, and can that determination be reproduced at the origin? Are eventual complete-session filters contemplated? How are late counterparts, contract mappings and exceptional status changes represented?

When do selected checkpoints and calibrators become usable? Does warm-started state carry information from ineligible periods? Are target clocks elapsed time, tradable time or observed rows?

These are bounded unknowns, not evidence that supporting documents do not exist anywhere. This review did not search protected areas to answer them.

## 24. R1 blockers

The gate-closing ledger is exactly:

- **X3-B01:** unresolved independent source authority.
- **X3-B02:** unestablished temporal admissibility for the proposed information set and claim.

Both are inherited and expressly acknowledged in the reviewed synthesis. Neither is a claim that a neural model will fail.

The six MAJOR items refine how a future admissibility decision must avoid convenient loopholes. They are not six additional current blockers, nor evidence of six implementation bugs.

R1 should not begin on the reviewed documentary state. A separately approved clean source and defensible temporal contract could change that disposition without altering the frozen reports. That future determination lies outside this recovery pass.

## 25. Non-blocking concerns

Architecture capacity, profitability, optimal context, beneficial cross-market interaction and the best forecast target remain outside this review's determination.

It is not inherently invalid to use bars, delayed origins, shared past context, causal state carry, completed multi-resolution inputs or a carefully bounded stale observation. Each requires a matching scientific claim.

Nor must every archive support local latency replay to have research value. Some can support slower or explicitly retrospective questions. What is impermissible is promoting those narrower observations into a contemporaneous forecasting claim without evidence.

Additional public research is unlikely to settle the principal local unknowns. More citations cannot replace approved lineage and origin-specific chronology.

## 26. What R20 got right

R20 correctly refuses inherited Phase 5C authority, distinguishes report integrity from data integrity and leaves protected material closed. It explicitly rejects equal-clock causality, future-nearest matching, first-row session origins, future-volume roll selection and fabricated receipt times.

It also preserves selection/calibration separation, mature labels, original issued forecasts, state tracking and support-derived purging. Its recognition that exact matching can select a biased population is especially valuable.

These are substantive strengths. The attack finds no basis to replace them with a simpler universal join, fixed embargo or architecture-specific safeguard. The most important supporting point is R20's requirement that an UNKNOWN prerequisite keeps its affected gate closed.

## 27. What R20 may be overclaiming

R20 itself is cautious; risk arises when its provisional vocabulary is promoted into operational approval.

“Completed” may be taken to mean published. “Finalized-bar” may hide unavailable revisions. “Exact” may be taken to mean simultaneously observable. “Frozen calendar” may be taken to mean historically known. “Training-only” may omit validation selection or production time. “Same origins” may conceal retrospective eligibility.

The defense map is a valuable inventory, but listing a defense does not establish that its evidence exists. R20 says this; downstream gate decisions must preserve the distinction.

The strongest challenge is therefore to any interpretation that documentary sophistication has already converted an unverified archive into causal research material. The reviewed package explicitly has not accomplished that conversion.

## 28. Final adversarial assessment

**Disposition: R1 remains closed under this review. BLOCKER count: 2. MAJOR count: 6.** Strongest objection: a chronologically ordered, accurately timestamped archive can still fail to represent information knowable at the claimed origins. Most important remediation: independent source approval followed by an availability-and-eligibility contract that includes revisions, selection decisions and artifact activation.

Public-source ledger, accessed 2026-09-25:

| Review source | Registry relationship | Scope and limitation |
|---|---|---|
| Databento OHLCV documentation | Existing R16-S06 / R18-S04 | Rechecked provider bar semantics; not archive lineage. |
| Databento common fields | Existing S109 / R16-S05 | Rechecked distinct clocks and identifiers; not local receipt evidence. |
| CME trading-hours page | Existing S29 / R16-S01 / R18-S09 | Rechecked mutable schedules; no complete historical calendar reconstructed. |
| CME roll-date page | Existing S30 / R16-S04 / R18-S10 | Rechecked roll/expiry distinction; not a continuous-series specification. |
| IANA Time Zones | Existing R16-S08 | Rechecked civil-time authority; not exchange-calendar authority. |
| pandas merge_asof documentation | **NEW: X3-S01** | Official technical documentation; backward/nearest key semantics, not causal certification. |

**New public source count: 1.** X3-S01 URL: https://pandas.pydata.org/docs/reference/api/pandas.merge_asof.html. Title: *pandas.merge_asof*. Organization: pandas project. Type: official living framework documentation; not peer-reviewed empirical evidence. No registry modification was performed.

Independence attestation: I formed this first-pass conclusion without reading X1, X2, X4, any recovered X report, the original X freeze-record conclusions or inaccessible prior X3 conclusions. No other reviewer conclusion informed this report. No subagent was spawned.

Safety attestation: this reviewer performed only authorized documentation reads, a read-only R20 digest calculation and public browsing. No files were written. No source code, datasets, credentials, protected outputs/results or protected OOS were inspected. No training, inference, scoring, benchmarks, tests, experiments, backtests, trading, broker access, installation, environment change or Git mutation occurred. Assertions concern this reviewer's actions, not unknowable project history.

The coordinator must persist the complete report, verify its contents and calculate its file hash before treating it as frozen repository evidence. This response alone does not satisfy that persistence gate.

END OF X3 TEMPORAL CAUSALITY ATTACK — COMPLETE INDEPENDENT RECOVERY REPORT
