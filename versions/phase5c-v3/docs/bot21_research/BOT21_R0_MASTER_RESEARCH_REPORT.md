# BOT 2.1 Phase R0 — Master Scientific & Neural Intelligence Research Report

**Research cutoff/access date:** 2026-09-24  
**Scope:** Literature and architecture research only. No code, model, training, inference, benchmark, prediction, protected OOS access, paper order, broker connection, or trading was performed.  
**Repository boundary:** `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`, branch `bot2-phase5c-z-review-remediation`, HEAD `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb` at initial inspection. Worktree was already dirty and remains untouched outside the newly authorized `docs/bot21_research/` area.  
**Review status:** Independent specialist first passes verified for R1–R12 so far. R13–R19 remain coordinator research notes pending independent passes. R20 synthesis and fresh X1–X8 adversarial reviews remain uncompleted. Therefore this is an interim, evidence-grounded report, not a review-ready completion.

## 1. Executive summary

The literature supports no single winning neural architecture for intraday ES/NQ. Generic time-series benchmarks, equity limit-order-book classification, daily equity returns, commodity futures, and model-marketing results do not establish cost-adjusted index-futures value. The most defensible next research posture is deliberately comparative: keep naïve/linear/statistical controls and a compact causal CNN/TCN; consider one predeclared recurrent, patch-attention, state-space and multiscale alternative only under matched causal inputs, context/compute budgets, and a frozen evaluation protocol. Large hybrids, mixtures of experts and foundation-model deployment are not justified before incremental value, provenance, and contamination are independently demonstrated.

Retain the one-minute OHLCV representation as a transparent baseline, with causal returns/range/volatility and explicit session/contract/time-quality context as prospective research candidates. More granular trades, quotes, MBP/MBO and order-flow are distinct data products with materially greater sequencing, synchronization, storage and licensing burdens. Cross-market ES/NQ inputs must use receipt-time-safe as-of alignment; neither correlation nor general futures price discovery proves stable ES↔NQ leadership.

Predictive target, calibration/uncertainty, regime context, and any later decision policy must remain separate. No prediction should become an order, sizing instruction, broker message, risk authorization, or paper-trade authority through this research phase. R0 is incomplete because the requested independent-role coverage, R20 synthesis, and X1–X8 red team are not complete.

## 2. BOT 2.0 preservation assumptions

The user-provided R0 specification is authoritative. BOT 2.0 is a valuable existing system and is read-only here: data schemas/contracts, timestamp logic, archives, features/targets, Phase 5C manifests/protocols/results, risk, pretrade authorization, paper gateway, ledger, execution, monitoring, recovery, credentials and provider configuration are not to be altered. Phase 5C remains paused; protected OOS stays closed. No Phase 5C performance or scientific decisions were used to choose a BOT 2.1 architecture. The initial git branch/HEAD and dirty state were recorded; no checkout, stash, reset, cleanup, commit or merge occurred.

## 3. Research methodology

Research was organized into 19 specialist roles; their full remit appears in the supplied R0 brief. Independent first-pass reports are verified for R1–R12 at this report revision. Role documents R13–R19 contain coordinator synthesis and must not be represented as independent findings. Sources were prioritized for peer-reviewed methods and primary/official technical references. Conclusions are labeled by evidence class and transfer limits. No model selection, new-data acquisition or result-driven protocol choice was performed.

## 4. Source quality methodology

Each source should be assessed by publication type/status, date/authors, what was actually measured, benchmark/data, target and horizon, split design, market/instrument, costs, replication and relevance. Vendor/official documentation can establish technical semantics but not alpha. An abstract or preprint is a lead, not established evidence. The source registry contains IDs, links/DOIs, type/status, reported finding, caveats, relevance and access date; bibliographic uncertainties are explicitly left uncertain rather than completed from memory.

## 5. 2025–2026 neural research landscape

Recent work expands multivariate/covariate-aware time-series foundation models, fresh-data benchmark design, calibration audits, financial candle pretraining, masked/self-supervised methods, efficient SSMs and online calibration under shift. Chronos-2, TimesFM-3, Kronos, FinCast, Time-MoE, TimeMixer and related work are candidates to monitor, not evidence of ES/NQ benefit. Some 2025–26 work is peer reviewed; some is vendor-authored or preprint. Provenance, data overlap, benchmark freshness, scale cost and transfer remain key uncertainties [S18–S23,S52–S57,S79,S101].

## 6. Financial time-series research landscape

Financial ML is dominated by low signal-to-noise, nonstationarity, heavy tails, changing liquidity, overlapping targets, market frictions and multiple testing. DeepLOB/FI-2010 study mid-price direction on equities; other LOB studies and OFI work motivate microstructure hypotheses. Daily cross-sectional equity results, a 2026 daily multi-asset futures benchmark preprint, and a 2024 ES/VX term-structure preprint do not establish ES/NQ 1-minute value. A historical E-mini execution study is relevant to execution modeling but is not a present-day strategy validation [S24,S38,S47–S51,S72–S74,S119,S120].

## 7. ES/NQ market characteristics relevant to neural modeling

ES and NQ have different contract multipliers despite the same 0.25 index-point minimum tick; contract/session/roll identity must remain explicit. Globex hours include breaks and holiday exceptions. RTH, overnight/ETH, roll windows and scheduled event periods represent different conditions. Intraday activity/volatility profiles are documented but not stationary guarantees. MBO/MBP semantics and sequence recovery matter for any depth model. Evidence does not justify a fixed ES-leads-NQ or NQ-leads-ES rule [S29–S34,S58–S66].

## 8. Input representation options

Options range from bars, returns, ranges, realized volatility and volume, to trades/ticks, quotes/spread, book depth, imbalance, microprice and event order flow. Each is a different information and failure surface. Bar aggregation loses path/order-book state; trade-only data omits unexecuted liquidity; MBP aggregates per-price state; MBO carries order-level detail at higher reconstruction burden. All added inputs require completeness, sequence, timestamp, synchronization and provenance contracts [S32,S33,S67–S77].

## 9. Feature representation options

No feature engineering or registry changes are authorized. For later comparison, raw/normalized prices, causal returns, ranges, volatility, relative activity and session context are plausible, but all transforms must be fit on past-only training data and session/contract-aware. Learned representations may complement or replace hand-built inputs only in frozen, isolated ablations. A feature’s predictive association is not a causal explanation or trade signal.

## 10. Multi-timeframe options

Distinguish bar timeframe, sampling resolution, and forecast horizon. Candidate 1/5/15/30-minute, hourly and session-to-date context remains unselected. Hierarchical aggregation and TimeMixer provide general methodological motivation; an indexed futures abstract and iron-ore-futures multiscale study are insufficient for ES/NQ transfer [S78–S81]. Any higher-timeframe bar must be both complete and received by decision time; partial OHLC high/low/close/volume leaks future events.

## 11. Target options

Potential estimands include fixed-horizon signed return, direction probability, return quantiles/distribution, future realized risk, path/barrier outcome, time-to-event, state/regime and auxiliary targets. These answer different questions. Target windows have maturity and overlap; labels cannot cross a data split without purging. Path labels need intrabar path and tie-breaking definitions. Meta-labels can entangle model and policy. No target or thresholds are selected [S35,S36].

## 12. Regime modeling options

Regime may be observed context, a target, a filtered latent state, or an expert router; these are not interchangeable. Full-sample clustering and smoothed latent states can use future information. Start any later investigation with causal observable context and a no-regime baseline; regime taxonomies, transition labels, HMMs and learned routing remain hypotheses. A regime label is not direction or permission to bypass uncertainty/risk [S16,S25].

## 13. Candidate neural architectures

Candidates span TCN/causal CNN, LSTM/GRU, CNN-RNN hybrids, Transformer/TFT, PatchTST, iTransformer, TimesNet, Informer/Autoformer/FEDformer/Crossformer, TiDE/N-BEATS/N-HiTS, S4/Mamba, foundation TS models, MoE and ensembles. The attached comparison matrix records qualitative properties without fabricated scores. No winner is declared [S01–S17,S18–S23,S52–S57].

## 14. TCN analysis

TCNs offer causal local filters, dilation, parallel training and direct multi-horizon heads. Their fixed receptive field and aliasing/stride choices remain relevant; TCN-vs-RNN evidence is from general sequence tasks and does not establish ES/NQ superiority [S01]. Keep a compact causal TCN as a candidate/control, not as a presumed winner or as authorization to evaluate BOT 2.0 A2.

## 15. Recurrent-model analysis

LSTM/GRU are natural streaming state models but train sequentially and compress history into state. They do not inherently solve drift, calibration, uncertainty, or regime adaptation. Any later comparison should use matched information/context and account for state reset at session/contract boundaries. No direct ES/NQ family advantage is established [S02].

## 16. Transformer analysis

Transformers can model long-range interactions but attention/memory and positional/causal design matter; long context can increase data demand and selection capacity. TFT adds gating, variable selection, local recurrent processing and quantile outputs, not guaranteed causal explanation or reliable calibration. LTSF-Linear results caution against assuming complexity wins [S03,S04].

## 17. PatchTST analysis

Patching can reduce sequence tokens and encode subseries motifs. Channel independence may omit cross-market interactions. Patch length/stride and effective history are experiment dimensions and must be frozen. Reported long-horizon results are general time-series evidence, not ES/NQ [S05].

## 18. iTransformer analysis

iTransformer treats variates as tokens and models cross-variate interactions after history projection. This is a distinct inductive bias, but variable alignment and asynchronous ES/NQ updates are essential; naive joins may manufacture relationships. Evidence remains generic forecasting [S06].

## 19. TimesNet analysis

TimesNet folds around detected periods to model intra-/inter-period changes. It is a plausible periodicity hypothesis but may be sensitive to shocks, session changes and nonstationary periodicity. No evidence supports a stable ES/NQ period-based edge [S07,S46].

## 20. State-space analysis

S4/Mamba-style models offer efficient long-sequence state updates with different inductive bias. Platform kernels, version support, hidden-state resets and reproducibility need careful engineering. Linear/asymptotic efficiency is not necessarily beneficial at short contexts, and general sequence results do not show ES/NQ predictive value [S15,S16].

## 21. Hybrid-model analysis

Local CNN/TCN plus recurrent/attention/SSM branches may combine scales or dynamics, but each branch adds parameters, interfaces, attribution ambiguity and search multiplicity. A hybrid is justified only by repeatable incremental ablation under equalized data/context/compute budgets. No stack is selected.

## 22. Mixture-of-experts analysis

MoE can conditionally specialize, but routers may collapse, chase noise or learn unstable regime partitions. It increases compute and hidden degrees of freedom. Use only after a simpler expert or regime baseline shows complementarity; generic MoE results do not justify financial routing [S17,S23,S56].

## 23. Ensemble/fusion analysis

Compare early feature fusion, late output fusion, cross-attention, gated routing and simple weighted ensembles only as separately preregistered hypotheses. Error diversity is required for useful ensembling. Ensemble disagreement is not calibrated epistemic uncertainty absent validation. Keep single-stream baselines first.

## 24. Multi-task learning

Direction, volatility, structure, return distribution and event/path labels may share representations or interfere. Task loss weighting methods from other domains do not prove positive transfer. Measure per-task predictive quality and calibration; preserve a single-task baseline and predeclare weighting [S37].

## 25. Uncertainty/calibration

Distinguish aleatoric from epistemic uncertainty; a softmax score or ensemble spread is not calibrated by default. Calibration requires temporal separation and monitoring by horizon/session/regime. Proper scores, quantile coverage/width, reliability and risk-coverage summaries are candidates. Marginal conformal coverage is not conditional per-state coverage; adaptive methods offer assumption-specific or long-run guarantees, not immediate post-shift assurance [S22,S25–S27,S36,S95–S101].

## 26. Abstention/selective prediction

Abstention is a separate future output/policy with explicit quality, coverage and error tradeoffs. Evaluate risk-versus-coverage and subgroup stability without converting it into order suppression/release. Thresholds are not selected in R0; under drift both coverage and calibration can change [S25–S27].

## 27. Nonstationarity/concept drift

Separate covariate, label/base-rate, concept, volatility, seasonal/session, contract and source drift. A detected change does not justify retraining. Candidate comparisons include static, expanding, rolling and regime-specific fits, with detector false alarms/delay and rollback tracked. There is insufficient evidence for a safe, profitable adaptive schedule for ES/NQ [S46].

## 28. Loss functions

Cross-entropy/Brier, robust regression, quantile/pinball, parametric likelihood, CRPS/QLIKE, focal/weighted, multi-task and self-supervised losses answer different objectives. Quantile crossing, tail sparsity, probability distortion, noisy volatility proxies, outlier handling and invalid augmentations require scrutiny. Lower fit loss is not executable value. No loss is chosen in R0 [S36,S37,S85–S87,S112–S118].

## 29. Optimization

Adam/AdamW, SGD, learning-rate schedules and early stopping are engineering choices, not evidence of edge. Keep future search grids small, record all attempts/seeds, and select on training/validation chronology only. No optimizer or hyperparameter optimization has been run.

## 30. Regularization

Weight decay, dropout, augmentation, early stopping and architecture constraints can reduce fit capacity but add choices and can erase rare-event signal. Regularization must be selected on past-only data and recorded as another trial dimension. No numerical regularization setting is proposed.

## 31. Validation methodology

Use pre-registered rolling/forward chronological outer origins, nested chronological selection, purged target windows, training-only transforms, temporally separate calibration, and a final untouched period outside repeated selection. Compare paired per-origin losses and use dependence-aware uncertainty with explicit assumptions; report by horizon/session/regime and log every attempt. Reality Check/SPA/PBO/DSR answer limited questions over a known trial universe; none repairs leakage or creates independent OOS [S28,S43–S45,S94,S102–S108].

## 32. Leakage prevention

Treat each fit/prediction origin as an availability audit. Preserve event, publisher and receipt timestamps, revision/vintage, and earliest feature-usable time; use causal as-of joins with a staleness limit; prohibit future interpolation, full-sample transforms, incomplete higher-timeframe bars, immature/overlapping target labels, future-informed roll adjustment, and test-driven calibration/checkpoint selection. Foundation-model pretraining provenance is a separate contamination boundary; opaque provenance remains unknown [S19,S20,S29–S31,S102,S109–S111].

## 33. Multiple-testing/data-mining prevention

Pre-register hypotheses, contexts, splits, model count, metrics, seeds, stopping and failure criteria. Log every model/target/feature/threshold/human iteration. Keep negative controls and simple baselines. Corrections for selection bias are not a license to repeatedly inspect the final test [S28,S43–S45].

## 34. Transaction-cost considerations for later phases

Prediction accuracy is not executable value. Later authorized work must independently specify commissions/fees, spread, slippage, impact, latency, queue position, partial/rejected fills, market state and opportunity cost. This report performed no cost calculation, profitability optimization or strategy test [S47,S48].

## 35. GPU/software environment

No software was installed. PyTorch is a reasonable later candidate due its ecosystem and deterministic-operation controls, but exact reproducibility is hardware/version-dependent. Current JAX/TensorFlow GPU support on Windows has constraints; validate framework, CUDA, driver and custom-kernel compatibility before any authorized setup. Hardware claims from user-provided configuration were not benchmarked [S39–S42].

## 36. Session/calendar correction research

Use current, versioned CME product calendars; retain exchange-local session date, canonical time, DST, maintenance, special/holiday closes, contract month and roll identity. The first-observed-row session-open semantic risk noted in existing materials remains a read-only concern, not an edit request. Do not silently merge continuous-adjusted histories using future roll information [S29,S30,S58–S64].

## 37. ES/NQ synchronization research

Keep per-instrument event and receipt times. A strict same-as-of or one-sided backward as-of join with explicit staleness/missingness is a conservative baseline. Relaxing max skew is a separate experiment; nearest-future alignment and interpolation are prohibited. Archives lacking receipt times cannot substantiate live-availability latency. No leader assumption is warranted [S65,S66,S75–S77].

## 38. Preservation/integration boundary

If later authorized, BOT 2.1 should initially be a separate read-only research package/process with independent namespace, dependencies, manifest and data adapter. It must not import broker, credentials, sizing, execution, risk mutation, authorization or paper gateway pathways. No BOT 2.0 source/risk/provider/feature/target/protocol/result file was changed in this work.

## 39. Architecture comparison matrix

See [BOT21_ARCHITECTURE_COMPARISON_MATRIX.md](BOT21_ARCHITECTURE_COMPARISON_MATRIX.md), which compares inductive biases, context, multivariate support, compute, calibration and evidence limits. It assigns no performance score and selects no winner.

## 40. Specialist disagreement matrix

See [BOT21_RESEARCH_DISAGREEMENT_MATRIX.md](BOT21_RESEARCH_DISAGREEMENT_MATRIX.md). It records observed convergence and open questions. Independent R1–R12 passes are verified at this report revision; later role reports and R20 synthesis are not complete.

## 41. Adversarial findings

The coordinator-authored R18 note identifies architecture shopping, pretraining contamination, timestamp/as-of leakage, target overlap, nonchronological preprocessing, selection bias, nonstationary shock memorization, transfer errors, omitted fill/costs and unfair baselines. This is not the requested fresh X1–X8 independent red team. Those reviewers have not run; their challenge and resolution remain a blocking gap.

## 42. Strongest evidence

Strongest evidence here is methodological/technical rather than profitable: primary architecture papers define model properties; CME documentation defines contract/calendar/book semantics; financial ML work documents multiple-testing/implementation-cost risk; literature supports data/target/split rigor; and independent R1–R12 find no direct source reviewed proves an ES/NQ intraday neural winner. “Strongest” does not mean sufficient for architecture adoption.

## 43. Weakest evidence

Weakest evidence includes vendor model releases, preprints, abstracts with insufficient methods, broad benchmark leaderboard gains, small equity LOB classification benchmarks, daily equity results, commodity futures results, mock trading, and cross-market price discovery not specific to ES↔NQ. These may generate hypotheses but cannot establish cost-adjusted intraday value.

## 44. Unresolved scientific questions

What context/resolution adds independent information? Which target has stable, measurable predictive content? Do richer order-book inputs help after alignment/quality costs? Does any model outperform naïve/statistical controls across forward regimes? Can uncertainty/abstention stay calibrated under drift? What sample size supports credible uncertainty? Which TSFM claims survive clean, target-specific, cost-aware replication?

## 45. Unresolved engineering questions

Current point-in-time source/revision/receipt timestamp coverage, contract/session semantics, data-quality and missingness paths, ES/NQ synchronization tolerance, calendar versioning, replay determinism, framework compatibility and isolated data access all require later authorized design review. No runtime/cost/latency benchmark was run in R0.

## 46. Recommended architectures TO PROTOTYPE LATER

If a future phase is explicitly authorized: mandatory naïve/linear/statistical controls; a compact causal CNN/TCN; then a small predeclared comparison of one recurrent, one patch-attention, one state-space, and one multiscale candidate under matched inputs/context/compute. Simple late fusion can follow only after single-stream baselines. This is a shortlist for comparison, not adoption.

## 47. Architectures NOT currently justified

No large multi-branch hybrid, MoE router, end-to-end action model, deployed foundation model, learned trade policy, or TCN-only/Transformer-only winner is justified by current evidence. This is not a claim that those families cannot work; evidence is insufficient to prefer them now.

## 48. Recommended research sequence

Complete remaining independent specialist first passes; obtain R20 synthesis; run the eight fresh, independent adversarial reviews; resolve objections with sources; complete source/citation and preservation audits; submit for independent review. Only a later explicit authorization can start R1. At no point should this R0 proceed to implementation, experiment or trading.

## 49. Proposed Phase R1 objectives

**Proposal for review only, not authorization:** define a strictly isolated research protocol; freeze public/approved data provenance, causal timestamps, splits, candidate count, evaluation metrics and stopping criteria; build no broker/execution interface; compare simple baselines before compact candidate families; log all attempts; reserve untouched future evaluation; and include model-risk/contamination review. R1 should begin only after R0 completion and explicit user authorization.

## 50. Explicit list of things NOT YET AUTHORIZED

- BOT 2.1 implementation or executable code.
- Python/ML environment creation or dependency installation.
- Model training, inference, architecture experiments, benchmarking or prediction generation.
- A1/A2 evaluation or any performance comparison.
- Protected Phase 5C/OOS access, scoring, inspection or outcome use.
- New data purchase/download or expanding existing feed scope.
- BOT 2.0 feature, target, data, protocol, risk, broker, provider, execution or paper-trading changes.
- Broker connection, risk authorization, order generation, sizing, paper or live trading.
- Phase R1 work before independent R0 review and explicit authorization.

## CHATGPT BOT 2.1 R0 HANDOFF

- **Top findings:** no defensible neural winner; chronology, source availability, target maturity and market transfer dominate architecture fashion; complexity increases search/contamination/ops risk.
- **Best-supported architecture families:** simple/linear/statistical controls and causal CNN/TCN as comparison anchors; this is a methodological shortlist, not a profitability claim.
- **Promising families:** compact recurrent, patch-based attention, multiscale encoders and efficient SSMs as later matched ablations; 2025–26 TSFMs for comparison only after pretraining provenance review.
- **Weak/speculative families:** large hybrids, MoE/routing and zero-/few-shot foundation-model trading claims for current ES/NQ.
- **Baseline inputs:** clock-time one-minute OHLCV with causal returns/range/volatility and explicit time/session/contract/source-quality metadata; no representation change now.
- **Context research:** compare 1m-only to completed-bar additive scales under equalized causal context; no selected number of minutes.
- **Targets:** study distinct return/direction/distribution/risk/path/state estimands; separate forecasting from policy and enforce maturity/purging.
- **Regime:** begin with causal observable context and a no-regime baseline; latent/router approaches remain hypotheses.
- **Uncertainty:** calibrated distributions plus separately audited abstention are candidates; no threshold or execution role.
- **Validation/leakage:** frozen rolling-origin protocol, purge overlap, train-only transforms/calibration, full attempt registry, receipt-time joins, independent protected future holdout, no pretraining-contamination assumptions.
- **Software:** no installation in R0; consider a pinned isolated PyTorch stack later only after platform compatibility review.
- **BOT 2.0 isolation:** no imports or write access to broker, execution, risk, paper, credential or protected Phase 5C paths.
- **Future prototype shortlist:** naïve/linear/statistical; compact TCN; one representative recurrence, patch-attention, SSM and multiscale model only if protocol permits.
- **Major disagreements/open questions:** architecture complexity versus data regime; bar simplicity versus microstructure richness; context scale, target, regime and cross-market value remain unknown.
- **Top adversarial objections:** generic evidence may not transfer; latency/as-of and bar-boundary leakage; multiple tests; calibration drift; unrealistic fills/costs; greater model capacity can overfit.
- **Proposed R1 objectives:** protocol and provenance first; baselines before neural complexity; matched chronological testing and isolated read-only outputs. R1 is not authorized by this report.

**Final decision gate:** R0 remains incomplete because independent specialist coverage R13–R19, R20 synthesis and fresh X1–X8 review are outstanding.

R0 INCOMPLETE — IMPORTANT RESEARCH GAPS REMAIN
