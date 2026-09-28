# X2 — CAPACITY / UNDERFITTING SKEPTIC

## 1. Target reviewed

This is the fresh independent X2 recovery review of frozen `R20_COORDINATOR_SYNTHESIS.md`, identified by coordinator-reconfirmed SHA-256 `A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE`. Review date: 2026-09-25.

Authorized local material read comprised R20, `BOT21_PROVISIONAL_PROTOTYPE_SHORTLIST.md`, frozen R01, R02 and R06, and relevant source-registry content. Public primary sources were consulted independently. No X report, original X freeze-record conclusion, previous inaccessible X conclusion, protected output, protected result or OOS material was read. No source code, dataset or credential was inspected.

The adversarial position is that insufficient capacity or an impoverished representation could generate false negatives. That position is a challenge to be tested, not a presumption that larger models contain profitable information.

This report distinguishes documented evidence, methodological principles, transfer hypotheses, BOT 2.1 design hypotheses and unknowns. It selects no architecture, prototype, target or R1 experiment. Capability classifications express evidential eligibility only; they confer no execution authority.

## 2. Strongest R20 claim

R20 correctly treats architecture ranking as provisional and refuses to infer an ES/NQ winner from unrelated forecasting benchmarks. More importantly, it separates source validity, causal availability, predictive evidence and trading usefulness.

For this review, its strongest safeguard is section 23: insufficient independent evidence does not demonstrate absence of an effect. Its Q2 and Q3 already ask about longer or multiresolution history and cross-market information. R20 explicitly rejects inherited eight-step windows, fixed feature limits and mandatory one-minute cadence.

Accordingly, an accusation that R20 simply mandates a short-window, TCN-only program would be inaccurate. The defensible capacity critique concerns how its provisional ordering and admission conditions could be operationalized later.

## 3. Weakest R20 claim

The weakest claim appears in the companion shortlist: cross-attention and separate encoders require “causal simple cross-market benefit first.”

That condition is scientifically stronger than the evidence supports. Information may be useful through an interaction while showing little additive or marginal benefit. A gate requiring the latter can systematically exclude the former.

A stylized example is a conditional effect whose sign reverses across a causally observable state. Averaging across states can cancel the main effect although the interaction remains predictive. This is a mathematical counterexample to the prerequisite, not evidence that such a structure exists in ES/NQ.

The TCN-first priority is also weak as a comparative scientific claim. R20 appropriately admits this. Inspectability and computational convenience do not establish that a compact TCN is a sensitive detector of every relevant dependency.

## 4. BLOCKER objections

**Newly established X2 BLOCKER objections: 0.**

No capacity-specific finding demonstrates that otherwise properly authorized, narrowly scoped research cannot begin. Ordinary uncertainty about architecture adequacy is not a gate-closing defect.

This does not open R1. R20 already records unresolved source authority and requires a defensible temporal contract, chronological selection governance and effective isolation. This review did not independently investigate their present satisfaction and does not reclassify them as newly discovered X2 blockers.

An eventual proposal that ignored those prerequisites would remain inadmissible regardless of model capacity. Conversely, resolving them would not prove that a particular representation can detect the hypothesized structure.

## 5. MAJOR objections

**X2-MAJ-01 — Additive-success prerequisites can exclude interaction-only information.**  
The shortlist’s simple-cross-market-benefit gate can reject a capability before a capable model evaluates it. A simple comparator is necessary, but its success is not logically necessary for a richer interaction to exist. This materially affects the validity of cross-market conclusions. Remediation is to distinguish a comparator from an admission prerequisite and preserve tightly bounded interaction hypotheses without demanding a significant marginal effect first.

**X2-MAJ-02 — Negative conclusions need an explicit capability boundary.**  
R20 contains sound caveats, but the program-level question about reproducible information is broader than any small portfolio’s tested function class. A negative result needs to identify representation, available history, target, learning procedure, capacity and detectable effect range. Otherwise an operationally convenient stopping decision can become the scientifically unsupported conclusion that no signal exists. This is a limitation of inference, not a demand for endless model search.

**X2-MAJ-03 — “Compact” does not establish adequate capacity or an informative comparison.**  
R20 discusses equal-parameter versus equal-compute comparisons but does not yet establish what would make a compact representative capable of testing its assigned hypothesis. A poorly optimized or aggressively compressed model may lose because of optimization, state bottlenecks, receptive-field truncation or unsuitable normalization. A family label cannot resolve those alternatives. Later governance needs an explicit adequacy rationale and permitted diagnostic boundaries before interpreting failures.

These are three distinct objections. Repetitions elsewhere in this report do not create additional severity counts.

## 6. MODERATE objections

**X2-MOD-01 — Bar controls restrict information, not merely architecture.**  
OHLCV aggregation is many-to-one: different event paths can produce the same bar. Failure on bars cannot settle whether a separately admissible event or quote representation contains information. R20 acknowledges this, so the concern is conclusion discipline rather than a newly discovered omission.

**X2-MOD-02 — Efficient long-context capability risks being evaluated at an irrelevant scale.**  
A state-space model restricted to a very short history cannot answer its principal efficiency question. Conversely, more history changes warmup eligibility and sometimes sample composition. Context comparisons need both capability relevance and comparable forecast origins.

**X2-MOD-03 — Self-supervision is grouped too closely with external foundation-model risk.**  
R20 reasonably defers opaque pretrained embeddings, but locally fitted self-supervised representation learning is a different hypothesis. It still requires strictly chronological corpus authority and adds selection burden; it need not inherit an external checkpoint’s unknown exposure. Deferral is reasonable, categorical dismissal would not be.

## 7. MINOR objections

**X2-MIN-01 — Registry S52 compresses opposing findings imprecisely.**  
The public 2026 Chronos financial follow-up reports gains from multivariate modeling within its studied equity and interest-rate panels, while mixing equity and rate series worsens accuracy. Registry S52’s description of related equities/rates reducing accuracy can obscure this distinction. R02’s narrower warning about mixing is more faithful. Record a later bibliography clarification without modifying frozen evidence now. [Das, Goyal and Yadav, 2026](https://arxiv.org/abs/2605.21504)

**X2-INF-01 — Family names are imperfect capability labels.**  
A dilated TCN can have substantial history; attention can be compact; a recurrent state can be restrictive despite unbounded nominal history. This is informational and supports capability descriptions alongside family names.

## 8. Evidence supporting objections

The strongest support is structural rather than financial. A model cannot condition on information excluded by its input. A purely additive class cannot generally express unrestricted conditional interactions. A finite receptive field cannot distinguish histories identical inside that field but different outside it. These are methodological facts; their relevance to ES/NQ is an unverified transfer hypothesis.

PatchTST demonstrates one practical route to handling longer histories through patch tokens, and includes self-supervised representation results. It supports the existence of a distinct capability question, not a requirement to deploy attention. [Nie et al., ICLR 2023](https://arxiv.org/abs/2211.14730)

iTransformer explicitly reallocates attention to variates. Its reported forecasting results challenge the assumption that channel-independent sharing adequately tests cross-variable dependence. They do not demonstrate profitable lead-lag structure between futures. [Liu et al., ICLR 2024](https://arxiv.org/abs/2310.06625)

The recent TimeMixer++ and TimeDART results strengthen the case that representation and temporal scale deserve independent consideration. Their relevance is that task performance can depend on what the representation preserves, not simply the number of fitted parameters.

## 9. Evidence against objections

The capacity skeptic must confront strong counterevidence. LTSF-Linear showed that simple linear models could outperform the compared Transformer forecasters on the authors’ benchmark collection. This undermines any general inference from greater architectural expressiveness to better forecasting. It does not prove that all subsequent attention models or all financial tasks are redundant. [Zeng et al., AAAI 2023](https://arxiv.org/abs/2205.13504)

Long histories can add stale relationships, missingness and irrelevant observations. Joint modeling can introduce negative transfer. Self-supervised objectives can favor reconstructing high-variance nuisance components. A larger network may be more capable of fitting training data and less reliable forward.

R20 already anticipates most of these issues: matched origins, training-only transforms, full search accounting, single-task controls and insufficient-evidence outcomes are explicit. The critique therefore supports sharper interpretation and admission rules more strongly than it supports expanding the initial model roster.

## 10. Recent 2025-2026 evidence that materially matters

Four source additions were checked by title, URL or identifying string against the registry; none was found there. They are additions to this review’s evidence ledger, not edits to the frozen registry.

**X2-S01 — Wang et al., TimeMixer++, ICLR 2025.**  
Primary peer-reviewed conference paper. The authors combine multiple temporal scales and frequency resolutions and report results across eight analytical tasks. This supports investigating multiscale representation; it does not isolate which component would help ES/NQ or justify the full architecture. [Conference record](https://proceedings.iclr.cc/paper_files/paper/2025/hash/2b187165e28fdfdc0ffb34d1bfff2b0c-Abstract-Conference.html)

**X2-S02 — Liu et al., Slimming the Fat-Tail: Morphing-Flow for Adaptive Time Series Modeling, ICML 2025.**  
Primary peer-reviewed paper. It reports benefits from a transformation/adaptation framework with linear and patch-Mamba backbones. The linear-backbone result is important counterevidence to architecture-first explanations. Its test-time component would require separate chronological scrutiny; this review does not endorse it. [PMLR record](https://proceedings.mlr.press/v267/liu25bq.html)

**X2-S03 — Wang et al., TimeDART, ICML 2025.**  
Primary peer-reviewed paper. A causal patch encoder and diffusion-based representation objective produce reported forecasting/classification gains. It supports a self-supervision research hypothesis while leaving financial relevance and additional computational expense unresolved. [PMLR record](https://proceedings.mlr.press/v267/wang25r.html)

**X2-S04 — Dao and Gu, Transformers are SSMs, ICML 2024.**  
Primary conference research, included despite its earlier date because it sharpens the efficiency argument. State-space duality and Mamba-2 show that efficient sequence modeling need not imply small nominal context. Reported core-layer speedups in language settings are not local host measurements. [Author record](https://arxiv.org/abs/2405.21060)

Two recent sources already in the registry were independently revisited:

- Chronos-2, 2025 preprint: group attention and multivariate/covariate forecasting provide an existence proof of broader cross-series capability, with predominantly generic benchmark evidence. [Author paper](https://arxiv.org/abs/2510.15821)
- TIME, 2026: the author record identifies an ICML-accepted camera-ready benchmark with fresh datasets and task-centric evaluation. It strengthens the case for evaluating capability under relevant tasks rather than relying on legacy leaderboard aggregates. [Author record](https://arxiv.org/abs/2602.12147)

No cited source supplies a verified prospective, cost-adjusted intraday ES/NQ result.

## 11. Evidence that does NOT transfer cleanly to ES/NQ

Electricity, weather and traffic often possess stable seasonal structure and forecasting targets unlike short-horizon futures returns. Better level forecasting can reflect persistence and scale rather than information about increments.

Language-model throughput is not forecasting throughput on the user’s hardware. Specialized kernels, batch size, sequence width and preprocessing can dominate practical performance.

Monthly equity/rate forecasts do not establish sub-minute or minute-scale ES/NQ synchronization, execution feasibility or useful return prediction. Financial subject matter alone does not close this gap.

General classification improvements from self-supervision do not establish forward calibrated return distributions. Likewise, a benchmark named Exchange is not an intraday CME futures replication.

These transfer limits apply symmetrically: generic evidence favoring simple models is also insufficient to establish that compact models are adequate for every ES/NQ hypothesis.

## 12. ES/NQ transferability considerations

ES and NQ are related equity-index futures, but relatedness alone does not establish incremental information. Shared exposure can make the second instrument largely redundant. Conditional sector-sensitive responses could instead create useful interactions. Which description applies is unknown here.

Apparent cross-market benefit can arise from unequal availability, stale observations, different missingness filters or changes in evaluated origins. R20’s temporal foundation is therefore part of the capacity question: a sophisticated encoder can amplify a timing artifact.

Long context may summarize volatility, session progression or prior shocks more plausibly than it predicts return sign. These are distinct estimands. Evidence for risk-state persistence must not be borrowed to justify directional complexity.

Contract transitions, sessions and incomplete history affect recurrent state and coarse aggregates. No model should receive inaccessible prehistory simply because its mathematical recurrence permits it. Actual eligible independent episodes and resource fit remain unknown; bar counts cannot resolve either.

## 13. Risk of underfitting

Underfitting has several mechanisms: insufficient function complexity, inaccessible history, lossy state compression, overly strong regularization, optimization failure and an output objective that suppresses relevant structure.

Those mechanisms should not be conflated. If a model cannot fit eligible training relationships, that is an adequacy warning, not proof of genuine signal. If it fits them but fails forward, increasing capacity may intensify variance. If all representations omit a causal variable, increasing capacity does nothing.

The appropriate scientific distinction is among “no reproducible benefit detected under the admitted procedure,” “the comparison was uninformative because adequacy or precision was insufficient,” and “evidence excludes benefits of a specified material size in the tested domain.”

This review chooses no numerical effect threshold or diagnostic experiment. It requires only that the eventual claim match the evidence. A research budget can end while scientific uncertainty remains.

## 14. Risk of inadequate representation

R20’s raw, engineered and small hybrid views are a useful defense against representation monoculture. They nevertheless share the bar information boundary.

A deterministic transformation of the same completed bars cannot restore event ordering discarded during aggregation. Normalization can also discard economically meaningful state if the transform removes scale without retaining its causal reference. Conversely, raw prices can make trivial scale or persistence effects appear valuable.

Completed multiresolution bars primarily reorganize or compress underlying history; they do not automatically add information. The scientific hypothesis is often improved accessibility or inductive bias, not new data. Longer fine-resolution history and shorter coarse summaries must therefore be described separately.

Joint-variable representation adds another distinction: shared parameters, concatenated inputs, additive effects and learned interactions are different capabilities. Success or failure of one is not conclusive evidence about all the others.

## 15. Capabilities justified for initial testing

The following classifications are conditional scientific eligibility judgments. They do not prescribe a portfolio or authorize R1.

**C1 — Access to meaningfully longer causal history: SUPPORTED_FOR_INITIAL_TESTING.**  
Hypothesis: available earlier observations contain predictive state beyond a short recent window. A short-window comparator cannot answer this by construction. Patch-based and state-space research supports technical feasibility; irrelevant or stale history is counterevidence. Compute rises with retained history and activation storage. Context choices create multiple-testing opportunities. ES/NQ transfer is most plausible for persistent risk/session state and remains unknown for returns. Eliminate preference for longer history if eligible forward evidence excludes a material incremental benefit under an adequate matched-origin comparison; imprecision means unresolved, not eliminated.

**C2 — Completed multiresolution representation: SUPPORTED_FOR_INITIAL_TESTING.**  
Hypothesis: coarse and fine summaries make useful structure easier to learn. A short fine-scale model may lack the relevant effective history, but a matched-history linear or dense comparator might already suffice. R06 and TimeMixer++ support consideration; smoothing can erase shocks and gains may merely reflect extra history. Compute includes aggregation and additional inputs; scale selection increases discovery risk. ES/NQ use depends on completed, available bars and session semantics. Eliminate the representation preference when gains disappear after equalizing history/origins or fail across eligible future conditions.

**C3 — Joint ES/NQ information with bounded conditional interaction: SUPPORTED_FOR_INITIAL_TESTING.**  
Hypothesis: one instrument’s relationship to the target depends on the other instrument or an observable state. Isolated/additive models can miss this; a small nonlinear joint comparator may already express it, so attention is not required. iTransformer and Chronos-2 supply external support; redundancy and the 2026 mixed-panel degradation supply counterevidence. Compute can remain modest. Synchronization, feature and interaction choices enlarge the search universe. Eliminate this capability preference if incremental evidence vanishes after availability/missingness controls or is unstable across valid forward conditions.

**C4 — Capacity adequacy within an admitted compact family: SUPPORTED_FOR_INITIAL_TESTING.**  
Hypothesis: an excessively restrictive representative can miss structure its broader family can express. A single small model cannot distinguish that possibility from lack of signal. Structural expressiveness supports the question; simple-model benchmark success and limited effective sample size oppose automatic expansion. Compute and seed sensitivity rise with size. Width, depth, regularization and training duration are selection choices. ES/NQ benefit is unknown. Eliminate escalation when additional admissible capacity fails to improve forward evidence or only reduces training loss. No size or search schedule is selected here.

## 16. Capabilities justified only as exploratory

**C5 — Patch-based temporal attention: SUPPORTED_ONLY_AS_EXPLORATORY.**  
Hypothesis: interactions between separated temporal motifs matter beyond compressed local summaries. Linear lags cannot express arbitrary interactions; a sufficiently capable TCN or MLP may. PatchTST supports feasibility; LTSF-Linear and patch-boundary sensitivity oppose presumptive superiority. Attention cost depends on patch count, with information loss possible inside patches. Patch lengths, strides and position encodings add selection choices. ES/NQ transfer remains indirect. Eliminate preference if matched-history alternatives capture the same benefit more reliably, or results depend on fragile patch choices. [PatchTST](https://arxiv.org/abs/2211.14730), [LTSF-Linear](https://arxiv.org/abs/2205.13504)

**C6 — Structured state-space long-context encoding: SUPPORTED_ONLY_AS_EXPLORATORY.**  
Hypothesis: a compact structured state can preserve useful long-history information efficiently. A restricted receptive field cannot answer that question; ordinary recurrence and simple summaries may. Mamba/state-space research supports efficient sequence processing, while compression can lose precise retrieval information. Compute may scale favorably with length but actual operators and memory remain unqualified. State size, reset policy and history length create search freedom. ES/NQ state persistence is plausible but unverified. Eliminate preference when comparable eligible alternatives match evidence at lower burden or state assumptions fail. [Mamba](https://arxiv.org/abs/2312.00752)

**C7 — Input-selective Mamba-style state: SUPPORTED_ONLY_AS_EXPLORATORY.**  
Hypothesis: relevance-dependent forgetting retains market state better than fixed dynamics. A fixed linear state cannot express all such selection; gated recurrence is a direct simpler alternative. Mamba and Mamba-2 support the mechanism and efficiency research; their principal evidence does not establish futures forecasting. Specialized compute can offset asymptotic advantages at short contexts. Gating, kernels and state choices add degrees of freedom. Eliminate selective-state preference if nonselective or recurrent controls perform comparably or apparent gains depend on unstable rare events. C6 and C7 are related capabilities, not a requirement for two candidates.

**C8 — Cross-variable attention: SUPPORTED_ONLY_AS_EXPLORATORY.**  
Hypothesis: variable-dependent weighting extracts conditional structure more efficiently than a fixed joint mapping. An additive model is insufficient, but a small joint MLP is a credible comparator. iTransformer supports external feasibility; two instruments may offer too little structural breadth to justify attention. Channel attention costs grow with channel count and temporal embeddings. Token definitions and variable selection increase discovery risk. ES/NQ transfer requires genuine causal joint observations. Eliminate attention preference if a simpler nonlinear joint model explains the gain. Failure of additive context alone cannot eliminate it. [iTransformer](https://arxiv.org/abs/2310.06625)

**C9 — Learned multiresolution encoder: SUPPORTED_ONLY_AS_EXPLORATORY.**  
Hypothesis: learned integration preserves interactions among scales better than fixed summaries. A concatenation comparator may suffice; fixed averaging may lose transients. TimeMixer++ supports this distinction, while its bundled components weaken attribution to any single capability. Compute and tuning exceed a simple completed-bar view. Learned periods, scales and fusion weights enlarge multiplicity. ES/NQ periodicity may shift around shocks. Eliminate the learned encoder preference if its incremental benefit disappears against matched-history summaries or depends on retrospective scale construction.

**C10 — Local self-supervised representation learning: SUPPORTED_ONLY_AS_EXPLORATORY.**  
Hypothesis: eligible historical observations teach features that improve downstream sample efficiency. Supervised training alone may use weak labels inefficiently; those labels are not necessarily scarce in raw count, so the claimed advantage needs scrutiny. TimeDART and PatchTST support generic transfer; nuisance reconstruction and inappropriate augmentation invariance oppose inclusion. Pretraining adds compute and objective selection. Every corpus cutoff, checkpoint and downstream choice belongs to the selection ledger. ES/NQ transfer is unknown. Eliminate preference if downstream forward scores/calibration do not improve despite better pretraining loss. [TimeDART](https://proceedings.mlr.press/v267/wang25r.html)

## 17. Capabilities still unjustified

**C11 — External representation pretraining or foundation checkpoints: INSUFFICIENT_EVIDENCE.**  
Hypothesis: a broad prior transfers useful dynamics to ES/NQ. Local supervised or self-supervised models may lack that diversity. Chronos-2 supports general transfer capability; contamination uncertainty, domain mismatch and negative transfer oppose admission. Inference may be affordable while provenance review and fine-tuning remain costly. Checkpoint selection is additional search. No admitted corpus identity or ES/NQ result is established here. Eliminate a particular checkpoint from consideration when provenance cannot support the proposed evaluation, or admissible forward evidence shows no incremental value. This does not eliminate pretraining as a research field.

**C12 — Event/quote representations as an immediate expansion: INSUFFICIENT_EVIDENCE.**  
Hypothesis: omitted event ordering or liquidity state contains information absent from bars. No bar-only comparator can recover genuinely discarded information. Aggregation mathematics supports the possibility; useful availability, history quality and effect size are unknown. Reconstruction/storage and timing costs may be substantial; many event definitions create discovery risk. ES/NQ relevance is plausible without being demonstrated. Eliminate a proposed representation when source authority or causal reconstruction fails, or later valid comparisons show no useful increment. This report authorizes no acquisition.

**C13 — Large hybrids, MoE or scale escalation without a specific deficit: NOT_JUSTIFIED.**  
Hypothesis: complementary mechanisms or conditional specialization overcome a demonstrated compact-model limitation. No such limitation has been demonstrated. Modern scaling papers provide generic motivation, but sparse regime support and attribution problems are strong counterarguments. Training, routing and maintenance costs increase, as do combinatorial choices. ES/NQ transfer is unsupported. Eliminate the proposal absent a precise capability deficit and an admissible simpler comparator; novelty is not an admission criterion.

## 18. Required remediation

For X2-MAJ-01, replace any scientific necessity claim attached to simple cross-market success with an explicit distinction between main effects and conditional interactions. Retain simple models as comparators.

For X2-MAJ-02, require eventual negative findings to state their information and capability domain. A bounded research program may stop without making a universal absence claim.

For X2-MAJ-03, require later proposals to explain why the admitted representative can test its assigned hypothesis and how optimization failure, truncation and state compression would limit interpretation. This is documentation and governance work before selection, not an R1 design supplied here.

Keep deferred capabilities visible with reasons and elimination conditions. Record the S52 clarification separately from frozen artifacts. Do not expand the candidate list automatically in response to this review.

## 19. Questions that remain unresolved

How much independently eligible history exists? Which target has enough independent episodes for a meaningful comparison? Does longer history add information or mostly nuisance state?

Are ES/NQ interactions mostly additive, nonlinear, redundant or artifacts of timing? Would self-supervision preserve target-relevant variation or wash it out?

Can resource constraints support a capability-relevant comparison without changing the scientific question? Which failure would justify narrower inference, and which would justify elimination?

None of these questions was answered by inspecting protected evidence. None is resolved by counting papers.

## 20. R1 blockers

The new-objection tally remains **0 BLOCKER**.

R20’s inherited source/partition authority, temporal admissibility, selection-policy and isolation prerequisites remain applicable. Their satisfaction was not established by X2. This review therefore makes no recommendation to begin R1.

A future broad “no reproducible signal” claim without adequate capability coverage would be scientifically unacceptable, but that potential future overclaim is classified MAJOR rather than being inflated into an unconditional blocker to all narrowly scoped research.

## 21. Non-blocking concerns

Compute uncertainty, candidate redundancy and possible negative transfer are material but normally govern scope and interpretation. They do not require every modern capability to be tested.

The program should tolerate an honest insufficient-evidence outcome. More models are not a substitute for independent episodes, admissible data or an appropriate estimand. Conversely, a fixed budget is a practical stopping reason rather than evidence that all untested representations are uninformative.

No hardware benchmark or numerical resource promise is made.

## 22. What R20 got right

R20 retains strong controls, explicitly includes longer-context and joint-information questions, recognizes representation loss, distinguishes forecast targets and treats architecture priorities as hypotheses.

Its refusal to equate calibration with profitability, hashes with clean data, or generic benchmarks with ES/NQ evidence is essential. Its warning that sparse evidence does not demonstrate impossibility directly supports the capacity skeptic’s central concern.

The report also correctly defers massive systems and rejects invented order flow from bars. Additional capacity cannot restore missing information or repair contamination.

## 23. What R20 may be overclaiming

The principal overclaim is the implication that simple cross-market benefit is a necessary precursor to a richer interaction question. The second is any later conversion of a compact-model research outcome into a claim about the whole available information set.

R20 itself usually avoids these overclaims. Its support-document gate and priority language nevertheless create an implementation risk: provisional convenience can become an unexamined scientific constraint.

Recent literature supports preserving capability questions, not presuming their answers. Equally, lack of direct ES/NQ proof supports uncertainty; it does not preferentially validate the smallest architecture.

## 24. Final adversarial assessment

R20 is more capacity-aware than its primary/secondary labels suggest. The strongest challenge is therefore targeted: **do not require additive success to admit a conditional-interaction question, and do not let bounded model failure become a universal absence-of-signal conclusion.**

Final unique severity totals: **BLOCKER 0; MAJOR 3; MODERATE 3; MINOR 1; INFORMATIONAL 1.** Existing R20 admission prerequisites are retained without being counted as new X2 discoveries.

The most important remediation is a capability-bounded interpretation and admission policy. The strongest point supporting R20 is its explicit refusal to treat insufficient evidence as impossibility. The strongest point challenging R20 is the shortlist’s logically unnecessary simple-cross-market-success prerequisite.

Four new public-source additions are identified as X2-S01–X2-S04. Existing registry sources were distinguished from additions; the registry was not modified. Literature evidence supports conditional exploration, not architecture selection, expected profitability or experiment authorization.

This first-pass conclusion was formed independently of all other X conclusions. No files were written by this reviewer. No protected material, source code, dataset or credential was accessed. No training, inference, scoring, benchmark, backtest, repository test, trading, broker connection, installation, environment change or Git mutation occurred. The coordinator must materialize, verify, hash and freeze this complete report before proceeding to the next reviewer.

**END OF X2_CAPACITY_SKEPTIC — COMPLETE INDEPENDENT RECOVERY REPORT**
