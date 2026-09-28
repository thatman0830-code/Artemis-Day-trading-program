# R17 — Decision architecture: independent research first pass

Role: R17 independent decision-architecture specialist.
Status: COMPLETE; frozen first pass, 2026-09-24.
Research cutoff/access date: 2026-09-24. Source count: 12 unique public primary works/documentation records.
Scope: conceptual evidence and tradeoffs only. No strategy, execution logic, final BOT 2.1 architecture, implementation, or architecture winner is specified.

## Finding and scope of inference

The strongest finding is that **training objective, model output, and trading authority are different decisions**. End-to-end optimization does not logically require a model to hold execution permissions. A modular predictor does not become safe merely because its output passes through more components. Task-based learning supports aligning training with downstream objectives [R17-S01]; calibration and shift research show why predictive confidence alone cannot establish reliable action [R17-S02, R17-S03]. Exchange risk tooling separately illustrates controls administered outside the predictor [R17-S09, R17-S10]. These observations support distinguishing the questions, not selecting a complete architecture.

The largest uncertainty is whether an ES/NQ action-oriented model would improve economically relevant outcomes over a predictive system after realistic costs, causal timing, selection correction, tail exposure and operational constraints. None of the sources establishes that comparison for BOT 2.1. No local performance evidence was inspected. This report makes no claim that either philosophy possesses alpha.

The user-specified philosophies are:
- A: market observations → neural model → buy/sell/hold/action.
- B: observations → representation → forecasts/state → uncertainty → abstention → opportunity/risk estimates → controlled decision → independent authorization → execution.

These are research descriptions, not executable contracts. A need not mean reinforcement learning; it could use supervised action labels or decision-focused losses. B need not mean independently trained components. Joint training and separate operational responsibilities can coexist. Conversely, the sequence written for B need not be a strictly linear computation: uncertainty about opportunity can depend on costs and risk, while abstention may concern data validity as well as forecasts.

## Distinguishing the seven responsibilities

The following definitions are analytical distinctions made in this report, not prescribed modules or schemas.

| Responsibility | Scientific question | Evidence needed | What it does not establish |
|---|---|---|---|
| Prediction | What observable outcome/state is expected, for what target and horizon? | Properly defined target, causal information set, predictive error and distributional assessment | Positive net opportunity or permission |
| Uncertainty | How reliable are those estimates and what variation remains? | Calibration/coverage, sharpness, subgroup/time stability, missingness and shift assessment | Guaranteed future correctness or a maximum realized loss |
| Opportunity estimation | Is an available action economically worthwhile under explicitly stated assumptions? | Connection between forecasts and net outcomes; sensitivity to costs, feasibility and alternative actions | Authorization or an assured fill |
| Risk estimation | What adverse outcomes and exposures could follow? | Tail/dependence/model-risk analysis and uncertainty about those estimates | Enforcement of an acceptable risk budget |
| Trade decision | Which permitted candidate action, including inaction, is preferred under an objective? | Objective justification and decision-quality evidence | Authority to change permissions or limits |
| Risk authorization | Is the candidate admissible under independently governed constraints and current operational state? | Evidence of control ownership, independence and enforceability | Prediction of profitability |
| Execution | How are authorized intentions realized and reconciled with actual venue state? | Operational correctness and observations of actual outcomes | A new economic mandate or reliable predictive model |

Prediction confidence, action probability, and probability of profit are distinct. A softmax buy score is not automatically any of the latter two. Policy randomization can express an action distribution without estimating epistemic uncertainty. A model can be uncertain but economically useful, or predict direction accurately while costs make the opportunity unfavorable. These are conceptual counterexamples, not a proposed strategy.

Aleatoric uncertainty concerns variability conditional on the represented information; epistemic uncertainty concerns limited knowledge/model estimation. The division depends on representation and assumptions and is not directly observable with certainty. Separate data-quality or timing invalidity should not be silently absorbed into a numerical confidence score. Likewise, risk estimation can share latent features with prediction, but shared representations create common-mode errors; logical separation alone does not make estimates statistically independent.

## Balanced comparison

The table states anticipated engineering tradeoffs and research hypotheses, not measured BOT 2.1 properties.

| Dimension | A: end-to-end action model | B: predictive intelligence system | Evidence needed to distinguish them |
|---|---|---|---|
| Objective alignment | Can optimize outcomes relevant to decisions rather than generic accuracy; reward/objective misspecification can propagate everywhere | Forecasts support multiple downstream objectives; optimizing forecasting alone may neglect decision-sensitive errors | Same information, cost assumptions and research budget; decision value alongside predictive measures [S01] |
| Interpretability | Actions can be behaviorally inspected, but reasons may be entangled in representation and objective | Intermediate quantities provide diagnostic checkpoints but can still be opaque or misleading | Faithful explanations, simple comparators, documented target semantics; decomposition alone is not interpretability [S11] |
| Calibration | Action logits need an explicit probabilistic meaning before calibration is meaningful | Forecast probabilities/distributions allow direct checks; adding a calibration stage creates estimation and maintenance burden | Held-out calibration and conditional/time-sliced evaluation for the relevant target [S02] |
| Failure isolation | Fewer explicit interfaces; distinguishing perception, objective and action failures is difficult | Local diagnostics may identify failures; interface mismatches and shared upstream faults remain | Attribution of failures with complete lineage rather than only final outcome [S07] |
| Testability | End-to-end behavior can be assessed; sparse/delayed outcomes can make diagnosis expensive | Components can be assessed separately; component success does not imply composed-system success | Component and whole-system evidence, including invalid-input and dependency scenarios |
| Auditability | A versioned policy with input/action records can be auditable even without semantic internals | Named intermediate decisions can aid reconstruction but increase records and version dependencies | Reconstructible reasons, data availability, versions, authority and outcomes |
| Risk governance | Learned penalties may trade safety against reward unless separately constrained | Explicit authorization responsibility is natural; a nominal gate may still be bypassable or depend on the same faulty data | Separation of authority from optimization and evidence of actual enforceability [S08–S10] |
| Model replacement | Policy replacement can alter many behaviors simultaneously | Swapping forecasts is easier in principle; equal schemas can conceal changed calibration/meaning | Compatibility evidence beyond shape/type matching |
| Shadow deployment | Action proposals can run without authority; hypothetical returns depend on unobserved fills and reactions | Forecasts and proposed decisions can both be compared in shadow; the same counterfactual limitation applies | Coverage of real input conditions and operational evidence; no claim that shadow proves realized profitability |
| Rollback | A prior policy is a clear artifact but its state and external actions complicate reversal | Individual versions may be restored, but incompatible combinations are a risk | Known compatible version sets, state ownership and reconciliation evidence |
| Research flexibility | Supports direct objective research but can couple studies to one objective and simulator | Reusable forecasts support multiple questions but invite repeated downstream tuning | A recorded research ledger and separation of evaluation from selection |
| Distribution shift | Policy may select actions outside logged support; adaptation can compound uncertainty | Forecast drift and calibration drift can be inspected separately, yet their detection may lag | Shift-specific evidence and limits of extrapolation [S03, S06] |
| Uncertainty/abstention | Can be jointly learned; hold is not necessarily an uncertainty rejection | Explicit abstention can be easier to audit but creates another selection mechanism | Risk–coverage behavior and post-selection calibration [S04, S05] |
| Human review | Policy-level review is possible; per-action review may be too slow | Intermediate estimates can aid review but overwhelm reviewers or induce automation bias | Defined scope, response time and competent interpretation; no assumption that a human click confers safety |
| Execution independence | Entirely possible when action output is a proposal; not inherent in end-to-end training | Expressly represented in B but still requires real permission separation | Demonstrated absence of unauthorized effects, not a diagram or Boolean label |

For table brevity, Snn means R17-Snn.

## What public research actually supports

Task-based end-to-end learning demonstrates that downstream objectives can matter more than generic prediction loss in particular optimization tasks [R17-S01]. It supports taking A seriously and challenges a simplistic argument that forecasting accuracy should settle architecture selection. It does not show that raw buy/sell outputs outperform structured forecasts in ES/NQ, nor that learned policies should own trading credentials.

SelectiveNet shows that rejection and prediction can be learned together, so abstention is not exclusive to B [R17-S04]. Research assessment must examine accepted-set error and coverage together: fewer accepted cases can mechanically make a model look better. Rejection can concentrate exposure in a narrow regime; whole-population calibration does not establish reliability on that selected subset. A hold action can reflect low opportunity, current constraints, or uncertainty; conflating those reasons defeats diagnosis.

Guo et al. demonstrate calibration problems and useful post-processing on their classification benchmarks [R17-S02]. Ovadia et al. show why in-distribution post-processing should not be treated as shift protection [R17-S03]. Thus neither action confidence nor a separate uncertainty component establishes permission. A calibration claim must name its event, horizon, population, period and procedure.

Nonexchangeable conformal methods address drift-related coverage degradation under stated conditions [R17-S05]. Their relevance is methodological, not a blanket guarantee for dependent market observations, conditional tails, selected trades, or path-dependent loss. Predictive interval coverage and a limit on account losses are different propositions.

Offline RL illustrates the extra concern that an optimized policy can prefer unsupported actions whose values are overestimated [R17-S06]. This is relevant if A is implemented as offline RL; it must not be attributed to every action classifier. B can also suffer counterfactual opportunity-estimation errors when forecasts are turned into actions.

The 2026 revision of Online Decision-Focused Learning extends investigation to evolving objectives and distributions [R17-S12]. It provides theoretical regret results and a knapsack demonstration under its assumptions. It does not establish market deployment readiness, cost realism, or safety. This current work reinforces that decision-focused research remains open rather than settling A versus B.

## Should a neural model ever directly possess trading authority?

“Direct authority” needs disambiguation.

1. **Producing an action proposal:** scientifically legitimate to research. An action output is not intrinsically more dangerous than a forecast if neither can create external effects.
2. **Operating automatically within an externally authorized mandate:** potentially defensible in principle, subject to independent validation and governance. Human review of every action is not a scientific necessity, and human latency can itself make review ineffective. This report grants no such permission.
3. **Unilateral authority to submit orders, alter risk constraints or approve itself without an independent enforceable boundary:** not supported by the evidence reviewed for BOT 2.1. A predictive or decision metric is not a justification for that authority.

This is a governance inference, not a theorem that neural networks are uniquely unsafe. The same issue applies to deterministic strategies. Risk authorization represents accountable control over consequences; a reward penalty or a self-reported confidence value is not equivalent to that control. CME's documented risk tools demonstrate separately administered pre-execution limits and permissions, but their existence neither guarantees a particular bot is protected nor specifies a complete bot design [R17-S09, R17-S10]. NIST provides voluntary lifecycle governance guidance, not a trading-specific approval or mandatory architecture [R17-S08].

Independence must be assessed in more than naming: who controls the constraints, whether the proposing model can modify them, whether shared information can corrupt both estimation and authorization, and whether failure can produce an external effect. Those are future evidence questions. No routing, thresholds, order handling, sizing, credentials, or execution algorithm is designed here.

## Evidence questions for later gates — not an experimental authorization

Before choosing between philosophies, later authorized work would need to answer:

- Are target, horizon, action meaning, uncertainty interpretation and objective documented sufficiently to distinguish prediction error from decision error?
- Does objective-aligned training add value under equal information and selection budgets, compared with credible simple and modular alternatives?
- Are estimates useful after costs and under uncertainty about costs, without substituting predictive scores for economic evidence?
- Does calibration remain informative in time slices, important regimes and the accepted subset? What uncertainty cannot be quantified reliably?
- Does abstention improve relevant outcomes without concealing harmful regime concentration or selection bias?
- Are evaluation and adaptation rules specified before outcomes are used for selection? Can apparent improvements be traced to repeated choices?
- Can input problems, model problems, calibration failures, decision failures and authorization failures be distinguished?
- Are dependencies and compatible versions identifiable enough to replace a model or restore a prior version without assuming external state is reversible?
- Does shadow observation establish operational compatibility while explicitly retaining uncertainty about fills, impact and feedback?
- Is human review assigned to decisions humans can competently and promptly assess, with visible limitations?
- Can either philosophy establish authorization independence and auditability with evidence rather than architecture labels?

These questions are not a test plan or permission to access protected results. All training, scoring, experimentation, OOS evaluation and deployment remain outside this report.

## Provenance, independence and freeze

This specialist read the current user request supplied in the attachment and public primary sources only. It did not read old R17 content, old R16/R18/R19, master synthesis, new sibling reports, the audit, frozen R1–R15, or the registry. This choice limits local specificity but preserves a genuinely independent first pass.

The pre-existing R17 file was copied without content inspection to R17_PRE_BATCH2_COORDINATOR_DRAFT.md. The independently authored report replaces only R17_DECISION_ARCHITECTURE.md. The preservation copy is historical material, not a research source. The two original/copy hashes were checked before replacement.

Only research-document files in docs/bot21_research/ were written by this specialist. No BOT 2.0 source, protected output, OOS, datasets, manifests, risk/execution code or credentials were accessed. No training, inference, tests, experiments, backtests, trading, broker connections, installations, environment changes or Git mutations occurred. Public web retrieval and document file operations were the only research activities beyond reading the supplied request.

The report is frozen upon final SHA-256 calculation, supplied to the coordinator outside the report to avoid a self-referential hash. It must not be rewritten to obtain agreement. R18 may criticize it. No R20 or X1–X8 work was performed.

## Sources

All accessed 2026-09-24. The 12 records below are unique works/documentation records; multiple URLs for a work do not increase the count. Search snippets and publisher/author abstracts were used where full text was unnecessary for the bounded claim; claims do not imply full-paper replication. No public source establishes BOT 2.1 performance.

### R17-S01
- Title: Task-based End-to-end Model Learning in Stochastic Optimization.
- Authors: Priya Donti, Brandon Amos, J. Zico Kolter.
- Year/venue: 2017; NIPS 30. Type/status: primary conference research, peer-reviewed.
- URL: https://proceedings.neurips.cc/paper/2017/hash/3fc2c60b5782f641f76bcefc39fb2392-Abstract.html
- Finding: Downstream task-based learning can outperform conventional modeling and black-box policy optimization in studied tasks.
- Limitation: Inventory, grid scheduling and energy storage applications; not ES/NQ or authority governance.
- BOT 2.1 relevance: Substantive reason to investigate objective alignment without assuming unrestricted autonomy.

### R17-S02
- Title: On Calibration of Modern Neural Networks.
- Authors: Chuan Guo, Geoff Pleiss, Yu Sun, Kilian Q. Weinberger.
- Year/venue: 2017; ICML, PMLR 70:1321–1330. Type/status: primary research, peer-reviewed.
- URL: https://proceedings.mlr.press/v70/guo17a.html
- Finding: Modern networks can be miscalibrated; temperature scaling was effective on many studied datasets.
- Limitation: Classification benchmarks, not a universal shifted-market calibration result.
- BOT 2.1 relevance: Output confidence needs independent interpretation and evaluation.

### R17-S03
- Title: Can You Trust Your Model's Uncertainty? Evaluating Predictive Uncertainty Under Dataset Shift.
- Authors: Yaniv Ovadia, Emily Fertig, Jie Ren, Zachary Nado, D. Sculley, Sebastian Nowozin, Joshua V. Dillon, Balaji Lakshminarayanan, Jasper Snoek.
- Year/venue: 2019; NeurIPS 32. Type/status: primary benchmark research, peer-reviewed.
- URL: https://papers.neurips.cc/paper_files/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html
- Finding: Uncertainty methods, including post-hoc calibration, can degrade under dataset shift.
- Limitation: Benchmark findings are not guarantees for market regimes.
- BOT 2.1 relevance: Shift reliability cannot be inferred from nominal calibration.

### R17-S04
- Title: SelectiveNet: A Deep Neural Network with an Integrated Reject Option.
- Authors: Yonatan Geifman, Ran El-Yaniv.
- Year/venue: 2019; ICML, PMLR 97:2151–2159. Type/status: primary research, peer-reviewed.
- URL: https://proceedings.mlr.press/v97/geifman19a.html
- Finding: Jointly learned prediction and rejection improved benchmark risk–coverage tradeoffs.
- Limitation: Selective prediction risk is not trading loss or a capital constraint.
- BOT 2.1 relevance: Abstention is compatible with end-to-end learning.

### R17-S05
- Title: Conformal prediction beyond exchangeability.
- Authors: Rina Foygel Barber, Emmanuel J. Candès, Aaditya Ramdas, Ryan J. Tibshirani.
- Year/venue: 2023; Annals of Statistics 51(2). Type/status: primary statistical research, peer-reviewed.
- URL/DOI: https://doi.org/10.1214/23-AOS2276 ; author text https://arxiv.org/abs/2202.13415
- Finding: Weighted/randomized extensions address coverage degradation under nonexchangeability.
- Limitation: Guarantees depend on mathematical conditions and do not guarantee selected-trade tails or profits.
- BOT 2.1 relevance: Makes assumptions behind uncertainty coverage explicit.

### R17-S06
- Title: Conservative Q-Learning for Offline Reinforcement Learning.
- Authors: Aviral Kumar, Aurick Zhou, George Tucker, Sergey Levine.
- Year/venue: 2020; NeurIPS 33. Type/status: primary research, peer-reviewed.
- URL: https://proceedings.neurips.cc/paper/2020/hash/0d2b2061826a5df3221116a5085a6052-Abstract.html
- Finding: Dataset-to-policy shift can cause value overestimation; conservative learning addresses it under studied assumptions.
- Limitation: Control benchmarks and theoretical conditions do not certify a financial policy.
- BOT 2.1 relevance: Highlights unsupported-action risk if an action model uses offline RL.

### R17-S07
- Title: Hidden Technical Debt in Machine Learning Systems.
- Authors: D. Sculley, Gary Holt, Daniel Golovin, Eugene Davydov, Todd Phillips, Dietmar Ebner, Vinay Chaudhary, Michael Young, Jean-François Crespo, Dan Dennison.
- Year/venue: 2015; NIPS 28. Type/status: primary systems experience paper, peer-reviewed conference.
- URL: https://proceedings.neurips.cc/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html
- Finding: Entanglement, feedback, dependencies and configuration create system-level maintenance risks.
- Limitation: Qualitative systems evidence, not a controlled A/B trading comparison.
- BOT 2.1 relevance: Neither fewer modules nor more boundaries guarantees maintainability.

### R17-S08
- Title: Artificial Intelligence Risk Management Framework (AI RMF 1.0).
- Author/organization: Elham Tabassi; NIST.
- Year/venue: 2023; NIST AI 100-1. Type/status: official voluntary framework; not a peer-reviewed experiment.
- URL/DOI: https://doi.org/10.6028/NIST.AI.100-1
- Finding: Organizes lifecycle risk work around governance, mapping, measurement and management.
- Limitation: Use-case agnostic and voluntary; no specific trading architecture or permission is established.
- BOT 2.1 relevance: Accountability and evaluation must extend beyond a model score.

### R17-S09
- Title: Pre-Trade Risk Management.
- Organization: CME Group.
- Year/venue: Undated live official documentation, checked in 2026. Type/status: primary exchange documentation; not academic peer review.
- URL: https://www.cmegroup.com/solutions/market-access/globex/trade-on-globex/pre-trade-risk-management.html
- Finding: Documents risk limits, permissions, monitoring and audit trails administered for market participants.
- Limitation: Access and protection depend on actual participant setup; not complete bot safety evidence.
- BOT 2.1 relevance: Illustrates separation between a trade-generating system and permission/risk administration.

### R17-S10
- Title: CME Globex Credit Controls (GC2), with What's New revision record.
- Organization: CME Group.
- Year/venue: Live documentation; revision record includes 2026-05-13. Type/status: primary exchange operational documentation; not academic peer review.
- URLs: https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/CME-Globex-Credit-Controls-Management.html ; https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/Whats-New.html
- Finding: Documents administrator-controlled pre-execution exposure/quantity settings and current weekday/weekend updates.
- Limitation: Clearing-level tooling does not establish which controls BOT 2.1 would have or guarantee prevention of all loss.
- BOT 2.1 relevance: Current through-2026 evidence that authority is a distinct operational concern.

### R17-S11
- Title: Stop explaining black box machine learning models for high stakes decisions and use interpretable models instead.
- Author: Cynthia Rudin.
- Year/venue: 2019; Nature Machine Intelligence 1:206–215. Type/status: scholarly Perspective, accepted journal publication; not an ES/NQ experiment.
- URL/DOI: https://doi.org/10.1038/s42256-019-0048-x
- Finding: Distinguishes inherent interpretability from potentially unfaithful explanations of black boxes.
- Limitation: Argument and examples do not prove interpretable models dominate this financial task.
- BOT 2.1 relevance: Intermediate outputs and saliency should not be mistaken for faithful reasons.

### R17-S12
- Title: Online Decision-Focused Learning.
- Authors: Aymeric Capitaine, Maxime Haddouche, Eric Moulines, Michael I. Jordan, Etienne Boursier, Alain Durmus.
- Year/venue: 2025 initial preprint; v3 revised 2026-03-07; arXiv 2505.13564.
- Type/status: primary academic preprint; peer-review status not established from consulted record.
- URL: https://arxiv.org/abs/2505.13564v3
- Finding: Studies evolving objectives/distributions with static/dynamic regret results and a knapsack example.
- Limitation: Assumption-dependent theory and a nonmarket application; no evidence of trading readiness.
- BOT 2.1 relevance: Keeps the decision-focused comparison current through 2026 without overstating maturity.
