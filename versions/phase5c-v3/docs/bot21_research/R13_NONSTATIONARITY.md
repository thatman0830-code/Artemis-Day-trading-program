# R13 — Nonstationarity and adaptation: independent first pass

Status: COMPLETE — FROZEN INDEPENDENT FIRST PASS. Completed 2026-09-24. Specialist: fresh R13 sub-agent in the R0-B recovery conversation. Source count: 15 distinct primary publications/documentation records, R13-S01–R13-S15. Search cutoff: 2026-09-24; this is a targeted evidence review, not a systematic claim of exhaustive literature coverage.

## Scope and strongest conclusion

An ES/NQ neural system can adapt causally only if every change to weights, scaling, probability calibration, and decision thresholds respects information availability. Adaptation policy itself must be treated as a fitted object: its triggers, window lengths, learning rates, and stopping rules can overfit historical noise even when individual model fits use past data only. This report assesses methodology; it selects no architecture or implementation and conducts no experiment.

**Strongest finding:** feature-distribution change, probability miscalibration, and loss of predictive information are different diagnoses. A feature alarm alone does not establish that retraining improves forecasts. Supervised adaptation cannot legitimately use a forecast's label until its entire outcome has become available. Recent forecasting research explicitly recognizes this delayed-feedback problem [R13-S11].

**Largest uncertainty:** how much stable, exploitable ES/NQ conditional signal survives after label delay, costs, changing market conditions, and adaptation-selection error. None of these sources establishes an optimal ES/NQ retraining interval, memory length, retirement boundary, or net trading benefit.

## Required distinctions

The following are operational definitions for this review. The probabilistic distinction follows concept-drift methodology [R13-S01]; the lifecycle implications are this specialist's deductions.

| Term | What changes or is measured | What it does not establish |
|---|---|---|
| Model retraining | Estimated predictor weights or representation, from scratch or by fine-tuning, using eligible historical labels | Improvement merely because weights are newer |
| Model recalibration | Mapping from a fixed model's output to probabilities, quantiles, or predictive intervals; in this report it excludes backbone retraining | Recovery of lost ranking/discrimination or a missing causal feature |
| Threshold recalibration | Cutoffs translating forecasts into action, abstention, or selection | Better underlying probability estimates; tuning it remains model selection |
| Feature-distribution monitoring | Changes in input marginals, dependence, missingness, scale, or support | A change in P(Y given X), or economic harm |
| Regime change | A persistent change in a specified market-generating mechanism or statistical state | A uniquely observable label; retrospective segmentation is not real-time detection |
| Predictive performance degradation | Deterioration in delayed, genuinely forward forecast scores against suitable comparators | That market drift caused it rather than data quality, random variation, calibration, or implementation changes |

Distribution shift is the broader change in P(X,Y). Covariate shift changes P(X); concept drift in the stricter supervised sense changes P(Y given X). Target prevalence may move too. These can occur together. A volatility increase may change forecast difficulty while a predictor retains the same relative advantage. Model aging is therefore deterioration associated with changed conditions, not a theorem that a model expires after a fixed number of days.

## Causal availability and leakage controls

The following are necessary research constraints, not a proposed final temporal contract. For a forecast issued at t and label with horizon h, the sample becomes eligible only after the outcome is complete and received, including any correction/processing delay. Eligibility is based on actual availability rather than a row timestamp or nominal t+h alone. Barrier/event labels can have variable maturity. A training window ending at t must still exclude immature labels originating before t. Proceed directly motivates attention to this gap [R13-S11].

All mutable state belongs in the chronology: scaler state, imputation rules, replay membership, optimizer state, calibration residuals, thresholds, detector reference distributions, and decisions to reset. Reconstructing historical forecasts using today's scaler or revised historical data can invalidate an otherwise chronological weight fit. A statistic over the complete session is unavailable at that session's opening. The current completed observation may inform its own input normalization if it is available at forecast time; later bars in the same evaluation batch may not.

For future authorized evaluation, an adaptation rule would need to be frozen before an outer chronological evaluation, with its tuning confined to earlier development periods. Each forecast would be scored as it was originally issued before its label is used for a later update. Recomputed forecasts after updating are not prequential evidence. Training/calibration/action-threshold samples need explicit roles; using the same outcomes to optimize all three and report success inflates confidence. These are methodological deductions, not evidence of a defect in BOT 2.0, which was not inspected.

TimeSeriesSplit documents expanding chronological splits and a gap, but a row-count gap does not automatically purge variable-horizon overlapping labels, solve irregular event timing, or reproduce delayed receipt [R13-S15]. The relevant exclusion is interval/availability based. Protected OOS is outside this review and was not accessed; future research eligibility does not override that boundary.

## Retraining, online learning, and the memory tradeoff

| Approach | Potential advantage | Principal weakness and research condition |
|---|---|---|
| Frozen predictor | Stable reference; no adaptation-selection variance | Can become stale; necessary comparator, not assumed winner |
| Expanding retraining | More observations and preservation of rare historical conditions | Stale observations may dominate; compute grows; equal weighting assumes more persistence than may exist |
| Rolling retraining | Limits stale-history influence | Discards useful recurrence and rare stress periods; a short window magnifies estimation noise |
| Recency-weighted fit | Smooth forgetting rather than a hard boundary | Decay rate is another selected hyperparameter; effective sample size may be much smaller than row count |
| Scheduled retraining | Predictable cadence and fewer data-dependent timing choices | Responds late to abrupt change and may update needlessly |
| Triggered retraining | Concentrates updates when evidence changes | False alarms, selection bias, feedback loops, and detection delay |
| Online gradient updates | Fast incremental adaptation with bounded update cost | Order dependence, noisy labels, optimizer-state drift, and forgetting |
| Continual learning with replay/constraints | Attempts to balance acquisition and retained competence | May preserve obsolete relationships or restrict useful plasticity |

The bias/variance and stale-information tradeoff is well established [R13-S01, R13-S02]. It does not determine whether expanding or rolling retraining wins here. A large bar count is not equivalent to many independent market episodes. Label overlap and session clustering reduce effective information; a brief adverse streak need not warrant a high-dimensional update. Window choice and cadence cannot be supplied responsibly from these publications alone.

Online learning describes sequential updates; continual learning additionally focuses on retention and transfer across changing tasks/distributions. Catastrophic forgetting is a demonstrated neural-learning issue: EWC slows changes to weights estimated as important for prior tasks [R13-S07]. Preserving prior knowledge is not always desirable when the old relationship is invalid. Financial drift may also be gradual with no reliable task boundaries, unlike many benchmark setups.

Replay buffers retain past examples to reduce forgetting. Reservoir sampling favors an approximation to historical frequency; recent-only memory favors adaptation; stratified memory can preserve rare known contexts but changes the effective training distribution. This taxonomy is this review's reasoning, not a validated BOT 2.1 buffer prescription. Replay membership must be decided using information available then, not hindsight profitability or full-history regime clusters. Inputs alone can enter memory before labels, but supervised replay requires mature labels. Store the relevant preprocessing provenance conceptually, because replaying old standardized tensors under a new scaler can change their meaning.

Replay is no universal stability guarantee: ICML 2024 work reports optimization instability even with all previous training examples [R13-S08]. AISTATS 2026 provides recovery bounds for dependent nonlinear regression tasks under specified task-transformation assumptions [R13-S12]. Those assumptions are valuable to inspect, but are not demonstrated properties of ES/NQ. Thus continual learning remains promising research rather than an established production remedy for this application.

## Adaptive normalization and test-time adaptation

A past-only rolling mean/scale, robust scale estimate, or input-window normalization can address changing location and scale without updating a predictor's full weights. RevIN is peer-reviewed evidence that reversible per-instance normalization can improve forecasting under distribution shift [R13-S04]. It is not proof that normalizing away volatility preserves market information. For ES/NQ, volatility magnitude may itself matter; removing it without retaining causally available scale information could erase useful conditioning. Small windows, outliers, nearly zero variance, and session/contract transitions require scrutiny. These are application-specific hypotheses.

Normalization changes also create a diagnostic hazard: a monitor running only after adaptive standardization may conceal the raw shift it is meant to detect. Future analysis should distinguish raw observation changes from standardized-model-input changes. Learned affine normalization parameters are fitted parameters; calling them normalization does not exempt them from leakage control.

TENT adapts normalization-related parameters through prediction-entropy minimization without labels [R13-S05]. CoTTA addresses accumulating pseudo-label error and forgetting in continual visual domain adaptation [R13-S06]. These are evidence that test-time adaptation can work in their studied settings, not evidence that market labels are recoverable from confidence. ICML 2025 ranked entropy minimization explicitly studies collapse to a single class [R13-S14]. A financial model can become confidently wrong during a genuine reversal in P(Y given X).

Causal TTA would have to specify update-before-predict versus predict-before-update, available batch composition, and reset rules. Even unlabeled future inputs are future information if a retrospective batch spans subsequent bars. The 2026 revision of ShifTS distinguishes temporal shift from concept drift and proposes a forecasting framework [R13-S13]; it remains an arXiv preprint in the record inspected, and claims of horizon-based invariant learning require full causal evaluation scrutiny before transfer. Neither its abstract nor this review establishes production validity.

## Recalibration and action thresholds

Temperature scaling is a simple established post-hoc probability-calibration method [R13-S03]. Its evidence comes from image/document classification, so ES/NQ calibration must be assessed in its own chronology. If ranking remains useful but probabilities become systematically overconfident, low-dimensional recalibration is more targeted than assuming that every representation weight needs changing. If the ordering of opportunities has deteriorated, a monotone calibration map cannot recover that information. Small recent calibration windows can themselves overfit, especially in the probability tails or rare action region.

Adaptive conformal inference targets long-run empirical coverage under changing distributions [R13-S09]; later work adapts tuning over time [R13-S10]. Coverage does not imply narrow/useful intervals, conditional coverage for every regime, a correct next-step probability, or profitable decisions. Delayed labels and multiple overlapping forecast horizons require attention to the algorithm's feedback assumptions. Conformal adaptation is promising for uncertainty monitoring, not an independent trading authorization.

Threshold recalibration changes who gets selected even when probabilities do not change. Selection based on a tiny recent profit sample can chase noise. Forecast quality and action economics should be examined separately: costs or execution conditions can degrade realized utility without degrading predictive scores. Conversely, a recalibrated score can look statistically better while producing no useful action. All threshold searches consume selection capacity and must be counted within the adaptation policy's validation burden. This is specialist reasoning, not a fitted threshold recommendation.

## Detection, triggers, and retirement

ADWIN is a well-established adaptive-window change detector with false-positive/negative guarantees under its model assumptions [R13-S02]. That does not transfer unchanged to heavy-tailed, dependent market losses, many simultaneous streams, overlapping windows, or repeatedly reset detectors. Clipping an unbounded score creates a bounded monitored variable but also changes what is being measured; no nominal significance level should be interpreted as a universal trading alarm probability.

Feature monitoring can examine shifts in support, missingness, scale, correlation, or a multivariate discrepancy. Its reference needs relevant session/time-of-day context so ordinary periodicity is not automatically called a new regime. A distribution alarm should first motivate diagnosis of data availability and semantics. Predictive monitoring needs mature outcomes, proper forecast scores, and a comparator exposed to the same difficulty. Calibration, discrimination, and conditional errors can disagree. Looking at only aggregate accuracy or realized PnL loses those distinctions.

The following trigger principles are judgments for later research, not configured rules: require persistence or corroboration rather than one abnormal bar; specify a minimum mature-information requirement; account for multiple monitored metrics and repeated examination; separate an alert from a decision to update; and evaluate the entire trigger/reset/retraining loop rather than a model chosen after seeing the drift date. Hysteresis and cooldown can reduce oscillation but also delay recovery. Their costs and choices require validation; no particular number is supported here.

Retirement should mean withdrawing a model version's eligibility when evidence or basic validity no longer supports its use, not deleting its audit history. Distinguish temporary quarantine for unreliable data, rollback after an unsuccessful update, and longer-term retirement after persistent relative degradation or invalid assumptions. Calendar age alone and a single losing streak are weak retirement grounds. A candidate replacement should not automatically inherit the incumbent's evidence. Keeping a versioned frozen comparator would help attribute deterioration, but this report designs no deployment process and executes none.

## Evidence assessment and unresolved questions

| Classification | Assessment for BOT 2.1 research |
|---|---|
| Well-supported methodology | Availability-aware chronology; separate input drift from predictive degradation; recognize memory/recency tradeoffs; evaluate calibration separately; distinguish training from monitoring |
| Promising, conditional | Periodic rolling or expanding retraining; constrained recalibration; conservative detector-assisted review; causal normalization; replay with explicitly assessed retention/plasticity |
| Experimental for ES/NQ | Autonomous online neural updates; proactive parameter-generation adaptation; continual TTA; inferred-regime-driven memory; adaptive conformal systems with application-specific delayed feedback |
| Dangerous or insufficiently supported | Full-session/full-test normalization; immediate access to future labels; endless recent-PnL threshold optimization; automatic retraining on every feature alarm; confidence maximization as a substitute for outcomes; selecting the best historical drift policy and calling its same-period performance independent |

These categories classify evidence transfer, not permission to run anything. Open questions include conditional signal half-life, minimum independent episodes for calibration, the severity of feedback delay, whether old regimes recur usefully, sensitivity to rare events, and whether update gains exceed added variance and operational burden. Disagreement with any other specialist remains unresolved because their reports were not read.

## Completion and independence attestation

I independently authored this first pass from the user's attached instructions and public primary sources. I did not read the existing R13 content, any R14–R19 report, master synthesis, or another new specialist report. I did not need the allowed audit, R1–R12, or registry for this first pass. The prior R13 coordinator draft was copied without displaying or consuming its contents and its exact SHA-256 matched: 1D3256DCC39E391648A0C1C2AD63771E26619722A012485D458F7C34E44303DE.

Only the R13 report and its preservation copy were written under docs/bot21_research. No BOT 2.0 source, data, protected output, protected OOS, model, environment, or execution system was read or changed by this specialist. No training, inference, tests, experiments, backtests, trading, package installation, or Git mutation was performed. This is a completed research document, not a claim of empirical validation. Its final file hash is reported separately to avoid a self-referential hash. First pass ends here; no synthesis, architecture selection, implementation, or R17–R20 work follows.

## Sources

All records introduced by fresh specialist R13; accessed 2026-09-24. Count: 15 unique works/pages. Repeated appearances of the same work are not extra sources. Limitations and relevance below are R13 assessments. Search snippets and source landing pages/abstracts support scope-level claims; selected accessible primary PDFs supplied further method context. This is not a claim to have audited every proof or reproduced any result.

### R13-S01
- Title: A Survey on Concept Drift Adaptation.
- Authors: Joao Gama, Indre Zliobaite, Albert Bifet, Mykola Pechenizkiy, Abdelhamid Bouchachia.
- Year/venue: 2014, ACM Computing Surveys 46(4), Article 44.
- URL/DOI: https://doi.org/10.1145/2523813
- Evidence type: Peer-reviewed methodological survey; publisher record and author university manuscript consulted.
- Limitations: Broad stream-learning literature; predates modern TTA and is not an ES/NQ trading study.
- BOT 2.1 relevance: Drift definitions, memory/recency tradeoffs, and evaluation framing.

### R13-S02
- Title: Learning from Time-Changing Data with Adaptive Windowing.
- Authors: Albert Bifet, Ricard Gavalda.
- Year/venue: 2007, SIAM International Conference on Data Mining, 443–448; accessible author manuscript dated 2006.
- URL/DOI: https://doi.org/10.1137/1.9781611972771.42 ; https://www.cs.upc.edu/~Gavalda/papers/adwin06.pdf
- Evidence type: Peer-reviewed algorithm and theory with empirical demonstrations.
- Limitations: Assumption-dependent guarantees; market dependence and unbounded losses need separate treatment.
- BOT 2.1 relevance: Adaptive windows and distinguishing detection from revision.

### R13-S03
- Title: On Calibration of Modern Neural Networks.
- Authors: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
- Year/venue: 2017, ICML, PMLR 70:1321–1330.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Evidence type: Peer-reviewed empirical calibration study.
- Limitations: Image/document tasks; no guarantee of calibration under future market shifts.
- BOT 2.1 relevance: Separates post-hoc probability calibration from representation fitting.

### R13-S04
- Title: Reversible Instance Normalization for Accurate Time-Series Forecasting against Distribution Shift.
- Authors: Taesung Kim, Jinhee Kim, Yunwon Tae, Cheonbok Park, Jang-Ho Choi, Jaegul Choo.
- Year/venue: 2022, ICLR.
- URL: https://openreview.net/pdf?id=cGDAkQo1C0p
- Evidence type: Peer-reviewed time-series normalization method and benchmarks.
- Limitations: Benchmark forecasting is not trading utility; potentially informative scale can be removed.
- BOT 2.1 relevance: Causal input-window normalization as a distinct adaptation mechanism.

### R13-S05
- Title: Tent: Fully Test-Time Adaptation by Entropy Minimization.
- Authors: Dequan Wang, Evan Shelhamer, Shaoteng Liu, Bruno Olshausen, Trevor Darrell.
- Year/venue: 2021, ICLR.
- URL: https://openreview.net/pdf?id=uXl3bZLkr3c
- Evidence type: Peer-reviewed unsupervised test-time adaptation research.
- Limitations: Primarily vision corruption/domain settings; confidence need not identify correct market direction.
- BOT 2.1 relevance: Defines an experimental adaptation mechanism and its transfer risk.

### R13-S06
- Title: Continual Test-Time Domain Adaptation.
- Authors: Qin Wang, Olga Fink, Luc Van Gool, Dengxin Dai.
- Year/venue: 2022, IEEE/CVF CVPR, 7201–7211.
- URL: https://openaccess.thecvf.com/content/CVPR2022/html/Wang_Continual_Test-Time_Domain_Adaptation_CVPR_2022_paper.html
- Evidence type: Peer-reviewed CoTTA method and vision experiments.
- Limitations: Pseudo-label assumptions and visual shifts do not establish financial applicability.
- BOT 2.1 relevance: Error accumulation and forgetting during continual adaptation.

### R13-S07
- Title: Overcoming catastrophic forgetting in neural networks.
- Authors: James Kirkpatrick, Razvan Pascanu, Neil Rabinowitz, Joel Veness, Guillaume Desjardins, Andrei A. Rusu, Kieran Milan, John Quan, Tiago Ramalho, Agnieszka Grabska-Barwinska, Demis Hassabis, Claudia Clopath, Dharshan Kumaran, Raia Hadsell.
- Year/venue: 2016 arXiv manuscript; published PNAS 2017.
- URL: https://arxiv.org/abs/1612.00796
- Evidence type: Primary EWC study, archival manuscript of peer-reviewed research.
- Limitations: Sequential benchmark tasks differ from unlabeled market regimes; retention can conflict with forgetting obsolete signals.
- BOT 2.1 relevance: Establishes the plasticity/retention problem.

### R13-S08
- Title: Layerwise Proximal Replay: A Proximal Point Method for Online Continual Learning.
- Authors: Jinsoo Yoo, Yunpeng Liu, Frank Wood, Geoff Pleiss.
- Year/venue: 2024, ICML, PMLR 235:57199–57216.
- URL: https://proceedings.mlr.press/v235/yoo24a.html
- Evidence type: Peer-reviewed online continual-learning study.
- Limitations: Benchmark results; replay improvement does not prove financial robustness.
- BOT 2.1 relevance: Replay does not by itself eliminate optimization instability.

### R13-S09
- Title: Adaptive Conformal Inference Under Distribution Shift.
- Authors: Isaac Gibbs, Emmanuel Candes.
- Year/venue: 2021, NeurIPS 34.
- URL: https://papers.neurips.cc/paper_files/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html
- Evidence type: Peer-reviewed theory and real-data demonstrations.
- Limitations: Long-run coverage does not guarantee local conditional coverage, useful width, or profit.
- BOT 2.1 relevance: Adaptive uncertainty calibration with explicit interpretation limits.

### R13-S10
- Title: Conformal Inference for Online Prediction with Arbitrary Distribution Shifts.
- Authors: Isaac Gibbs, Emmanuel J. Candes.
- Year/venue: 2024, Journal of Machine Learning Research 25.
- URL: https://www.jmlr.org/papers/v25/22-1218.html
- Evidence type: Peer-reviewed online conformal theory and methodology.
- Limitations: Forecast usefulness and application-specific feedback delays require separate assessment.
- BOT 2.1 relevance: Extends adaptation of conformal tuning; does not remove causal-label constraints.

### R13-S11
- Title: Proactive Model Adaptation Against Concept Drift for Online Time Series Forecasting.
- Authors: Lifan Zhao, Yanyan Shen.
- Year/venue: KDD 2025; arXiv first posted 2024, version 5 revised 2025-12-18.
- URL/DOI: https://arxiv.org/abs/2412.08435 ; https://doi.org/10.1145/3690624.3709210
- Evidence type: Primary forecasting research, accepted venue stated in author manuscript record.
- Limitations: Five forecasting datasets and synthetic drift training do not validate ES/NQ utility or universal proactive adaptation.
- BOT 2.1 relevance: Explicit delayed-ground-truth gap; motivates maturity-aware research.

### R13-S12
- Title: Recovery Guarantees for Continual Learning of Dependent Tasks: Memory, Data-Dependent Regularization, and Data-Dependent Weights.
- Authors: Liangzu Peng, Uday Kiran Reddy Tadipatri, Ziqing Xu, Eric Eaton, Rene Vidal.
- Year/venue: 2026, AISTATS, PMLR 300:3592–3600.
- URL: https://proceedings.mlr.press/v300/peng26a.html
- Evidence type: Peer-reviewed theoretical study.
- Limitations: Nonlinear task-transformation assumptions are not demonstrated for market sequences.
- BOT 2.1 relevance: Current 2026 evidence that continual-learning guarantees remain explicitly assumption-dependent.

### R13-S13
- Title: Tackling Time-Series Forecasting Generalization via Mitigating Concept Drift.
- Authors: Zhiyuan Zhao, Haoxin Liu, B. Aditya Prakash.
- Year/venue: 2025 arXiv preprint, version 2 revised 2026-03-25; no peer-reviewed venue established from inspected record.
- URL: https://arxiv.org/abs/2510.14814
- Evidence type: Primary preprint, ShifTS forecasting framework.
- Limitations: Preliminary evidence; no ES/NQ production conclusion and no independently verified causal deployment protocol here.
- BOT 2.1 relevance: Current research distinguishes temporal shift from concept drift; merits cautious scrutiny.

### R13-S14
- Title: Ranked Entropy Minimization for Continual Test-Time Adaptation.
- Authors: Jisu Han, Jaemin Na, Wonjun Hwang.
- Year/venue: 2025, ICML; OpenReview publication record dated 2025-05-01.
- URL: https://openreview.net/forum?id=lHaGLJ65J9
- Evidence type: Primary peer-reviewed conference record/abstract retrieved through search; subsequent direct page access encountered browser verification.
- Limitations: Vision evidence, not financial forecasts; limited retrieved content used only for the stated collapse concern.
- BOT 2.1 relevance: Documents a concrete failure mode of continual entropy minimization.

### R13-S15
- Title: TimeSeriesSplit.
- Authors/organization: scikit-learn developers.
- Year/venue: Living official documentation, stable page accessed in 2026.
- URL: https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html
- Evidence type: Official framework API documentation.
- Limitations: Split utility is not a financial leakage proof; row-count gap and regular spacing assumptions require interpretation.
- BOT 2.1 relevance: Chronological expanding splits and explicit gap semantics; highlights need for availability-aware evaluation.