# R16 — Session / Synchronization Science

Role: fresh independent R16 specialist (`/root/batch2_r16`).
Status: COMPLETE — independent first pass frozen on 2026-09-24.
Research cutoff/access date: 2026-09-24; current official 2026 materials checked. This is not an exhaustive survey of every 2026 publication.
Source count: 12 public primary sources, plus 1 local audit context source (13 total, R16-S01–R16-S13).
Scope: evidence requirements for a future temporal contract; no final temporal contract, chosen synchronization tolerance, executable specification, architecture synthesis, or implementation.

## Principal finding and evidence limits

Equal timestamps do not prove equal information availability. Session identity, aggregation interval, exchange event time, vendor receipt time, application receipt time, and decision availability are different objects. A model may be temporally causal in a cleaned event-time archive and still use information unavailable to a real receiver. This is a methodological inference, supported by the different clock semantics documented by CME and Databento [R16-S05–S07].

The permitted audit reports first-observed-row session-open semantics, exact and nearest-skew synchronization paths, normalized one-minute data, and absent historical receipt-time evidence. These are audit-reported concerns, not freshly inspected source or dataset findings [R16-S13]. This review did not inspect archives or establish what their actual timestamp columns contain.

A particularly consequential provider fact: Databento OHLCV labels the interval start; its documented aggregation basis is trade receipt time, and no bar is emitted when there is no trade. Its daily bars follow UTC dates [R16-S06]. Therefore neither a missing bar nor a field named `ts_event` can be interpreted from its name alone. Future investigation must identify whether the archive uses this schema, another historical version, or custom resampling. The provider documentation is not proof of archive lineage.

## Market-calendar evidence

Current ES and NQ product overviews specify the normal Globex envelope as Sunday 17:00 through Friday 16:00 Chicago time, with a daily 16:00–17:00 maintenance interval [R16-S02–S03]. This normal envelope is not a complete dated session calendar. CME's holiday page separates platforms and supplies 2026 product schedules; it warns that holiday schedules can change and are usually finalized near the holiday [R16-S01]. Do not substitute ClearPort, trading-floor, options, BTIC, TACO, or another exchange's hours for outright ES/NQ futures.

RTH and ETH require explicit semantic labels. A cash-equity reference window, an exchange futures trading session, a vendor's chart template, and an overnight subset are not interchangeable. A research feature may use a cash-open reference, but must identify that reference and its dated calendar independently of the Globex session. ETH can mean all electronic hours or only the complement of a selected RTH window; the acronym alone establishes neither.

Historical official CME notices themselves demonstrate changing hours: the 2012 notice describes a 15:15–15:30 halt and a different close [R16-S11]. These must not be copied into a universal 2026 template. This report has not independently reconstructed every historical halt schedule. A dated calendar/status evidence package remains required, including unplanned halts, reopening phases, and instrument-specific termination.

CME's 2026 roll table gives June expiration as June 18, not a mechanically generated third Friday [R16-S04]. Its Juneteenth notice separately addresses settlement publication [R16-S12]. Settlement, expiry, cash close, maintenance, and session close must remain separate concepts.

## Explicit answers to the twelve required questions

### 1. What does session open need to mean scientifically?

It needs to identify a scheduled boundary of a named market session, for a named venue/product and trading date, under a dated calendar authority. Distinguish scheduled trading start, actual transition to tradable status, first exchange trade, first vendor-observed event, and first locally received event. Pre-open order entry is not necessarily continuous matching. A feature reference such as cash open must be named separately. Which of these a feature needs is part of its scientific definition; silently using the first available row conflates market time with sampling coverage.

### 2. Should session-relative features depend on first observed data?

Calendar-relative elapsed time should not. Removing the first five bars should not redefine official session age. A separately named observation-relative feature may intentionally measure time since first observed event, but must carry its sampling/coverage meaning. Price-relative features need a further distinction: the true session opening price is unavailable if the opening trade/bar is missing; the first available price is a different reference. Relabeling it as session open would change the estimand. An elapsed clock can be wall-clock time or accumulated tradable time excluding breaks; either requires an explicit, separately reviewed definition.

### 3. How should missing opening observations be represented?

Retain the calendar boundary and mark opening coverage absent or uncertain. Required evidence includes first-observed timestamp, delay from scheduled open, expected versus observed opening intervals, cause if known, and validity of open-dependent values. Distinguish no trades, scheduled closure, trading halt, feed loss, ingestion gap, and unknown cause. Absence of an OHLCV row does not alone distinguish these states [R16-S06]. Opening-price returns and opening-range quantities should be unavailable or explicitly partial until their required information is present. Do not fabricate opening prices from later data. Any partial-session inclusion rule is a later research decision requiring bias assessment.

### 4. What should define trading-day/session identity?

Use exchange trading-date semantics plus venue, product/contract, session kind, and calendar version/effective date; preserve the source-provided trade date where available and reconcile disagreements. UTC date, file name, local date, and first-observed date are insufficient. The evening part of a session can belong to the next trading day. Session segments and status transitions need identities within that day, so a break does not accidentally start an unrelated sample or erase the day's identity. Vendor daily aggregate identity requires independent reconciliation.

### 5. How should DST/holiday/early-close behavior be represented?

Retain UTC instants and a named civil timezone such as America/Chicago with a pinned timezone database version; retain exchange-local labels for audit. Never assume CT means permanent UTC-6, and never derive exchange time from the user's Arizona clock. IANA maintains historical offset and DST rules [R16-S08]. A dated product calendar must represent openings, closings, breaks, special phases, exceptions and provenance. DST affects UTC conversions; holiday changes affect market schedules independently. Future evidence must cover spring/fall transitions, ambiguous/nonexistent local times, early closes, and multi-day holiday gaps. Do not assume a fixed row count per session or infer a holiday merely from missing rows.

### 6. How should futures contract rolls be represented?

Keep underlying root and actual listed contract/security identity, expiration, mapping effective interval, old/new contract, selection rule/version, and roll decision's information cutoff. Expiration is an exchange event; a continuous-series roll is a chosen transformation. CME's customary lead-month transition is useful reference evidence, not a requirement that all participants roll then [R16-S04]. Calendar-based and liquidity-based selection are different hypotheses. Same-day final volume used to choose that day's contract leaks future information; lagged observable liquidity or an announced calendar rule needs separate justification. Preserve unadjusted prices and identify any adjustment vintage/method. A roll gap is not an ordinary market return. Context windows, normalization, cross-contract targets and ES/NQ month pairing all require explicit boundary treatment before dataset approval; this report selects none.

### 7. Under what conditions is exact ES/NQ synchronization justified?

Exact joining is scientifically defensible for comparable completed intervals on the same defined clock/grid, with verified interval endpoints, timestamp meanings, calendar/session identities, contract mapping and revision semantics. Both inputs must also have been available by the stated decision cutoff. Equal bar-open labels alone are inadequate: the high, low, close and total volume require interval completion. Raw event streams need not have matching event instants; exact raw-event equality can discard almost everything or select a peculiar subset. Even an exact bar inner join can condition the sample on both markets having observations; missingness/coverage selection must be measured before claiming generalization.

### 8. Under what conditions could nearest/max-skew synchronization be scientifically defensible?

For a deliberately defined asynchronous state estimate, backward/as-of selection among already available observations can be defensible if age, tolerance, tie-breaking, repeated use and calendar/contract boundaries are visible and justified against the forecast horizon and measured feed behavior. Symmetric nearest matching may be appropriate for retrospective measurement of co-movement, but does not by itself support online prediction. It can be causal at a later decision cutoff only if every selected observation was available then and the target starts after that cutoff. Tolerance should be an independently justified scientific parameter with uncertainty and sensitivity analysis, not selected on protected performance. No numeric tolerance is recommended here.

### 9. When would nearest matching introduce lookahead or stale-information risk?

Lookahead occurs when the closest observation lies after the information cutoff, when an earlier event arrives late, when a start-labelled completed bar is exposed at its start, or when revised historical values replace the original contemporaneous view. Staleness occurs when old observations are reused without age/validity metadata, especially across breaks, halts, missing intervals, sessions or rolls. A max event-time skew does not bound receipt delay. Illustrative reasoning: at decision time 10:00:00, an NQ observation stamped 10:00:00.020 cannot be included merely because it is closer than the last available one. Conversely an event stamped 09:59:59.990 but received at 10:00:00.030 is also unavailable. These are hypothetical counterexamples, not executed experiments.

Forward filling must identify carried state. Carrying a last quote for a bounded stale-state hypothesis differs from inventing a traded bar, volume, or return. Repeated filled prices can suppress volatility and manufacture apparent lead/lag. Even a causal fill can create statistically misleading data.

### 10. Should BOT 2.1 have one canonical synchronization contract?

Yes, in the limited sense of one versioned semantic authority governing each dataset/model identity, so training, validation, replay and future observation paths cannot silently disagree. This does not imply one universal join algorithm for all data resolutions. Explicitly distinct research modes may coexist only with distinct identities and validated meanings; switching from exact to nearest cannot be an invisible fallback. This is a governance/evidence requirement, not the final contract or a selection of either algorithm.

### 11. What metadata must accompany every synchronized observation?

At minimum the evidence must permit reconstruction of:

- Dataset/provider/schema versions and lineage; original instrument/security IDs and contract mapping vintage.
- Exchange trading date, session and segment identity, calendar/version, timezone/version, status and relevant roll state.
- Each leg's original timestamp and clock meaning; interval start/end and inclusion convention for bars; available exchange event/send, vendor receipt, application receipt, and processing/decision timestamps. Unavailable fields must be explicitly unknown.
- Bar completeness/publication/revision state; sequence/gap/duplicate flags; source observation identity and correction lineage.
- Match method/version, signed skew, per-leg age at decision, tolerance reference, missingness, stale/reuse/fill flags, and acceptance/rejection reason.
- Forecast origin and information cutoff, with label horizon clock separately defined. Elapsed minutes, tradable minutes and number of observed rows are not synonymous.

This is a conceptual metadata inventory. It does not mandate a schema or authorize adapters. Timestamp precision must not be misrepresented as clock accuracy; cross-clock offset uncertainty and synchronization status are necessary where meaningful [R16-S05–S07].

### 12. What timing assumptions must be tested before neural training?

The following are proposed future evidence requirements, not tests performed or authorized in this session:

| Evidence obligation | Failure it must expose |
|---|---|
| Calendar reconciliation against dated CME product schedules/status records, including 2026 holidays and June expiry | Fixed weekday rules, wrong product/platform, missing special closes |
| UTC/local round-trip and session assignment examples at DST and year boundaries | Offset drift, duplicated local times, wrong trading day |
| Missing-opening and truncated-session cases with unchanged calendar origin | Features re-zeroing at first surviving row |
| Vendor schema/version and bar construction/publication provenance | Start labels treated as closes, UTC days treated as sessions |
| Independent clocks and actual availability reconstruction or explicitly bounded uncertainty | Event-time causality falsely claimed as receiver-time causality |
| Prefix invariance: later arrivals/corrections must not change earlier purported decisions without a revision record | Hidden future data and retrospective corrections |
| Exact/as-of/nearest boundary examples including ties, gaps, duplicates and disordered arrivals | Future matches, stale reuse, sequence-dependent joins |
| Missingness/coverage accounting by session, contract and volatility regime using permitted data | Selection bias from retaining only jointly observed bars |
| Roll-boundary and continuous-series vintage review | Future volume selection, artificial returns and retroactive adjustments |
| Causal availability and horizon accounting for every input/target interval | Labels beginning before all inputs could have been known |
| Sensitivity to plausible clock error, latency, bar phase and stale thresholds | Apparent lead/lag caused by acquisition rather than markets |
| Independent reproduction of semantics across historical and prospective paths | Research/deployment clock mismatch |

A failing or unknown prerequisite must limit the claim made. Historical OHLCV without publication/application-receipt evidence can support a conditional bar-level hypothesis; it cannot alone certify a deployable latency-sensitive edge. Any later validation must use separately authorized nonprotected material.

## Asynchrony, clocks and inferential uncertainty

Hayashi–Yoshida addresses covariance estimation from nonsynchronous observations without requiring naive regular-grid synchronization [R16-S09]. It demonstrates that sampling design belongs in inference, not that a particular ES/NQ neural input or fill policy is validated. Hoffmann–Rosenbaum–Yoshida studies lead/lag estimation with non-synchronous sampling [R16-S10]. Such retrospective estimators must not be turned into permission to shift a future stream into past features.

Economic lead/lag, timestamping location, channel delay, clock offset and bar-construction phase are competing explanations. A measured lead can reverse after changing the observation clock. No source reviewed establishes a stable tradable ES-leading-NQ or NQ-leading-ES edge for this repository. Timestamp resolution, provider clock quality and local clock discipline are separate; neither PTP/NTP configuration nor nanosecond encoding proves historical accuracy. Future provenance should document clock source, monitoring, uncertainty bounds, outages and local monotonic-versus-wall-clock use. No clock was inspected or changed here.

Largest uncertainty: the actual archived bar lineage and contemporaneous availability information are unverified. Public documents cannot resolve whether the repository can reconstruct a defensible decision-time information set. Exact matching is insufficient to resolve that uncertainty, and nearest matching cannot repair missing provenance.

## Sources

All URLs below were searched/opened on 2026-09-24. Living documentation years are reported as undated/current rather than fabricated publication years. Citations identify source facts; the twelve answers and proposed evidence gates are the specialist's reasoning, not claims that CME prescribes a neural design.

### R16-S01
- Title: CME Group Holiday and Trading Hours.
- Organization/year/venue: CME Group; living page with 2026 schedules; CME official website.
- URL: https://www.cmegroup.com/trading-hours.html
- Type/review: exchange primary operational documentation; not academic peer review.
- Finding: dated platform/product holiday schedules differ from normal hours and can change.
- Limitation: dynamic tables; this review did not extract and verify every ES/NQ daily exception.
- Relevance: authoritative starting point for dated session evidence, not generic weekday arithmetic.

### R16-S02
- Title: E-mini S&P 500 Futures Overview.
- Organization/year/venue: CME Group; current 2026 view; CME product website.
- URL: https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.timeAndSales.html?videoId=6400720213112
- Type/review: official product documentation; not peer reviewed.
- Finding: ES normal Globex hours and maintenance window are explicitly separated from other trading facilities.
- Limitation: overview is not a complete historical exception calendar.
- Relevance: normal ES session envelope.

### R16-S03
- Title: E-mini Nasdaq-100 Futures Overview.
- Organization/year/venue: CME Group; current September 2026 view; CME product website.
- URL: https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.timeAndSales.html?videoId=6396076863112
- Type/review: official product documentation; not peer reviewed.
- Finding: NQ normal Globex hours include the daily maintenance break.
- Limitation: product overview does not prove every historical halt/holiday boundary.
- Relevance: independent NQ product confirmation instead of assuming all ES rules transfer.

### R16-S04
- Title: Equity Index Roll Dates.
- Organization/year/venue: CME Group; living page with 2025–2028 table; CME website.
- URL: https://www.cmegroup.com/trading/equity-index/rolldates.html
- Type/review: exchange primary reference; not peer reviewed.
- Finding: customary roll and expiration are distinct; 2026 June dates are June 15 and June 18.
- Limitation: customary lead month does not specify an individual research continuous-series method.
- Relevance: contract identity and exception-aware roll provenance.

### R16-S05
- Title: Common fields, enums and types.
- Organization/year/venue: Databento; undated living documentation current at access; Databento Docs.
- URL: https://databento.com/docs/standards-and-conventions/common-fields-enums-types
- Type/review: provider primary technical documentation; not peer reviewed.
- Finding: event, send and receive timestamps have different semantics; publisher clock differences can remain in data.
- Limitation: documentation does not establish the actual archive or local application latency.
- Relevance: timestamp meanings and clock uncertainty must survive normalization.

### R16-S06
- Title: Aggregate bars (OHLCV).
- Organization/year/venue: Databento; undated living documentation current at access; Databento Docs.
- URL: https://databento.com/docs/schemas-and-data-formats/ohlcv
- Type/review: provider primary schema documentation; not peer reviewed.
- Finding: start labels, receipt-time interval basis, no record for no trades, and UTC daily aggregation.
- Limitation: archive schema version/custom transformations unverified; publication timing is not guaranteed by the label.
- Relevance: bar availability, missingness and session identity cannot be inferred from timestamp names.

### R16-S07
- Title: MDP 3.0 - Trade Summary.
- Organization/year/venue: CME Group; undated living documentation; CME Client Systems Wiki.
- URL: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457418925
- Type/review: official technical documentation; not peer reviewed.
- Finding: TransactTime denotes event-processing start in epoch nanoseconds; messages identify instruments and update actions.
- Limitation: field semantics do not prove synchronized gateway clocks or subscriber availability.
- Relevance: exchange event time and subsequent receipt/correction history are distinct evidence.

### R16-S08
- Title: Time Zones.
- Organization/year/venue: IANA; living page, 2026d release displayed at access; IANA.
- URL: https://www.iana.org/time-zones
- Type/review: official technical database documentation; not academic peer review.
- Finding: timezone data encode historical local offsets and DST rules and are updated.
- Limitation: civil timezone rules do not supply exchange schedules.
- Relevance: pin timezone provenance separately from market calendar provenance.

### R16-S09
- Title: On covariance estimation of non-synchronously observed diffusion processes.
- Authors/year/venue: Takaki Hayashi and Nakahiro Yoshida; 2005; Bernoulli 11(2), 359–379.
- URL: https://www.ms.u-tokyo.ac.jp/~nakahiro/mypapers_for_personal_use/hayyos03.pdf
- Type/review: original journal research, author-hosted paper; peer reviewed.
- Finding: covariance can be estimated while accounting for nonsynchronous observation intervals.
- Limitation: model assumptions and covariance objective do not validate neural prediction, real latency, or a specific ES/NQ join.
- Relevance: principled warning against treating synchronization as an innocuous preprocessing detail.

### R16-S10
- Title: Estimation of the lead-lag parameter from non-synchronous data.
- Authors/year/venue: Marc Hoffmann, Mathieu Rosenbaum and Nakahiro Yoshida; 2013; Bernoulli 19, author-listed journal publication; arXiv:1303.4871 author manuscript.
- URLs: https://arxiv.org/abs/1303.4871 ; https://www.ceremade.dauphine.fr/~hoffmann/static3/research
- Type/review: original statistical research; journal publication peer reviewed, arXiv copy itself not a separate review.
- Finding: lead/lag estimation accounts for nonsynchronous sampling and sampling sparsity.
- Limitation: theoretical inference does not establish a usable ES/NQ trading edge or permit future shifting in inputs.
- Relevance: distinguish acquisition artifacts and retrospective estimation from causal forecasting.

### R16-S11
- Title: Equity Index Later Close for CME Globex Trading Day, Daily Price Limits; Advisory 12-423.
- Organization/year/venue: CME Clearing; 2012, notice October 1 effective November 18; CME advisory archive.
- URL: https://www.cmegroup.com/tools-information/lookups/advisories/clearing/Chadv12-423.html
- Type/review: historical exchange primary notice; not peer reviewed.
- Finding: historical hours, halts and trade-date transition were changed explicitly.
- Limitation: historical, not authority for present hours.
- Relevance: reject timeless session templates and record effective dates.

### R16-S12
- Title: Juneteenth Holiday 6/19/2026 Settlement Times.
- Organization/year/venue: CME Group; 2026; official holiday-calendar PDF.
- URL: https://www.cmegroup.com/tools-information/holiday-calendar/files/2026/juneteenth-day-settlement-times-2026.pdf
- Type/review: exchange primary notice; not peer reviewed.
- Finding: June 19 settlement dissemination exception is explicitly specified.
- Limitation: settlement notice is not the product's full trading-hours schedule.
- Relevance: settlement calendar must not be substituted for tradability or expiry evidence.

### R16-S13
- Title: BOT2_CURRENT_STATE_MASTER_AUDIT.md.
- Organization/year/venue: prior BOT2 audit coordinator; supplied local 2026 audit; repository docs.
- Location: C:/Users/fjone/hyperliquid-trading-bot-phase5c-v3/docs/BOT2_CURRENT_STATE_MASTER_AUDIT.md
- Type/review: permitted local static-audit context; not peer reviewed or independently revalidated here.
- Finding: identifies first-row session origin, dual synchronization concepts and receipt-time uncertainty.
- Limitation: report assertions do not certify actual archives or runtime behavior; tool output was lengthy/truncated, relevant audit sections and handoff were visible.
- Relevance: establishes the bounded questions addressed without inspecting protected data.

## Independence, safety and freeze attestation

I read the full current user request and the permitted audit context. I did not read existing R16 conclusions, old R17–R19, the master synthesis, any newly generated specialist report, or the source registry. No R1–R15 content was needed. The existing R16 was copied without reading its content to R16_PRE_BATCH2_COORDINATOR_DRAFT.md; both source and copy hashed CD82844DA9729BD7BD7EE76ABC4F497F335D6874C9FAECCEEC24E8E58F3C4B78 before replacement.

This specialist wrote only these two authorized research documents under docs/bot21_research. No BOT2 source, datasets, features, labels, manifests, Phase 5C, risk, execution, environments or Git state were changed. No protected output/OOS was accessed; no model inference, training, tests, experiments, backtests, trading, broker connections or installations occurred. Public browsing and document copy/write/hash operations are the only research operations beyond reading the request/audit. These attestations apply to this specialist's actions, not unknowable project history.

Frozen on completion; SHA-256 is returned separately to avoid a self-referential hash. Later critique may challenge these conclusions but should not silently rewrite the frozen report. No R20 or X1–X8 work was performed.