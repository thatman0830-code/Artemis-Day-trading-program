# BOT 2.1 R20 — Architecture comparison matrix

Provisional experimental priority, not expected trading performance. No implementation, runtime measurement, training, inference or benchmark occurred. All resource/difficulty statements are qualitative hypotheses from R01/R14/R15, not measured host facts. Frozen literature references resolve through BOT21_RESEARCH_SOURCE_REGISTRY.md. Every family remains subject to clean-source, temporal-contract, validation and BOT 2.0 isolation gates.

## Priority overview

| Family | Category |
|---|---|
| Naïve majority/persistence/transition/zero-return | FOUNDATIONAL_BASELINE |
| Logistic regression / ridge / lagged linear | FOUNDATIONAL_BASELINE |
| Small MLP / historical A1 | FOUNDATIONAL_BASELINE |
| Small causal CNN / TCN / historical A2 | PRIMARY_PROTOTYPE_CANDIDATE |
| Simple GRU / LSTM | SECONDARY_PROTOTYPE_CANDIDATE |
| Compact PatchTST | EXPLORATORY_CANDIDATE |
| Generic Transformer / TFT | DEFER |
| iTransformer | DEFER |
| TimesNet | DEFER |
| Structured state-space / S4 | EXPLORATORY_CANDIDATE |
| Mamba-style selective SSM | EXPLORATORY_CANDIDATE |
| TiDE / N-BEATS / N-HiTS | DEFER |
| TimeMixer / explicit multiscale encoder | DEFER |
| Separate encoders / cross-attention fusion | DEFER |
| CNN/RNN/attention/SSM hybrids | DEFER |
| Deep / architecture ensembles and stacking | DEFER |
| Regime specialists / MoE | DEFER |
| Foundation models / pretrained financial models | DEFER |
| Online self-modifying / RL execution / autonomous trading | NOT_CURRENTLY_JUSTIFIED |

## Reading the dossiers

Each priority is BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS: MODERATE confidence for simple controls/compact temporal comparison, LOW for exploratory incremental value, UNKNOWN for actual ES/NQ advantage and workload measurements. Architecture definitions have foundational or primary benchmark support; they are not financial validation. Requiring a comparator does not promise the candidate wins. Historical A1/A2 are never approved to load, import or run. No neural experiment may proceed with an undefendable temporal contract.

## Naïve majority/persistence/transition/zero-return

**FOUNDATIONAL_BASELINE**

| Dimension | Assessment |
|---|---|
| Scientific question | Is there information beyond prevalence, no change and last eligible state? |
| Inductive bias | Persistence and training-period frequencies |
| Reason for inclusion or deferral | Defines task-matched nulls |
| Evidence | R03/R07/R10; S04 |
| Counter-evidence | Some are inapplicable to continuous/distribution targets; immature previous labels leak |
| Data requirement | Eligible training frequencies or last mature target; identity-aligned origins |
| Compute requirement | Minimal storage/compute |
| Parameter/complexity risk | Low; transition bins still add degrees of freedom |
| Nonstationarity risk | Prevalence/transitions can change |
| Uncertainty compatibility | Empirical probabilities/quantiles need calibration assessment |
| Multi-task compatibility | Separate simple reference per task |
| ES/NQ relevance | Essential controls, no edge assumption |
| Expected training difficulty | Low; maturity/transition eligibility matters |
| Expected inference difficulty | Low; do not query future labels |
| Simpler model it must beat | Task-matched unconditional forecast |
| Evidence that would eliminate it | Drop only an inapplicable or invalid control; never drop merely because it is hard to beat |

## Logistic regression / ridge / lagged linear

**FOUNDATIONAL_BASELINE**

| Dimension | Assessment |
|---|---|
| Scientific question | Do static or lagged linear effects improve the null? |
| Inductive bias | Linear conditional relationships with regularization |
| Reason for inclusion or deferral | Strong simple comparator; challenges complexity |
| Evidence | R01/R10/R12; S04/S85 |
| Counter-evidence | Misses nonlinearities; regularization and lag choices can overfit |
| Data requirement | Same causal features/history as the comparison; training-only scaling |
| Compute requirement | Low to moderate with feature width |
| Parameter/complexity risk | Low to moderate as lags/features grow |
| Nonstationarity risk | Coefficients and residual scale age |
| Uncertainty compatibility | Logistic probabilities or separate residual/quantile calibration; no inherent shift guarantee |
| Multi-task compatibility | Independent heads or limited shared linear model |
| ES/NQ relevance | Direct future comparator only, not proof from generic benchmarks |
| Expected training difficulty | Low; objective/scaler fit and regularization selection |
| Expected inference difficulty | Low, generally; actual latency unmeasured |
| Simpler model it must beat | B0/B1 naïve controls |
| Evidence that would eliminate it | Stop predictive-use claim for unstable/no-repeatable incremental value; retain as diagnostic control |

## Small MLP / historical A1

**FOUNDATIONAL_BASELINE**

| Dimension | Assessment |
|---|---|
| Scientific question | Do static nonlinear interactions help beyond linearity? |
| Inductive bias | Compact nonlinear feature mixing |
| Reason for inclusion or deferral | Separates static nonlinearity from temporal modeling |
| Evidence | R01/R12; audit A1 description is historical only |
| Counter-evidence | Can fit noise; A1's existing three targets and artifacts carry no fresh authority |
| Data requirement | Same approved observation view and origins as linear controls |
| Compute requirement | Low to moderate; width-dependent |
| Parameter/complexity risk | Moderate; hidden width and heads count |
| Nonstationarity risk | No inherent drift protection |
| Uncertainty compatibility | Probabilistic heads plus separate calibration |
| Multi-task compatibility | Compatible, but single-task controls remain necessary |
| ES/NQ relevance | Plausible control; existing A1 not executed or imported |
| Expected training difficulty | Low to moderate; bounded seeds/regularization |
| Expected inference difficulty | Low expected at compact scale, unmeasured |
| Simpler model it must beat | Logistic/ridge |
| Evidence that would eliminate it | Stop candidate if gains disappear under repeat seeds/forward blocks or calibration degrades; A1 remains historical |

## Small causal CNN / TCN / historical A2

**PRIMARY_PROTOTYPE_CANDIDATE**

| Dimension | Assessment |
|---|---|
| Scientific question | Does local causal temporal order add information? |
| Inductive bias | Finite causal convolution, dilation and parameter sharing |
| Reason for inclusion or deferral | Minimal temporal question relative to static controls |
| Evidence | R01/S01, with S04 baseline counterweight |
| Counter-evidence | Generic sequence preprint does not establish futures superiority; padding/stride risk |
| Data requirement | Approved ordered sequences; explicit receptive field, gaps and boundary rules |
| Compute requirement | Low to moderate compact training; kernel/context-dependent |
| Parameter/complexity risk | Moderate; dilation/width/context search counts |
| Nonstationarity risk | Fixed filters can age; shocks differ from local motifs |
| Uncertainty compatibility | Quantile/probability heads compatible; calibration external |
| Multi-task compatibility | Shared trunk possible; per-task negative transfer monitored |
| ES/NQ relevance | No direct winner evidence; A2 only historical reference |
| Expected training difficulty | Moderate; verify temporal dependencies in a later authorized phase |
| Expected inference difficulty | Potentially low; buffering/preprocessing included later |
| Simpler model it must beat | Lagged linear and small MLP on matched information |
| Evidence that would eliminate it | Eliminate family preference if local ordering adds no repeatable value, boundary sensitivity dominates, or calibration/latency fails |

## Simple GRU / LSTM

**SECONDARY_PROTOTYPE_CANDIDATE**

| Dimension | Assessment |
|---|---|
| Scientific question | Does recurrent state improve over finite local context? |
| Inductive bias | Gated compressed sequential memory |
| Reason for inclusion or deferral | Distinct temporal hypothesis with one representative, not both by default |
| Evidence | R01/S02; R13 retention tradeoffs |
| Counter-evidence | Sequential training, forgetting and hidden-state contamination; no ES/NQ head-to-head benefit |
| Data requirement | Ordered sequences with explicit session/contract/fold resets and allowed continuation |
| Compute requirement | Moderate sequential fit; compact streaming state |
| Parameter/complexity risk | Moderate; state size/layers increase search |
| Nonstationarity risk | State and weights can carry obsolete dynamics |
| Uncertainty compatibility | Distributional heads compatible, not self-calibrated |
| Multi-task compatibility | Compatible; state sharing can couple errors |
| ES/NQ relevance | Useful contrast to TCN, no inferred edge |
| Expected training difficulty | Moderate; traversal/state/reset sensitivity |
| Expected inference difficulty | Low to moderate expected, serial update; unmeasured |
| Simpler model it must beat | Small TCN plus matched lagged/static controls |
| Evidence that would eliminate it | Stop if state leakage/reset dependence, unstable seeds, or no stable forward gain over TCN |

## Compact PatchTST

**EXPLORATORY_CANDIDATE**

| Dimension | Assessment |
|---|---|
| Scientific question | Does patch-based longer available context help? |
| Inductive bias | Subseries patches and shared channel-independent attention |
| Reason for inclusion or deferral | Tests attention/context without committing to giant models |
| Evidence | R01/S05; R14-S07 |
| Counter-evidence | Channel independence may miss interactions; patch/horizon benchmarks unlike futures |
| Data requirement | Enough independent episodes for longer context; fully available patches |
| Compute requirement | Moderate to high; patch count reduces attention tokens |
| Parameter/complexity risk | Moderate to high; patch/stride/depth search |
| Nonstationarity risk | Long history may import obsolete relationships |
| Uncertainty compatibility | External probabilistic head/calibration possible; original benchmark outputs are not guarantees |
| Multi-task compatibility | Possible adapted heads; adds design burden |
| ES/NQ relevance | Generic long-horizon support only |
| Expected training difficulty | Moderate to high; context/search and fair matching |
| Expected inference difficulty | Moderate, context-dependent; end-to-end unmeasured |
| Simpler model it must beat | Longer-context TCN and lagged linear on same information |
| Evidence that would eliminate it | Defer unless context has value; stop if gain is only extra history/capacity or unstable patch selection |

## Generic Transformer / TFT

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Do global interactions or gated covariates add beyond compact attention? |
| Inductive bias | Attention; TFT mixes recurrence, gating and attention |
| Reason for inclusion or deferral | Only distinct interaction/known-covariate question earns inclusion |
| Evidence | R01/S03/S08–S11 |
| Counter-evidence | S04 simple baselines challenge broad superiority; TFT attention is not causal explanation |
| Data requirement | Defensible token and covariate availability, larger sample support |
| Compute requirement | High relative to small controls; implementation-dependent |
| Parameter/complexity risk | High; many interacting components |
| Nonstationarity risk | Global context and learned covariates can drift |
| Uncertainty compatibility | TFT quantile structure useful but calibration still empirical |
| Multi-task compatibility | Compatible, extra weighting/heads add choices |
| ES/NQ relevance | No direct intraday net evidence |
| Expected training difficulty | High; masks, component attribution and search |
| Expected inference difficulty | Moderate to high; memory/cold path uncertain |
| Simpler model it must beat | Compact patch attention/TCN and simple controls |
| Evidence that would eliminate it | Stop if extra mechanisms lack ablated incremental evidence or precision/latency/resource budget is untenable |

## iTransformer

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Does explicit cross-variate attention beat simple joint or separate views? |
| Inductive bias | Variables as tokens; temporal history projected per variable |
| Reason for inclusion or deferral | Competing interaction hypothesis to channel independence |
| Evidence | R01/S06; R14-S08 |
| Counter-evidence | Nominal alignment may conceal delay; correlation may not transfer |
| Data requirement | Synchronized eligible variates with known scales/missingness and same history |
| Compute requirement | Moderate to high depending channel count/history |
| Parameter/complexity risk | Moderate to high; interaction capacity |
| Nonstationarity risk | Cross-market correlations and lead/lag can change |
| Uncertainty compatibility | External uncertainty heads/calibration required |
| Multi-task compatibility | Compatible, not proven positive transfer |
| ES/NQ relevance | ES/NQ question relevant, supporting benchmarks generic |
| Expected training difficulty | Moderate to high; alignment and causal ablations |
| Expected inference difficulty | Moderate, channel/history-dependent |
| Simpler model it must beat | Simple additive ES/NQ view, independent models and compact PatchTST |
| Evidence that would eliminate it | Stop if cross-variate benefit vanishes with causal alignment, missingness accounting or simple fusion |

## TimesNet

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Do stable causal periodic structures add information? |
| Inductive bias | Period selection and two-dimensional within/between-period convolution |
| Reason for inclusion or deferral | Tests a specific periodicity hypothesis |
| Evidence | R01/S07; R04 notes seasonality |
| Counter-evidence | R04/R13: periodic patterns change; shocks and detection selection |
| Data requirement | Causal period estimation, calendar identity and adequate independent cycles |
| Compute requirement | Moderate to high; multiple period branches |
| Parameter/complexity risk | Moderate to high period/branch search |
| Nonstationarity risk | High sensitivity to changing session/volatility cycles |
| Uncertainty compatibility | Adaptable heads, calibration external |
| Multi-task compatibility | Possible; not a demonstrated futures benefit |
| ES/NQ relevance | Volatility seasonality is not directional alpha |
| Expected training difficulty | Moderate to high; period provenance |
| Expected inference difficulty | Moderate, branch-dependent |
| Simpler model it must beat | Causal session/risk controls, TCN and simple multiscale view |
| Evidence that would eliminate it | Stop if periods are unstable, future-estimated, or add no value beyond calendar/context |

## Structured state-space / S4

**EXPLORATORY_CANDIDATE**

| Dimension | Assessment |
|---|---|
| Scientific question | Does efficient state representation help when long context is informative? |
| Inductive bias | Structured recurrent state with efficient sequence operations |
| Reason for inclusion or deferral | Distinct long-context efficiency question |
| Evidence | R01/S15; R15 systems qualifications |
| Counter-evidence | Specialized kernels and offline/streaming mismatch; asymptotics may not matter |
| Data requirement | Causal long history and explicit scan/cache/reset ownership |
| Compute requirement | Potential linear/structured scaling; actual memory/kernel fit unknown |
| Parameter/complexity risk | Moderate to high model/runtime complexity |
| Nonstationarity risk | State can retain stale relationships |
| Uncertainty compatibility | Heads can encode distributions; no intrinsic reliable uncertainty |
| Multi-task compatibility | Compatible with heads, no proven transfer |
| ES/NQ relevance | Generic sequence evidence; ES/NQ relevance conditional on useful history |
| Expected training difficulty | High relative to TCN if specialized operators required |
| Expected inference difficulty | Potential efficient state updates; local latency unknown |
| Simpler model it must beat | Matched-context TCN/GRU and lagged linear |
| Evidence that would eliminate it | Defer if timing/kernel qualification absent; stop if no long-context gain or parity/reset failure |

## Mamba-style selective SSM

**EXPLORATORY_CANDIDATE**

| Dimension | Assessment |
|---|---|
| Scientific question | Does input-selective state add useful long-context information? |
| Inductive bias | Input-dependent state selection |
| Reason for inclusion or deferral | At most one SSM representative may earn conditional study |
| Evidence | R01/S16; R02/R15 |
| Counter-evidence | Language/general sequence scaling is not short-window financial advantage |
| Data requirement | Same causal long-context identity; no bidirectional/offline leakage |
| Compute requirement | Potential favorable scaling, specialized implementation cost |
| Parameter/complexity risk | High relative to controls; selective state/kernel choices |
| Nonstationarity risk | Selection may chase noise or suppress rare events |
| Uncertainty compatibility | External calibrated probabilistic heads |
| Multi-task compatibility | Possible, with per-task controls |
| ES/NQ relevance | No direct ES/NQ evidence |
| Expected training difficulty | High until exact host/operator qualification |
| Expected inference difficulty | Potentially efficient streaming; cache/precision behavior unknown |
| Simpler model it must beat | S4 or simpler GRU/TCN under the actual question |
| Evidence that would eliminate it | Stop if selective mechanism lacks gain versus simpler state or technical/parity burden outweighs evidence |

## TiDE / N-BEATS / N-HiTS

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Do compact dense or multirate forecasts add beyond the small MLP? |
| Inductive bias | Residual dense projections, basis/interpolation and multirate structure |
| Reason for inclusion or deferral | Potential alternative control if the basic dense model leaves a specific question |
| Evidence | R01/S12–S14 |
| Counter-evidence | Smooth long-horizon competition tasks differ; projection width can grow |
| Data requirement | Fixed causal history and explicit multirate availability |
| Compute requirement | Low to moderate by architecture, not universally cheap |
| Parameter/complexity risk | Moderate; basis/horizon/width choices |
| Nonstationarity risk | Basis or smoothness can miss shocks |
| Uncertainty compatibility | Output adaptation/calibration needed |
| Multi-task compatibility | Possible; output/target fit must be explicit |
| ES/NQ relevance | Generic benchmark motivation only |
| Expected training difficulty | Moderate |
| Expected inference difficulty | Potentially low to moderate, unmeasured |
| Simpler model it must beat | Small MLP/lagged linear/TCN |
| Evidence that would eliminate it | Stop if no repeated incremental value, interpolation misses tails, or gains reflect unequal context |

## TimeMixer / explicit multiscale encoder

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Does multiscale mixing add beyond extra history alone? |
| Inductive bias | Fine/coarse mixing and decomposed scales |
| Reason for inclusion or deferral | Tests fusion only after additive completed-bar context is useful |
| Evidence | R06/S79; R14-S10 |
| Counter-evidence | Coarse inputs are redundant; future decomposition and unequal history confound |
| Data requirement | Completed and received coarse bars with explicit dependency spans |
| Compute requirement | Moderate to high |
| Parameter/complexity risk | Moderate to high scale/branch search |
| Nonstationarity risk | Periodicity and relevance of scales drift |
| Uncertainty compatibility | Calibrated heads possible |
| Multi-task compatibility | Multiple horizons/tasks possible but dependent |
| ES/NQ relevance | Generic forecasting; futures leads not decisive |
| Expected training difficulty | Moderate to high; aggregation/fairness |
| Expected inference difficulty | Moderate with aggregation overhead |
| Simpler model it must beat | Single-stream matched-history TCN and simple additive multiscale control |
| Evidence that would eliminate it | Stop if benefit disappears after history/capacity matching or aggregation causality fails |

## Separate encoders / cross-attention fusion

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Does preserving instrument structure then interacting help? |
| Inductive bias | Instrument-specific embeddings with intermediate fusion |
| Reason for inclusion or deferral | Attribution and asymmetric context hypothesis |
| Evidence | R14-S06–S09 |
| Counter-evidence | Two-instrument sample size, extra parameters and delays; attention not economic causality |
| Data requirement | Both legs causally available; instrument/scaling/coverage identities |
| Compute requirement | Moderate to high multiple branches |
| Parameter/complexity risk | High fusion/gate/branch choices |
| Nonstationarity risk | Conditional relations and missingness patterns drift |
| Uncertainty compatibility | Joint output must be calibrated; branch confidence not sufficient |
| Multi-task compatibility | Possible shared or distinct heads |
| ES/NQ relevance | Relevant hypothesis, no direct evidence of superiority |
| Expected training difficulty | High; fair comparison and semantic pairing |
| Expected inference difficulty | Moderate to high including waiting/fusion |
| Simpler model it must beat | Independent instrument models and simple early/late combination |
| Evidence that would eliminate it | Stop if branch gain vanishes with no extra history/capacity or causal synchronization |

## CNN/RNN/attention/SSM hybrids

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Are local and long-context biases complementary? |
| Inductive bias | Composed biases and parallel/serial branches |
| Reason for inclusion or deferral | Only an identified residual weakness justifies composition |
| Evidence | R01/R14; general architecture literature |
| Counter-evidence | Attribution ambiguity, component interactions and many trials |
| Data requirement | Approved component inputs with identical information budgets |
| Compute requirement | High relative to single compact members |
| Parameter/complexity risk | High |
| Nonstationarity risk | Multiple stale components and shared preprocessing |
| Uncertainty compatibility | Compatible, but calibration of composed output required |
| Multi-task compatibility | Possible; added interactions can cause negative transfer |
| ES/NQ relevance | No demonstrated ES/NQ complementarity |
| Expected training difficulty | High |
| Expected inference difficulty | Moderate to high; full pipeline measured later |
| Simpler model it must beat | Best eligible single member and simple late fusion |
| Evidence that would eliminate it | Stop if removing a branch does not hurt robust forward evidence or system cost exceeds defensible benefit |

## Deep / architecture ensembles and stacking

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Do good members have complementary forward errors? |
| Inductive bias | Prediction combination rather than nominal diversity |
| Reason for inclusion or deferral | Potential reliability/variance benefit after member evidence |
| Evidence | R14-S01–S05/R18 |
| Counter-evidence | Correlated bias, in-sample stacking, tail cofailure and extra selection |
| Data requirement | Comparable out-of-time member predictions with mature meta-labels |
| Compute requirement | Multiple fits/forward passes and separate calibration |
| Parameter/complexity risk | High search/meta-estimation cost |
| Nonstationarity risk | Weights/calibration/complementarity age |
| Uncertainty compatibility | Combined distribution must be calibrated; spread not a certificate |
| Multi-task compatibility | Compatible only with coherent targets/horizons |
| ES/NQ relevance | Complementarity unmeasured for ES/NQ |
| Expected training difficulty | Moderate to high; whole pipeline chronology |
| Expected inference difficulty | High relative to one member; parallel memory cost |
| Simpler model it must beat | Best eligible single model and fixed/equal-weight combination |
| Evidence that would eliminate it | Stop if covariance/tail failures lack stable complementarity or pooled calibration/resources deteriorate |

## Regime specialists / MoE

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Does causal specialization outperform a general predictor? |
| Inductive bias | Conditional routing and expert capacity |
| Reason for inclusion or deferral | Only repeatable conditional differences justify it |
| Evidence | R08/S93; R14-S11–S14 |
| Counter-evidence | Sparse support, hindsight regimes, gate collapse/starvation and hidden tuning |
| Data requirement | Sufficient independent episodes per causally defined state; unknown-state behavior |
| Compute requirement | Moderate to high; sparse activation is not low total storage |
| Parameter/complexity risk | High to very high |
| Nonstationarity risk | Routers can chase moving or rare states |
| Uncertainty compatibility | Per-route and pooled calibration/coverage required |
| Multi-task compatibility | Possible; task routing increases sparsity |
| ES/NQ relevance | No stable ES/NQ regime taxonomy or gain established |
| Expected training difficulty | High; gate and experts jointly selected |
| Expected inference difficulty | Unknown; dispatch overhead may dominate small batches |
| Simpler model it must beat | One general model with causal context and simple fixed fusion |
| Evidence that would eliminate it | Stop if expert support unstable, gate oracle/leakage, no conditional gain or tail failures concentrate; complex MoE not justified |

## Foundation models / pretrained financial models

**DEFER**

| Dimension | Assessment |
|---|---|
| Scientific question | Does transferred representation add beyond local simple supervised models? |
| Inductive bias | Broad pretraining and task-specific prompting/adaptation |
| Reason for inclusion or deferral | Only a provenance-compatible comparison can address transfer |
| Evidence | R02/S18–S23/S52–S57; R18-S05/S06 |
| Counter-evidence | Opaque corpora/shock overlap, vendor/preprint claims, benchmark/domain mismatch |
| Data requirement | Independently acceptable corpus/cutoff/checkpoint lineage plus future clean evaluation |
| Compute requirement | Often high storage/inference/adaptation; size-dependent |
| Parameter/complexity risk | High hidden pretraining/prompt/selection complexity |
| Nonstationarity risk | Broad patterns may fail under local market shifts |
| Uncertainty compatibility | Distributional outputs vary; independent calibration needed |
| Multi-task compatibility | Model-specific; adaptation may require new heads |
| ES/NQ relevance | Daily/monthly/equity/candle evidence does not prove intraday ES/NQ |
| Expected training difficulty | Low local zero-shot fit can conceal huge prior fit; fine-tuning high |
| Expected inference difficulty | Potential high; local exact workload unverified |
| Simpler model it must beat | Naïve/linear/compact supervised candidate on same allowed information |
| Evidence that would eliminate it | Do not enter with unknown provenance; stop if no robust incremental gain or unacceptable cost/latency; large deployment not justified |

## Online self-modifying / RL execution / autonomous trading

**NOT_CURRENTLY_JUSTIFIED**

| Dimension | Assessment |
|---|---|
| Scientific question | Would policy optimization add value under valid counterfactual support? |
| Inductive bias | Adaptive policy or direct decision objective |
| Reason for inclusion or deferral | No initial inclusion; retain as explicit scope boundary |
| Evidence | R17-S01/S06/S12 recognizes decision-focused questions |
| Counter-evidence | No admissible simulator/support/economics/authority evidence; user prohibits implementation/trading |
| Data requirement | Would require separately approved policy data, feedback and action-support evidence |
| Compute requirement | Potential very high; unbounded adaptive search not acceptable |
| Parameter/complexity risk | Very high |
| Nonstationarity risk | Feedback, unsupported actions and changing costs amplify drift |
| Uncertainty compatibility | Action probability is not profit probability or risk authorization |
| Multi-task compatibility | Possible conceptually, irrelevant to current permission |
| ES/NQ relevance | No BOT 2.1 action-oriented advantage established |
| Expected training difficulty | Very high/unknown |
| Expected inference difficulty | Unknown and authority-sensitive |
| Simpler model it must beat | Non-authoritative forecasts plus separately governed decision research |
| Evidence that would eliminate it | Stop immediately under current scope; any future study requires new authorization and independent support/economics/isolation evidence |

## Cross-family stopping and scope

An unknown source authority, future availability, protected exposure or authority inheritance closes the corresponding gate before scores can justify complexity. Lack of enough independent evidence leaves a candidate unestablished, not proven useless. Valid forecast improvements are distinct from eventual economic viability. No numerical thresholds, parameter counts, context length, ensemble weights, route conditions or task weights are specified. Giant variants of attention/foundation models, complex MoE and autonomous agents are NOT_CURRENTLY_JUSTIFIED; the deferred families describe narrower conditional hypotheses only.
