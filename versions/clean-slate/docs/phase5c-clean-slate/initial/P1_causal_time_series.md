# P1 — Causal time-series evaluation methodology (initial first draft)

**Date:** 2026-09-24  
**Role:** P1, causal time-series evaluation  
**Independence statement:** This is an independent clean-slate first draft. The sole repository input consulted was `docs/BOT2_PHASE5C_TECHNICAL_INVENTORY.md`, used only to identify the declared experiment object and its technical dimensions. No historical Phase 5C protocol, scientific proposal or review, evaluation output, model output, protected dataset or outcome, or other repository document was consulted. This draft is a proposed methodology, not an adopted protocol or authorization to access data, execute models, score outcomes, trade, or implement changes.

## 1. Evaluation object and limits of what is known

The declared object is a future-market-state classification experiment for ES and NQ, with a feature row containing 24 inputs and model sequence length 8. The target horizons are 5, 15, and 30 minutes. The inventory lists WF1–WF4, multiple named contracts for each instrument, and a cross-market ablation. WF identifiers are names only: this draft assigns them no dates, chronological order, window geometry, or operational meaning.

This is a temporal prediction problem. For a prediction made at decision time (t), every input must be available to the system by (t), and every fitting or calibration operation must use only labels whose outcomes and data were available by its own fitting cutoff. Rolling-origin out-of-sample evaluation is a natural starting point because each forecast is made from observations preceding its origin; repeated test periods reduce dependence on one historically unusual period. These are established time-series evaluation concerns, not evidence that any particular split geometry is sufficient for this experiment [Tashman (2000)](https://doi.org/10.1016/S0169-2070(00)00065-0), [Cerqueira, Torgo & Mozetič (2020)](https://doi.org/10.1007/s10994-020-05910-7).

The inventory does not establish bar/row cadence, feature definitions or their raw-data windows, the target construction or exact label support, timestamp semantics and latency, session calendar, contract-roll treatment, split dates, sample counts, or whether features are generated on an instrument-specific or shared clock. Those are prerequisites for exact row counts and executable boundaries. No cadence, dates, or split proportions are assumed below.

## 2. Time and information-set semantics

Represent each example (i) by a decision/anchor time (t_i), instrument (a_i\in\{ES,NQ\}), contract (c_i), session (s_i), feature sequence (X_i\in\mathbb{R}^{8\times24}), and target (Y_{i,h}) for horizon (h\in\{5,15,30\}\) minutes. Use a single declared comparison clock for ordering (prefer a monotonic normalized UTC instant), while retaining source exchange and receipt timestamps and their provenance. Calendar/session labels are separate metadata, not substitutes for absolute time.

For each raw event (e), distinguish event time (v_e) (when the event is said to have occurred) from usable/availability time (a_e) (when the event was actually received and could enter the pipeline). A feature at anchor (t_i) may depend only on events with (a_e\le t_i), subject to an explicitly specified tie rule. If availability cannot be established from source timestamps, do not silently treat event time as availability: either exclude that source observation or apply a documented conservative delay. Every derived feature must inherit the latest availability of all its inputs. This is a point-in-time rule, not a claim that receipt timestamps in the inventory are complete or correctly interpreted.

For any transform learned from data (scaling, imputation parameters, feature selection, target thresholds if estimated, class weighting, model weights, calibration), fit it only on the currently permitted training/calibration segment. Deterministic row-local transforms can be shared only when they use no future or globally estimated information. Freeze feature definitions and split construction before opening the final test outcomes. The separation of model selection from final assessment matters because repeated adaptive choices consume test information even when the model never directly trains on test labels; this draft leaves the multiplicity/reporting policy for selection counts as an open protocol choice.

## 3. Feature and sequence dependency is not label dependency

Let feature row (r) at anchor (u) have raw-data support (F_r(u)\subseteq(-\infty,u]\), and let (L_r(u)=\inf F_r(u)) be its earliest raw dependency. Exact values are unknown until the feature registry’s definitions are inspected under an authorized later step. A sequence ending at (t_i) consists of the eight ordered feature rows (u_{i,0},\ldots,u_{i,7}=t_i). Its raw-input dependency begins at

\[
L_i^{X}=\min_{k=0}^{7} L_{r(i,k)}(u_{i,k}),\qquad
\text{and ends no later than }t_i.
\]

If—and only if—rows are equally spaced by an established cadence \(\Delta\), the eight anchors span (7\Delta) from first to last row. That span is not automatically the total feature lookback: rolling or stateful feature calculations can reach further into the past. With irregular anchors, use the observed timestamps and actual feature dependencies instead of converting eight rows into a nominal duration. If a sequence is assembled before splitting, its timestamps and row provenance still must satisfy the same causal rule.

Sharing historical inputs between training and later test *features* is expected in forward deployment: a test prediction may use the preceding seven rows and other old market history. That alone is not leakage. The critical condition is that no training label or fitted transformation consumes information unavailable at the training cutoff, and no test-time feature consumes information unavailable at its own decision time. A global pre-split scaler, imputer, feature selector, or future-informed feature table would violate this condition.

## 4. Label support, maturity, purge, and embargo

For each example and horizon, define the target’s **support interval** (I_{i,h}=[ell_{i,h},r_{i,h}]) as the complete set of future observations needed to determine its class, and its **maturity/availability time** (m_{i,h}) as when those observations and the resulting label are actually available to the evaluation pipeline. The names “5/15/30 minutes” establish horizon lengths but not whether a target is a point state at (t_i+h), a statistic over ((t_i,t_i+h]), a threshold-crossing event, or a label with delayed finalization. Thus neither (I_{i,h}) nor (m_{i,h}) can yet be made exact.

For a point-state target whose last required observation is exactly (h) after the anchor and is immediately available, a first-order expression is (m_{i,h}=t_i+h). For an interval statistic, use the actual right endpoint and receipt/finalization delay. Event-time endpoint equality needs a declared ordering convention; absent a reliable tie order, the conservative rule is that a label must mature strictly before the next segment’s origin.

At any fit origin (o), a training row is eligible for head (h) only if

\[
\text{(i) }t_i<o,\qquad \text{(ii) }m_{i,h}<o,\qquad
\text{(iii) its feature inputs and all fit-time transforms were available by their applicable cutoffs.}
\]

Condition (ii) is the row-level purge derived from label maturity: exclude every would-be training row whose label is unfinished at the new origin. For multiple heads trained jointly with a requirement that all labels be present, eligibility uses \(\max_h m_{i,h}<o\); if heads are fitted/evaluated independently, apply head-specific maturity. A conservative shared-row purge can therefore be longer than the horizon used by any single head, but it must be computed from label semantics and actual availability, never selected as an unexplained fixed minute count.

More generally, for a non-forward split or any training/evaluation arrangement where training examples can lie on either side of a held-out block, purge training example (i) if its label support intersects any held-out label support:

\[
P_h=\{i\in Train:\ I_{i,h}\cap(\cup_{j\in Eval}I_{j,h})\ne\varnothing\}.
\]

This interval rule is exact once supports and endpoint conventions are known. In strictly forward-only walk-forward, no post-test examples are allowed into the training set, so the main boundary control is maturity at the test origin; a separate **post-test embargo** is not required for causality in that split. Embargo is a distinct optional exclusion of observations immediately after a held-out block, relevant only if a design later admits post-test observations to training or documents a residual/serial-dependence concern. Its duration cannot be inferred from the given horizons: it would require a stated dependence estimand and a data-only selection procedure confined to training/validation. Purging addresses direct label-support overlap; embargo does not repair future-informed features, global preprocessing, or an otherwise nonchronological evaluation.

If observations are on a regular cadence \(\Delta\), a purely horizon-based row-count approximation would be \(k_h=\lceil h/\Delta\rceil\) steps for a point target, adjusted for the chosen endpoint convention and observed label availability. This is only a derived convenience after cadence and target endpoint semantics are fixed; timestamp maturity remains authoritative. Missing rows or irregular event times invalidate a simple row-count purge.

## 5. Chronological fit, validation, calibration, and test

For each outer evaluation unit, define ordered cutoffs (O_0<O_1<O_2<O_3<O_4) (the actual instants or dates are deliberately unspecified). A defensible locked-origin sequence is:

1. **Fit and model-selection training:** use only observations before (O_0) whose required labels have matured by (O_0). Fit candidate model parameters and learned preprocessing here.
2. **Validation:** generate predictions at origins in ([O_0,O_1)) from information available at each origin. Validate choices on labels only after maturity. If validation is used to choose features, architecture, epoch/stopping point, or hyperparameters, record the number and scope of adaptive decisions; do not reuse these observations as the final test.
3. **Final pre-calibration fit:** after the selected design is frozen and the validation labels used for selection have matured, refit the selected model and preprocessing on the permitted historical training-plus-validation observations at a declared origin (O_1). This refit schedule is a design choice; it must be identical across compared candidates.
4. **Calibration:** make predictions over a later calibration interval ([O_1,O_2)) using the frozen model. Fit any probability-calibration mapping only when the interval’s labels have matured. With a calibrated classifier, the mapping and class mapping are selected using this interval alone. Calibration data are not model-training data for this locked test. If operational requirements instead call for refitting the model after calibration, the calibration mapping must be estimated for that refitted model using a separate later calibration history.
5. **Final test:** after calibration labels have matured and all decisions are locked, evaluate forecasts made at origins in ([O_2,O_3)), using the frozen model and calibration map. Do not alter features, thresholds, models, or split rules in response to this test. Labels can be read after their individual maturities; report a test result only for rows with complete outcomes.

This provides a simple isolated locked test for one outer interval. Repeated rolling-origin evaluation can repeat the complete sequence at multiple successive origins, with each test interval later in time than its own fit/validation/calibration data. If the scientific aim is ongoing periodic refitting, define an explicit refit schedule and calibration-refresh schedule; the test simulation must reproduce them. Do not pool predictions from folds that were generated using incompatible information sets without identifying those regimes.

For the declared labels WF1–WF4, propose only that each be a separately documented outer chronological evaluation unit with exact start/end instants, instrument/contract membership, and internal train/validation/calibration/test cutoffs. Whether WF1–WF4 are four distinct test eras, four complete rolling cycles, or some other structure remains unresolved. Do not infer dates or make the units overlap/disjoint until the owner specifies their meaning. If they are intended as distinct periods, report per-unit outcomes as well as any predeclared aggregate; later WF outcomes must not influence earlier decisions.

Rolling-origin fits may use either an expanding history or a fixed-width rolling training window. Tashman’s review treats fixed versus rolling windows, coefficient updating/recalibration, multiple test periods, and origins as material choices; the design must state which behavior is simulated, rather than conflating a rolling origin with automatic retraining [Tashman (2000)](https://doi.org/10.1016/S0169-2070(00)00065-0). For potentially non-stationary series, repeated temporally ordered out-of-sample periods are a reasonable default to assess temporal variation; the empirical comparison by Cerqueira et al. found that temporally ordered out-of-sample methods were most accurate in their non-stationary settings, while also finding no universally settled estimator [Cerqueira et al. (2020)](https://doi.org/10.1007/s10994-020-05910-7). Standard random K-fold is not the default here: time-series dependence makes its validity conditional on assumptions that should not be presumed for this market task [Bergmeir, Hyndman & Koo (2018)](https://doi.org/10.1016/j.csda.2017.11.003).

## 6. ES/NQ panel, contracts, and cross-market synchronization

Treat an example’s identity as a keyed panel row, not merely a timestamp: at minimum instrument, contract, anchor, and source/session identity must remain attached. ES and NQ observations at a common wall-clock time are not necessarily simultaneous observations of the same information set. Cross-market features should be reconstructed **as of the prediction decision time**: for each source market, include only source values actually available by the target anchor. A source value observed after that anchor cannot be backfilled into the target row even if it has the same nominal bar label. A finite staleness threshold, alignment tolerance, and handling of source-market closure must be declared; none is supplied by the inventory.

High-frequency finance literature documents that nonsynchronous observations and interpolation choices can make conventional synchronized covariance estimates unreliable. That supports making the synchronization rule explicit; it does not dictate one particular alignment method for this classifier [Hayashi & Yoshida (2005)](https://doi.org/10.3150/bj/1116340299). If the task uses a regular grid, establish a canonical anchor clock and causal as-of sampling rule, record source age at every join, and retain missing/stale indicators. If it instead uses irregular event-time rows, define exactly which instrument owns an anchor and how each other stream is queried at that instant. Compare results only under the same synchronization rule. Do not infer that ES leads NQ or vice versa.

Contracts must not be silently pooled as if identical continuous observations. Split chronology by actual event/anchor timestamps; preserve contract ID; state whether evaluation concerns future data for contracts already represented in training or generalization to unseen contracts. The latter requires grouping/holding out contract IDs in addition to forward time, which answers a different question from normal future deployment. At a roll boundary, do not stitch feature sequences, price changes, or target windows across contracts unless an explicit causal adjustment and mapping policy exists. Even when adjacent contracts overlap in calendar time, both are distinct instruments for provenance. Aggregate across contracts only after the per-contract samples and boundary rules are defined.

## 7. Session boundaries, missing data, and elapsed time

Trading session labels and boundaries must come from a specified exchange calendar with timezone and daylight-saving handling. The inventory identifies raw `session_id` and timestamps but does not provide calendar rules. A model sequence may either reset at session boundaries or carry prior-session rows with elapsed-time/session-transition information; either is a design choice and should reflect intended deployment. The safest provisional eligibility rule is to disallow a sequence across a session or contract discontinuity unless the production feature semantics intentionally carry state across that boundary and can encode the discontinuity causally. Count and document rows lost under the rule before fixing split sizes.

Do not equate missing clock intervals with observed flat prices. For each stream, classify absent data as expected closure, no event/trade, feed gap, timestamp failure, or unknown; the available raw feed may not distinguish them. A feature row is eligible only under a predeclared missingness policy. Permitted options include excluding incomplete anchors, using bounded causal last-observation carry with explicit age/staleness and missing indicators, or causal imputation fitted on training only. Unbounded forward fill across a market closure, session break, contract roll, or unrecovered feed gap can make stale values appear current. Never backfill from a later observation. Report missingness and exclusions by instrument, contract, session, and split so a model cannot appear strong by silently evaluating only convenient periods.

If the model consumes eight consecutive *rows* on an irregular grid, equal row counts do not imply equal elapsed-time context. Either define an actual fixed-duration sampling grid and its causal aggregation/empty-bin behavior, or preserve irregular timestamps/elapsed-time metadata and make the model’s intended interpretation of the sequence explicit. This choice cannot be resolved without feature cadence and model-input semantics.

## 8. Boundary eligibility and auditable construction

Construct candidate anchors independently inside the declared instrument/contract/session policy, then evaluate these predicates per row and per horizon:

```text
eligible(i, h, origin o):
  anchor i belongs to this split's permitted population
  all 8 feature rows exist in order and pass boundary policy
  every raw event used by those rows was available by its row's anchor
  all cross-market inputs satisfy as-of and staleness rules at anchor i
  all preprocessing values used for i were fitted only on permitted history
  label support and maturity are defined for (i,h)
  if i is used for fit: label maturity m[i,h] < o
  if i is used for evaluation: prediction is generated at i before label maturity
  if i is used for reporting: the complete outcome is eventually observed
```

An implementation should retain an exclusion reason for every candidate row (insufficient sequence, boundary crossing, stale/missing source, unavailable timestamp, label not mature, or incomplete eventual outcome). Exact boundary row counts then follow from records and declared predicates, not a hand-entered time buffer. For any future non-forward split, audit pairwise label-support intersections and apply the interval purge definition above.

## 9. Decisions required before this becomes an executable protocol

1. Confirm anchor clock and actual cadence (fixed, event-based, mixed, or irregular), the timezone/calendar source, and whether anchors are shared across ES/NQ.
2. Define availability semantics for event, exchange, and receive timestamps, including tie ordering, timestamp corrections, latency, and behavior when receipt availability is unknown.
3. Define all 24 feature computations and lookback/state requirements, sequence construction order, session reset/carry policy, missingness policy, and cross-market as-of tolerance/freshness rules.
4. Define each 5/15/30-minute target’s exact mathematical support, endpoint inclusivity, price/state source, class thresholds, and label-finalization delay.
5. Specify contract-roll stitching/adjustment policy and whether the claim is future-time generalization within represented contracts or unseen-contract generalization.
6. Give WF1–WF4 their intended meaning, chronological dates, split geometry, per-fold training window/refit cadence, minimum training history, and whether outer test windows overlap.
7. Decide the calibration method and whether one locked model is retained through each test interval or retraining occurs; if retraining, define a calibration refresh procedure.
8. Freeze selection scope, sample/label inclusion rules, and any test-result aggregation/inference plan before reading test outcomes.

These are protocol-completion requirements, not reasons to invent defaults. Once resolved, the split and eligibility algorithm can be specified in timestamps and verified against label support; until then, exact purge or embargo durations and eligible boundary rows are indeterminate.

## References

- Tashman, L. J. (2000). “Out-of-sample tests of forecasting accuracy: an analysis and review.” *International Journal of Forecasting*, 16(4), 437–450. https://doi.org/10.1016/S0169-2070(00)00065-0 — rolling origins, multiple test periods, split/window choices, and updating versus recalibration are design dimensions.
- Cerqueira, V., Torgo, L., & Mozetič, I. (2020). “Evaluating time series forecasting models: An empirical study on performance estimation methods.” *Machine Learning*, 109, 1997–2028. https://doi.org/10.1007/s10994-020-05910-7 — empirical comparison of time-series estimation methods; temporally ordered out-of-sample estimates performed best in their non-stationary settings, without establishing one universal procedure.
- Bergmeir, C., Hyndman, R. J., & Koo, B. (2018). “A note on the validity of cross-validation for evaluating autoregressive time series prediction.” *Computational Statistics & Data Analysis*, 120, 70–83. https://doi.org/10.1016/j.csda.2017.11.003 — ordinary K-fold validity depends on model/error assumptions, so it is not automatically transferable to a dependent, potentially non-stationary market series.
- Hayashi, T., & Yoshida, N. (2005). “On covariance estimation of non-synchronously observed diffusion processes.” *Bernoulli*, 11(2), 359–379. https://doi.org/10.3150/bj/1116340299 — regular synchronized sampling and interpolation choices can affect estimates with nonsynchronous high-frequency observations; supports explicit synchronization semantics, not a unique classifier join rule.
