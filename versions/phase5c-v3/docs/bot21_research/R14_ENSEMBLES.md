# R14 — Independent ensemble / fusion research

Status: COMPLETE — independent first pass frozen on 2026-09-24.
Scope: literature research only. Source count: 14 distinct works, R14-S01–R14-S14. Public research was actively searched through 2026-09-24; this is a bounded review, not a claim of exhaustive coverage. No architecture is selected and no prototype shortlist or implementation is created.

## Independence and evidence boundary

I am the fresh R14 specialist. I read the recovery request and public primary research pages, proceedings, author-hosted research and abstracts. I did not read the old R14 text, any R13–R19 report, other new specialist reports, master synthesis, source code, datasets, protected outputs or protected OOS. No R1–R12 report was needed. The previous R14 file was copied without opening its contents to R14_PRE_RECOVERY_COORDINATOR_DRAFT.md; both files had SHA-256 5CE0C44827258324696A5B581055FEE47A902D46660FA1E03E149197069A2A9B before replacement. Conclusions below are my own research assessment, not a coordinator-directed architecture preference.

Evidence levels distinguish established methodology from demonstrated benchmark performance and unverified transfer to ES/NQ. I verified bibliographic metadata and abstracts/proceedings summaries; I did not reproduce experiments or audit every paper's code or full experimental protocol. No source reviewed establishes profitable, causal intraday ES/NQ trading after costs. All ES/NQ implications are explicitly methodological inferences.

## Main finding and remaining uncertainty

Strongest finding: ensemble size and architectural variety do not establish useful diversity. Gains require sufficiently good members with complementary out-of-time errors; weighting and routing introduce another estimation problem. A causal comparison of one general model, specialists, and fusion is scientifically warranted, but none is justified as the winner by current public evidence. Simple combination remains a serious comparator [R14-S01, R14-S02].

Largest uncertainty: whether ES/NQ contain persistent, causally usable complementary signals across instruments, horizons and regimes large enough to survive correlated errors, smaller specialist samples, selection bias, execution costs and added latency. Generic forecasting and image-classification results cannot settle that question.

## Terms that must remain distinct

| Family | What is combined | Scientific motivation | Principal uncertainty / cost |
|---|---|---|---|
| One general model | Pooled inputs and/or training examples | Share statistical strength and one operational path | Negative transfer; one model and preprocessing failure can affect every output |
| Early fusion | Synchronized raw/derived features before a shared encoder | Learn joint nonlinear interactions | Alignment and scale errors propagate into a shared representation |
| Intermediate fusion | Separate representations joined by concatenation, learned mixing or cross-attention | Preserve instrument/timeframe structure before interaction | More parameters and attribution ambiguity |
| Late fusion | Complete forecasts or predictive distributions | Modular comparisons and member-level diagnostics | Cannot recover interactions discarded before forecasts were made |
| Fixed weighted ensemble | Forecasts combined with constant weights | Reduce estimation variance | Weights may age; equal weights can include weak members |
| Stacking | Base predictions passed to a trained meta-model | Learn complementary errors | Meta-model leakage and extra fitting/selection variance |
| Deep ensemble | Independently fitted neural predictors | Capture variation between plausible fitted functions | Multiple training/inference costs; shared data bias remains |
| Specialist systems | Models restricted by instrument, horizon, session or context | Fit genuinely different conditional relationships | Fragmented effective sample size and undefined boundary behavior |
| Mixture of experts (MoE) | Expert outputs/hidden states selected or weighted by a router | Conditional capacity and specialization | Router collapse, expert starvation, routing error and overhead |

A multihead network is not automatically an independent ensemble. Channel-independent shared weights are not separate fitted ES/NQ encoders. Internal sparse MoE blocks are not interchangeable with independently trained, independently deployable specialists. A learned gate is itself a predictor with a training cutoff and failure modes. These distinctions matter when attributing any future benefit.

## Diversity, correlated errors and weighting

For fixed weights summing to one and residual vector e, the ensemble error variance is w' Cov(e) w; bias is w' E[e]. Under the simplifying assumptions of equal residual variance sigma^2 and equal pairwise correlation rho, the equal-weight average has variance sigma^2 [rho + (1-rho)/M]. This algebra is illustrative, not a market estimate: at rho=1 increasing M provides no variance reduction, and reducing variance does not remove a shared bias. The relevant correlations are residual correlations on comparable causal evaluation points, not correlations of raw ES/NQ prices or visually different architectures.

Useful diversity can arise from different data views, horizons, inductive assumptions, objective functions or training samples. Random seeds can explore different fitted functions [R14-S03], but bootstrap samples of dependent observations are not independent evidence and arbitrary row resampling destroys time structure. Members can disagree because one is poor; maximizing disagreement alone is not a sensible objective.

Future analysis would need error covariance, joint tail failures, incremental contribution when a member is removed, stability across contiguous periods, and both unconditional and conditional error diagnostics. A small overall correlation may hide simultaneous failures in volatile periods. A common data outage or timestamp defect will affect even independently trained models. Numerical covariance inversion is especially fragile with many highly correlated members and few independent observations; constrained or shrunk weighting deserves methodological scrutiny rather than automatic preference for estimated optimal weights. The forecast-combination literature documents the tradeoff between sophistication and estimation uncertainty [R14-S01].

## Calibration and uncertainty

Deep ensembles have strong benchmark evidence for uncertainty estimation [R14-S03]. They do not supply a certificate of safety or a calibrated probability of a profitable trade. Ovadia et al. show that uncertainty quality deteriorates under shift and that calibration measured on an ordinary validation distribution need not carry to a shifted distribution [R14-S04]. Post-hoc temperature scaling has useful classification evidence [R14-S05], but its calibration data must precede use and its success is not established for the proposed market task.

Within-member predictive noise and between-member disagreement are different quantities. For a weighted mixture of distributions, total variance equals the weighted within-component variance plus the weighted squared deviation of component means from the mixture mean. This identity is not proof that the first term measures all aleatoric risk or that the second measures all epistemic risk. All members can share the same blind spot and confidently agree.

Probability averaging, logit averaging, mean-forecast averaging and mixture-density construction have different meanings. Averaging quantiles does not generally produce quantiles of the density mixture. Evaluate the combined distribution itself with a proper score suited to the target (for example log loss/Brier for classification, CRPS for distributions), reliability and interval coverage by horizon and relevant context. Calibration diagnostics require sample-size uncertainty; bin counts and the extreme-probability tail matter. Recalibrating members does not guarantee the pooled output is calibrated. Prediction calibration, decision threshold selection and economic outcomes are separate questions.

## General model versus specialists

Pooled learning can share information without assuming that each series is identical; the local/global forecasting literature supports studying both and explains that pooling is not inherently restricted to obviously similar series [R14-S06]. This is not a guarantee for two correlated futures. Two instruments do not provide the cross-sectional diversity of a large forecasting panel.

Specialization can target instrument identity, response horizon, session conditions or causally observed volatility. It earns scientific credibility only if conditional relationships differ reproducibly and enough past observations support each component. Splitting by every instrument, timeframe and regime multiplies sparsity. Shared encoders with separate output heads lie between complete pooling and completely separate training, and their shared errors must remain visible.

Regime-conditioned routing must use information available before the decision. A retrospective segmentation using future volatility, final daily range, later trend extrema or hindsight change points is an oracle comparator, not deployable evidence. Soft routing may avoid discontinuities but blend incompatible specialists. Hard routing simplifies selection yet can jump at boundaries. Neither solves ambiguous, new or poorly sampled states. A learned router can exploit calendar artifacts rather than stable market structure; balanced utilization is an optimization diagnostic, not proof of meaningful specialization.

## ES/NQ joint encoding and separate encoders

Joint early encoding permits direct cross-instrument relationships but may confound instrument scales, missingness and delayed availability. Separate encoders can retain instrument-specific representations and make branch diagnostics easier; their later merger still requires causal alignment. Independent per-instrument training loses parameter sharing and may be noisier. Shared-weight channel-independent processing is yet another case: PatchTST supplies forecasting evidence for channel independence [R14-S07], while iTransformer supplies evidence for explicitly learning cross-variate correlations [R14-S08]. These are competing empirical motivations, not an ES/NQ verdict.

Cross-attention lets one representation query another and can represent asymmetric relationships; TimeXer is a concrete exogenous-variable forecasting example [R14-S09]. Calling NQ exogenous to ES does not establish causal economic direction or permission to use a future NQ observation. Attention scores are model-internal weights, not causal explanations. Any future study must distinguish common drivers from stable incremental predictive information.

The decision-time information set is the binding constraint for all forms of fusion. Matching nominal timestamps is insufficient if one observation or bar is not yet available. Missing/stale inputs, timestamps, instrument identity and target horizon must have explicit meaning. This is a research prerequisite, not a design of the final temporal contract and not a resolution of R16.

## Multi-timeframe fusion

Fine and coarse histories can encode different scales. TimeMixer demonstrates a multiscale mixing approach on generic forecasting benchmarks [R14-S10]. It does not establish that adding chart intervals creates independent information: coarse bars are transformations of the same underlying observations, and overlapping windows create dependence.

An incomplete higher-timeframe bar cannot be retrospectively replaced with its eventual closing value. Centered smoothing, whole-series decomposition, full-session statistics and normalization computed with future observations contaminate even a simple fusion model. Distinct branches can make these dependencies more inspectable but do not cure leakage. Multiple horizons also create multiple target definitions; their forecasts cannot be averaged without a coherent common target or explicitly evaluated decision mapping.

Any later evidence should isolate whether gains come from longer context, increased parameters, more input observations, or the fusion operation. Comparing a large multiscale model to a smaller short-context model alone cannot identify the source of improvement. This is a general validity condition, not a new experiment authorization.

## MoE and current 2025–2026 evidence

Switch Transformers provide primary evidence that sparse conditional activation can increase capacity efficiently, while also addressing instability and communication costs in very large language models [R14-S11]. Activated parameter count is not total model storage and FLOPs are not measured end-to-end latency. A single-device, small-batch trading decision need not inherit multi-accelerator training speedups.

Time-MoE provides 2025 conference evidence for sparse time-series foundation models trained on a very large multidomain corpus [R14-S12]. This supports the feasibility of time-series MoE, not a claim that training a small ES/NQ specialist gate will improve performance. Data scale, target domains, objective and pretraining availability differ substantially.

The 2026 Timer-S1 preprint reports further foundation-model scaling and broad forecasting results [R14-S13]. The 2026 MoHETS preprint combines heterogeneous experts with multiscale structure and covariate cross-attention [R14-S14]. These are current research directions, explicitly preprint-level in this review. Their reported aggregate forecasting improvements do not verify trading utility, calibrated tail risk, sparse-data regime routing or affordable latency on the user's machine. No code or checkpoints were downloaded or executed.

## Compute, latency, interpretability and failure isolation

Dense late ensembles generally require all members' forward passes. Parallel execution may reduce critical-path latency but increases concurrent memory demand; serial execution reuses memory at added latency. Training cost includes every seed, member, meta-model and calibration stage. A shared trunk may reduce compute while increasing common-mode failures. Sparse gating reduces activated work only when the implementation and workload actually exploit it; router dispatch, many small kernels and memory movement can dominate small batches.

A meaningful future comparison would account for peak memory, warm and cold behavior, tail latency, preprocessing, cross-instrument waiting, calibration and fusion overhead, not just parameter counts. This report makes no measured hardware claim and does not supersede R15.

Late fusion makes member forecasts and weighted contributions inspectable. Separate components can isolate a bad model version or stale branch only if their input dependencies and outputs are independently observable. Failure isolation is weaker when all members share one feed, normalization or scheduler. Removing a failed member changes the predictive distribution and may invalidate calibration; casually renormalizing surviving weights is not automatically safe. Cross-attention and hidden-state MoE offer richer interactions but weaker direct attribution. Stable routing patterns are useful diagnostics, not economic explanations.

## Evidence classification and admissibility of a future comparison

Well-supported methodology: retain a general-model comparator; estimate incremental rather than nominal diversity; keep the meta-learner's fitting data distinct from in-sample base predictions; preserve temporal availability through preprocessing, routing and calibration; assess the final combined distribution and common-mode errors. Stacked regressions supplies the foundational held-out-prediction principle [R14-S02]. For dependent market labels, chronological out-of-time base predictions and avoidance of overlapping label leakage are necessary adaptations; ordinary shuffled folds are not enough.

Promising but unproven for ES/NQ: constrained late fusion, deep ensembles, parameter sharing across instruments, separate encoders with modest interaction, and multiscale representations. Their literature support warrants questions, not selection.

Experimental for this use: learned regime routers, hidden-state sparse MoE, uncertainty-weighted routing, complex cross-attention and transferred foundation-model specialists. Recent forecasting papers increase plausibility without closing domain, data and operational gaps.

Dangerous or insufficiently supported: weighting members by their in-sample performance; learning stacking weights on predictions from members trained on those same labels; choosing experts using future regimes; treating low disagreement as guaranteed confidence; selecting many members after repeated evaluation and reporting only the winning combination; claiming lower active FLOPs proves lower live latency; assuming more models diversify execution or data faults.

An eventual scientific comparison of ONE GENERAL MODEL versus MULTIPLE SPECIALIZED MODELS versus ENSEMBLE/FUSION is justified. It would require the same causal information and target, fair tuning and compute accounting, chronological separation of fitting/selection/calibration/evaluation, uncertainty that respects temporal dependence, and accounting for all selection attempts. Gains must be stable enough to matter relative to complexity and any eventual decision costs. This report does not select architectures, prescribe a prototype sequence, resolve other reports, access protected evaluation material or authorize experiments.

## Sources

All records introduced independently by R14; accessed 2026-09-24. Distinct work count: 14. A proceedings version and its arXiv version count once. Bibliographic URLs below are primary proceedings, author/university or author-submitted research records.

### R14-S01
- Title: Forecast combinations: an over 50-year review.
- Authors: Xiaoqian Wang, Rob J. Hyndman, Feng Li, Yanfei Kang.
- Year / venue: 2023, International Journal of Forecasting 39(4), 1518–1547; preprint 2022.
- URL / DOI: https://fpp.robjhyndman.com/publications/combinations/ ; https://doi.org/10.1016/j.ijforecast.2022.11.005
- Evidence type: Peer-reviewed methodological review; author-hosted metadata/summary verified.
- Limitations: Broad synthesis, not direct ES/NQ evidence or a universal guarantee for equal weighting.
- BOT 2.1 relevance: Combination uncertainty, correlation, simple versus estimated weights and probabilistic combinations.

### R14-S02
- Title: Stacked Regressions.
- Author: Leo Breiman.
- Year / venue: 1992, UC Berkeley Statistics Technical Report 367; institutional page references later Machine Learning publication with uncertainty, so this record cites the verified report.
- URL: https://statistics.berkeley.edu/tech-reports/367
- Evidence type: Primary university research report.
- Limitations: General regression methodology; temporal market dependence requires additional safeguards.
- BOT 2.1 relevance: Cross-validated predictions and constrained fitting of combination weights; foundational stacking evidence.

### R14-S03
- Title: Simple and Scalable Predictive Uncertainty Estimation using Deep Ensembles.
- Authors: Balaji Lakshminarayanan, Alexander Pritzel, Charles Blundell.
- Year / venue: 2017, NeurIPS 30.
- URL: https://papers.nips.cc/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html
- Evidence type: Peer-reviewed classification/regression benchmark research.
- Limitations: No ES/NQ trading evidence; disagreement is not complete uncertainty and compute increases with members.
- BOT 2.1 relevance: Independent neural fits and probabilistic ensemble uncertainty.

### R14-S04
- Title: Can you trust your model's uncertainty? Evaluating predictive uncertainty under dataset shift.
- Authors: Yaniv Ovadia, Emily Fertig, Jie Ren, Zachary Nado, D. Sculley, Sebastian Nowozin, Joshua Dillon, Balaji Lakshminarayanan, Jasper Snoek.
- Year / venue: 2019, NeurIPS 32.
- URL: https://proceedings.neurips.cc/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html
- Evidence type: Peer-reviewed empirical uncertainty benchmark.
- Limitations: Studied shifts and classification tasks do not reproduce financial nonstationarity.
- BOT 2.1 relevance: Calibration can degrade under shift even when validation calibration was good.

### R14-S05
- Title: On Calibration of Modern Neural Networks.
- Authors: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
- Year / venue: 2017, ICML, PMLR 70:1321–1330.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Evidence type: Peer-reviewed classification calibration research.
- Limitations: Image/document classification; temperature scaling does not ensure market-shift calibration.
- BOT 2.1 relevance: Evaluate confidence separately from discrimination and fit calibration causally.

### R14-S06
- Title: Principles and algorithms for forecasting groups of time series: Locality and globality.
- Authors: Pablo Montero-Manso, Rob J. Hyndman.
- Year / venue: 2021, International Journal of Forecasting; university working paper 2020.
- URL / DOI: https://doi.org/10.1016/j.ijforecast.2021.03.004 ; https://www.monash.edu/business/ebs/research/publications/ebs/wp45-2020.pdf
- Evidence type: Peer-reviewed theory/methodology and forecasting research, institutional paper record.
- Limitations: General groups of time series; two futures and short-horizon conditional returns are a narrower problem.
- BOT 2.1 relevance: Pooling versus separate models is an empirical question; shared learning can be valid without identical series.

### R14-S07
- Title: A Time Series is Worth 64 Words: Long-term Forecasting with Transformers.
- Authors: Yuqi Nie, Nam H. Nguyen, Phanwadee Sinthong, Jayant Kalagnanam.
- Year / venue: 2022 arXiv preprint (PatchTST); later ICLR 2023 paper, abstract record used here.
- URL: https://arxiv.org/abs/2211.14730
- Evidence type: Primary forecasting architecture research.
- Limitations: Long-horizon benchmark results; channel independence does not establish separate ES/NQ-model superiority.
- BOT 2.1 relevance: Shared-weight channel-independent representation and patching as alternatives to joint encoding.

### R14-S08
- Title: iTransformer: Inverted Transformers Are Effective for Time Series Forecasting.
- Authors: Yong Liu, Tengge Hu, Haoran Zhang, Haixu Wu, Shiyu Wang, Lintao Ma, Mingsheng Long.
- Year / venue: 2024, ICLR; preprint 2023.
- URL: https://arxiv.org/abs/2310.06625 ; https://proceedings.iclr.cc/paper_files/paper/2024/file/2ea18fdc667e0ef2ad82b2b4d65147ad-Paper-Conference.pdf
- Evidence type: Peer-reviewed multivariate forecasting architecture research.
- Limitations: Benchmark correlations need not persist in financial conditional predictions; attention is not causality.
- BOT 2.1 relevance: Explicit interaction between per-variate representations supplies a competing fusion hypothesis.

### R14-S09
- Title: TimeXer: Empowering Transformers for Time Series Forecasting with Exogenous Variables.
- Authors: Yuxuan Wang, Haixu Wu, Jiaxiang Dong, Guo Qin, Haoran Zhang, Yong Liu, Yunzhong Qiu, Jianmin Wang, Mingsheng Long.
- Year / venue: 2024, author-submitted arXiv research record (2402.19072); venue not needed for claims here.
- URL: https://arxiv.org/abs/2402.19072
- Evidence type: Primary architectural and benchmark research.
- Limitations: Exogenous-variable framing does not prove economic exogeneity, causal availability or trading usefulness.
- BOT 2.1 relevance: Cross-attention to combine endogenous and external representations.

### R14-S10
- Title: TimeMixer: Decomposable Multiscale Mixing for Time Series Forecasting.
- Authors: Shiyu Wang, Haixu Wu, Xiaoming Shi, Tengge Hu, Huakun Luo, Lintao Ma, James Y. Zhang, Jun Zhou.
- Year / venue: 2024, ICLR.
- URL: https://arxiv.org/abs/2405.14616
- Evidence type: Peer-reviewed architecture and forecasting benchmarks; paper identifies ICLR 2024.
- Limitations: Generic multiscale forecasting, not proof that redundant market bars add independent information.
- BOT 2.1 relevance: Fine/coarse mixing and multiple predictors; motivation for careful timeframe ablation.

### R14-S11
- Title: Switch Transformers: Scaling to Trillion Parameter Models with Simple and Efficient Sparsity.
- Authors: William Fedus, Barret Zoph, Noam Shazeer.
- Year / venue: 2022, Journal of Machine Learning Research 23(120):1–39.
- URL: https://jmlr.org/papers/volume23/21-0998/21-0998.pdf
- Evidence type: Peer-reviewed sparse MoE systems/ML research.
- Limitations: Large language-model setting and hardware; active compute differs from total memory and actual small-batch latency.
- BOT 2.1 relevance: Conditional activation, training instability, routing and systems tradeoffs.

### R14-S12
- Title: Time-MoE: Billion-Scale Time Series Foundation Models with Mixture of Experts.
- Authors: Xiaoming Shi, Shiyu Wang, Yuqi Nie, Dianqi Li, Zhou Ye, Qingsong Wen, Ming Jin.
- Year / venue: 2025, ICLR; preprint 2024.
- URL: https://arxiv.org/abs/2409.16040 ; https://proceedings.iclr.cc/paper_files/paper/2025/file/558d48c1f08675daa636e09bfe94a89e-Paper-Conference.pdf
- Evidence type: Peer-reviewed time-series foundation-model research.
- Limitations: Massive multidomain pretraining and forecasting evaluation; no ES/NQ after-cost or local hardware guarantee.
- BOT 2.1 relevance: Current time-series MoE feasibility and the scale mismatch to a small market-specific system.

### R14-S13
- Title: Timer-S1: A Billion-Scale Time Series Foundation Model with Serial Scaling.
- Authors: Yong Liu, Xingjian Su, Shiyu Wang, Haoran Zhang, Haixuan Liu, Yuxuan Wang, Zhou Ye, Yang Xiang, Jianmin Wang, Mingsheng Long.
- Year / venue: 2026, arXiv preprint submitted March 5.
- URL: https://arxiv.org/abs/2603.04791
- Evidence type: Current primary preprint; abstract and metadata reviewed.
- Limitations: Author-reported results, no independent reproduction here; large-scale generic forecasting is not trading validation.
- BOT 2.1 relevance: 2026 sparse MoE scaling trajectory, with total versus activated capacity distinction.

### R14-S14
- Title: MoHETS: Long-term Time Series Forecasting with Mixture-of-Heterogeneous-Experts.
- Authors: Evandro S. Ortigossa, Guy Lutsker, Eran Segal.
- Year / venue: 2026, arXiv preprint submitted January 29.
- URL: https://arxiv.org/abs/2601.21866
- Evidence type: Current primary preprint; abstract and metadata reviewed.
- Limitations: Author-reported multivariate benchmarks; no ES/NQ result or verified latency/robustness claim for this setting.
- BOT 2.1 relevance: Heterogeneous expert routing and covariate cross-attention as experimental fusion directions.

## Completion attestation

First-pass research is complete and frozen. Only R14_ENSEMBLES.md and its exact-byte preserved predecessor were written by this specialist, both under docs/bot21_research. No registry edit was made by me; the source appendix is available for provenance-preserving coordinator append. No tests, training, inference, backtests, trading, installations, environment edits or Git mutations were performed. No protected material was accessed. No synthesis, architectural selection, implementation, R17–R20 or red-team work was performed.