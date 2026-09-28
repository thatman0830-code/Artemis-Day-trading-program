# BOT 2.0 Phase 5C — Prospective Clean-Slate Scientific Evaluation Protocol

**Status:** `PROPOSED` · `NOT ADOPTED` · `NON-EXECUTABLE`  
**Version:** draft 0.1  
**Branch:** `bot2-phase5c-clean-slate-protocol`  
**Purpose:** reset only the scientific evaluation design.  
**Not authorized:** protected-data access/scoring, model execution, trading, implementation, resumption of paused Phase 5C work, or Phase 6.

## 1. Scope and technical object

This proposal governs only the prospective evaluation of the existing declared ES/NQ technical object identified in [`BOT2_PHASE5C_TECHNICAL_INVENTORY.md`](BOT2_PHASE5C_TECHNICAL_INVENTORY.md). The inventory and code-inspection addendum are factual and nonnormative. They record ES and NQ; the current A0 persistence, train-majority, and train-transition implementations; A1 and A2 code identities; target horizons 5, 15, and 30 minutes; three three-class target heads; WF1–WF4 identifiers; declared ablations; current v3 feature/target calculations; A2 input `[8,24]`; and its declared 7,417 parameter count without executing the model.

No architecture, feature, target, model training method, contract definition, or trading behavior is changed by this document. No new baseline, action mapping, portfolio, or transaction-cost strategy is added. Prior protocol lineage remains preserved as `HISTORICAL_NONAUTHORITATIVE` and is not the source of any scientific rule in this proposal.

## 2. Evaluation firewall and fail-closed gates

Until a separate formal independent review adopts a complete protocol, all protected OOS access remains closed. No data archive job, prediction generation, model inference, probability generation, scoring, P&L analysis, or order simulation is permitted by this proposal. Trading authority remains `NONE`.

Before an adopted protocol could authorize a future evaluation, each gate below must be closed prospectively without viewing protected results. If any gate is absent, ambiguous, or internally inconsistent, the runner must stop before protected data access and emit a machine-readable `PROTOCOL_PREREQUISITE_MISSING` reason with the missing field identifiers.

Required gate inputs:

1. A non-null immutable source dataset ID, source and normalized hashes, exact instruments/contracts, coverage interval, schema version, code commit, and data license/usage scope.
2. Identity/hash confirmation of current v3 feature code/registry and feature schema; exact feature-row/sequence construction and preprocessing; and verification that raw receipt/availability semantics support the declared exchange-time calculations. Session aggregates use session-open-to-anchor support, not a guessed fixed lookback.
3. Identity/hash confirmation of current v3 target code/schema and its recorded class construction/support. Receipt/finalization latency, corrections, and operational label-maturity semantics remain to be established. Target support differs by head: direction/structure depend on the future path; volatility additionally depends on a prior 30-return reference, which current generation also requires for a valid row.
4. Authoritative event/exchange/receipt/decision clock semantics, clock normalization and tie ordering, late/corrected event treatment, timezone and exchange-session calendar source.
5. The meaning, timestamp boundaries, chronology, instrument/contract membership, fit/validation/calibration/threshold/evaluation roles, window type, model refit schedule, and allowed updates for WF1–WF4.
6. Session/contract roll and sequence reset/carry policy; ES/NQ as-of synchronization clock, staleness limit, unmatched-stream policy, and missingness policy.
7. Frozen model training recipe/configuration, output schema and probability availability for each A0/A1/A2, deterministic seeds, software identity, and failure handling.
8. Primary estimand/metric hierarchy, eligible population, denominator and missing-class behavior, multiplicity families, uncertainty procedure and all numeric parameters.
9. Calibration and abstention applicability, fitting partitions, support requirements, threshold/coverage target, tie behavior, and baseline handling.

These prerequisites are not permissions. Passing technical gates only permits submission to the independent adoption gate; protected evaluation still requires separate authorization.

## 3. Time and information-set definition

Each candidate forecast row is identified by stable source sample key, instrument, contract, anchor/decision time, session, horizon, and target head. All times are normalized to UTC instants for ordering while preserving original exchange, event, receipt, and source timestamp fields and their provenance.

For a raw record (e), let (v_e) be event time and (a_e) be the documented time at which the record became available to the forecasting pipeline. Event time is not presumed to equal availability time. A feature at anchor (t_i) may consume record (e) only if (a_ele t_i) and the source/tie-order contract allows it. Records with unknown or ambiguous availability are not silently treated as timely; the adopted source-specific policy must either exclude them or apply a documented conservative availability bound.

Every feature row and fitted transform must be reproducible from its allowed source records. Scaling, imputation parameters, class frequencies, transition counts, model weights, calibration parameters, and thresholds are fitted only with information available by their respective chronological fit cutoffs. No test-derived/global preprocessing is allowed. A target, future-window statistic, or revised target label is never a feature unless it has independently matured and the frozen feature definition explicitly allows such history.

### Sequence support

Let (F_r(u)) be the raw-record support of feature (r) at anchor (u); let (L_r(u)=inf F_r(u)). For an eight-row sequence ending at (t_i), its earliest raw dependency is:

\[
L_i^X = \min_{k=0}^{7} L_{r(i,k)}(u_{i,k}), \quad u_{i,7}=t_i.
\]

The last-to-first anchor span equals (7\Delta) only if a fixed cadence \(\Delta\) is established. This is not necessarily the full raw feature lookback because individual features may reach farther into the past. With irregular anchors, use actual timestamps and declared feature support; do not convert a row count into a guessed minute duration.

Historical input overlap between a past training example and a later test sequence is not by itself leakage in forward deployment. It is allowed only when all shared data were actually available at both prediction times and fitted transforms obey their cutoffs. Session/contract carry behavior must be specified from intended deployment, not selected based on outcome.

## 4. Chronological walk-forward construction

Only forward-in-time, non-overlapping outer evaluation segments are permitted in this proposal. Random K-fold and non-forward train/test folds are prohibited. WF1–WF4 are identifiers only; their actual dates, interval boundaries, memberships and ordering are a required gate, not inferred here.

For each outer segment, the final adopted protocol must define ordered cutoffs for:

1. **Training/fit:** parameters and training-only transforms are fitted using eligible prior rows whose required labels have matured by the fit cutoff.
2. **Selection/validation (if required):** may inform only the explicitly enumerated model-selection or stopping decisions. These outcomes cannot also serve as final evaluation or the calibration/threshold partition unless a nested design is separately specified.
3. **Calibration:** a strictly later partition, if probability calibration is part of the evaluated prediction contract. Model weights and preprocessing remain frozen while the calibration mapping is estimated; calibration labels are used only after they mature.
4. **Threshold selection:** a distinct later partition if abstention is evaluated. The threshold rule and its nominal coverage target must be frozen before use. The threshold-selection outcomes may not be used to fit the model or calibration map. If the threshold is purely coverage-selected without target labels, document that explicitly.
5. **Evaluation:** a still-later locked period. No model, feature, threshold, calibration, split, metric, or data-quality choice is altered in response to these outcomes.

The fit/validation/calibration/threshold/evaluation roles are not all necessarily required in every future implementation; whether a role is omitted must be stated before evaluation and must preserve independence of all reused information. The sample sizes and exact cutoff instants are not specified by this proposal because the inventory lacks WF dates, cadence, target maturity, and data coverage. This proposal is therefore not executable.

Expanding versus fixed-width fit history, refit cadence, and whether a model is held frozen through each evaluation interval are design choices that must be fixed identically across candidate systems. Any periodic refit used in evaluation must reproduce only information available at that refit time. Report each outer segment separately before any fixed aggregation. Reuse/selection over test periods is prohibited.

## 5. Label maturity, purge, and embargo

For row (i) and target horizon/head (h), define the complete label-support interval (I_{i,h}=[\ell_{i,h},r_{i,h}]) and label maturity/availability time (m_{i,h}): the time when all source observations needed to finalize the label are available and corrections under the data contract are complete. Current target code records future endpoints at T+H from exactly H one-minute bars, within the same session and exact listed contract, and includes a prior 30-return volatility reference ending at T. The `label_information_start` reaches the beginning of that reference window; actual point-in-time maturity still requires receipt/correction provenance. Horizon alone does not establish maturity.

At fit origin (o), an example is eligible for training head (h) only if:

\[
t_i<o,\qquad m_{i,h}<o,
\]

and its input records and fitted transformations satisfy their respective availability cutoffs. Strict inequality is the proposed conservative boundary rule in the absence of a reliable event tie-order guarantee. When a jointly fit model requires labels for all heads, use (\max_h m_{i,h}<o\); if heads are fit separately, apply each head's maturity rule separately.

This maturity predicate is the forward-chain training-label purge. It is computed from actual label support and receipt/finalization time—not from an unexplained constant. If a future specification permits training rows on both sides of an evaluation interval, it must stop and be redesigned; at minimum, purge every training row whose label support intersects the held-out support:

\[
P_h=\{i\in Train: I_{i,h}\cap(\cup_{j\in Eval}I_{j,h})\ne\varnothing\}.
\]

No post-test training rows are permitted here. Accordingly, a universal post-test embargo is not required for causal separation under this strictly forward design. Embargo is distinct from label-maturity purge; any future embargo must identify the dependence estimand, a training/validation-only method to choose its duration, and the precise timestamp boundary. It cannot be borrowed from historical protocols or described as a generic leakage cure. There is no inherited or adopted `37 minutes` (or any other fixed minute buffer).

If observations have proven fixed cadence \(\Delta\), a row-count approximation for a point target may be computed as \(\lceil h/\Delta\rceil\) adjusted for the declared endpoint convention and observed finalization delay. Actual maturity timestamps take precedence; gaps and irregular times invalidate simple row-count conversion.

## 6. Instrument, contract, session, synchronization, missingness

- Preserve instrument, contract, session, source, and anchor identity at every row; do not silently stitch contracts or reuse future roll identifiers.
- Do not pool ES and NQ training labels or baselines. If the intended evaluation later pools contracts within an instrument, it must establish comparable target/feature semantics and a point-in-time roll policy before data access.
- For cross-market features, select only counterpart records with availability time at or before the anchor. Nearest-future matching, centered windows, or retrospective bar-close joins are prohibited. The actual anchor owner, maximum staleness, clock uncertainty, unmatched-stream policy and tie ordering are required inputs.
- Session boundaries must come from a named exchange calendar with timezone and daylight-saving semantics. Sequence reset/carry across session boundaries must match declared future deployment and be identical across methods. No sequence/target stitching across a contract roll unless a predeclared causal mapping proves it.
- A missing interval is not assumed to be a flat price. Distinguish expected closure, no event, source gap/outage, late record, timestamp fault, and unknown when source evidence permits. Never fill backward from future data. Any causal forward carry/imputation must have fixed age limits, explicit missing/stale markers, and training-only fitted parameters.
- If equal row counts cover unequal elapsed times, either define a fixed sampling grid and empty-bin semantics or retain exact elapsed-time metadata and define model interpretation. This is unresolved for the present object.

## 7. Baseline and candidate-system treatment

The comparison set remains the existing three A0 implementations, A1, and A2, with the existing ablation set. No new logistic model, no-change reference model, or strategy/portfolio is added in this protocol reset. All existing A0 identities are reported separately; the best A0 may not be selected after seeing evaluation results.

At each eligible origin, all systems receive the same permitted source/instrument/horizon/head population and matching matured training history as applicable. A0 statistics must be computed exclusively from eligible training labels available by the origin. A history-based A0 with insufficient valid history must emit a typed unavailable/abstention state, never a silently substituted majority or other model. A1/A2 fitted transforms use training history only. Tie ordering follows the frozen target schema class order and must be verified as part of the technical gate.

The inventory does not identify whether each system emits a probability vector or only a hard class, nor how A0 probabilities are defined. Therefore no probability comparison/calibration operation is allowed until a versioned output contract defines, for every system/head/horizon, class order, probability normalization, invalid-output behavior and interpretation. Do not infer probabilities from hard labels or apply a calibrator to one model while claiming like-for-like calibration across systems.

## 8. Eligibility, denominators, and row states

Eligibility is model-independent and fixed before model predictions are generated. Freeze a sorted canonical key set per declared WF × instrument × horizon × head. Eligibility cannot depend on prediction, confidence, probability, correctness, loss, P&L, ranking, or model-specific convenience. The complete data-quality and labelability rule must be encoded and versioned before evaluation.

For each candidate key, record exactly one current state and an append-only transition history:

| State | Meaning / denominator treatment |
|---|---|
| `STRUCTURAL_UNAVAILABLE` | Fails a frozen model-independent universe/contract criterion before eligible denominator freeze. Excluded from eligible denominator; count and reason must be reported. |
| `ELIGIBLE_PENDING` | In the frozen eligible universe; prediction/outcome lifecycle not complete yet. |
| `MODEL_INPUT_UNAVAILABLE` | Eligible but the required common feature input cannot be formed/validated. Remains in full-eligible availability and coverage denominators. |
| `PREDICTION_AVAILABLE` | A schema-valid output exists; for probability metrics this requires a finite valid class probability vector. |
| `ABSTAINED` | A prediction is available but declines a class decision under a frozen threshold rule. Counts as not covered and not selectively scored. Probabilities may remain scoreable for full-vector probability metrics. |
| `SCORED` | A valid prediction and the complete valid target are available for the declared metric. This is a terminal scored status for that record and metric. |
| `FAILURE:<reason>` | Preprocessing, training, calibration, inference, invalid output, artifact/provenance, threshold, or target failure. If the key is already eligible, failures remain visible in full-denominator reporting and cannot improve results. |

An eventual target that has not matured remains `ELIGIBLE_PENDING`, not a convenient class or silently deleted prediction. Structural exclusions and post-origin target unavailability must be distinguished. Where target-invalid outcomes can only be known after the forecast, retain the prediction in population/coverage accounting and report a typed unscoreable outcome; do not redefine model denominators retrospectively.

For every cell and system publish integer counts: structural exclusions by reason; eligible rows; input-available rows; valid predictions; abstentions; failures by reason; pending outcomes; valid labeled/scored rows. Report end-to-end coverage as accepted predictions divided by the full frozen eligible denominator, plus prediction availability and scoreability. Conditional accuracy/risk among accepted predictions cannot stand alone. Never drop failed model rows from a confirmatory denominator.

## 9. Metrics, calibration, abstention, aggregation

The complete metric hierarchy is **not selected by this proposal**. The first drafts support hard-label metrics (notably per-head macro recall) and, where a valid common probability interface exists, proper probability scores (NLL/Brier) and reliability diagnostics. Those metrics answer different questions. The technical inventory gives no error-cost/estimand preference or common probability contract, so a primary endpoint and claim family must be set in formal protocol review before any predictions or protected results. No scalar combining the three semantically different heads is inferred.

Minimum reports in a future adopted protocol:

- complete 3×3 confusion matrix and class support for every cell;
- classwise metrics with explicit numerator/denominator and `NOT_ESTIMABLE` for absent classes (no post-result metric substitution);
- where output contract permits, NLL/Brier, reliability/calibration diagnostics, and number of valid probability vectors;
- eligible/predicted/abstained/scored/pending/failed counts and coverage at every declared denominator;
- disaggregated results for every WF × instrument × horizon × head × model/configuration/ablation and every declared seed;
- any pooled value only under a fixed, justified aggregation order and weights, with all component cells visible.

If calibration is authorized, fit it on a past-only calibration segment after model parameters are frozen; preserve calibration/evaluation separation. If abstention is authorized, its score, threshold-selection rule, operating point, calibration dependency, and baseline treatment must be frozen. Keep `STRUCTURAL_UNAVAILABLE`, `MODEL_INPUT_UNAVAILABLE`, `PREDICTION_AVAILABLE`, `ABSTAINED`, and `SCORED` disjoint. No abstention q, such as 0.80, is selected here. Full eligible denominators and coverage must accompany any selective risk.

## 10. Uncertainty, multiple comparisons, seeds, ablations

Any inferential claims require a prespecified paired method appropriate to time dependence and the chosen endpoint. Adjacent anchors, overlapping horizons, ES/NQ at contemporaneous times, walk-forward windows, and random seeds are not assumed independent. Row-IID standard errors or independently resampled model rows are prohibited. The proposed candidate direction is a synchronized time-block procedure that keeps ES/NQ, horizons, heads and model comparisons paired; its block units, length rule, replicate count, endpoint calculation and interval/p-value procedure require formal review. A forecast-loss differential test may be used only if its estimand and assumptions fit the endpoint. No method, alpha, block length or confidence claim is authorized by this draft.

Before results, the adopted protocol must define the complete claim family across A0/A1/A2, heads, horizons, instruments, WFs, ablations and seeds, including primary/secondary/exploratory labels and multiplicity control. Report all planned contrasts and no implicit “winner.” If seeds are used, freeze the complete seed set and training recipe, report all seeds and summarize by a predeclared statistic/distribution; never select the best seed. Seeds are not added to market sample size. Ablations answer predeclared feature-family removal questions; they cannot be used as a performance search to select a new live model.

## 11. Failure handling and reproducibility

Every validation/processing failure has a machine-readable reason, source key and stage. At minimum distinguish `PROTOCOL_PREREQUISITE_MISSING`, `SOURCE_UNAVAILABLE`, `TIMESTAMP_UNAVAILABLE`, `STALE_OR_UNSYNCHRONIZED_INPUT`, `SESSION_OR_CONTRACT_BOUNDARY`, `LABEL_NOT_MATURE`, `MODEL_INPUT_UNAVAILABLE`, `TRAINING_FAILED`, `CALIBRATION_FAILED`, `THRESHOLD_SELECTION_FAILED`, `INFERENCE_FAILED`, `OUTPUT_INVALID`, `OUTCOME_INVALID_OR_UNAVAILABLE`, and `ARTIFACT_HASH_MISMATCH`. The exact controlled vocabulary and schema version must be frozen before implementation.

A future authorized run must write a reproducible manifest with source/instrument/contracts/date range, schema and target versions, source/normalized hashes, validation status, exact protocol/prose hash, code commit, configuration hash, model identities, seeds, split/key assignment hashes, output artifact hashes, environment/software identity, run status, coverage/quality report, and `trading_authority: NONE`. A mismatch or critical corruption fails closed; no partial result is silently treated as complete.

## 12. Methodological basis and provenance labels

The candidate’s general recommendations draw on public time-series forecasting, leakage, probabilistic scoring, calibration, selective classification, forecast comparison, dependence-aware resampling, and multiple-comparison literature cataloged in [`METHODOLOGY_REFERENCE_LEDGER.md`](phase5c-clean-slate/METHODOLOGY_REFERENCE_LEDGER.md). Such sources support general propositions, not the exact experiment choices.

Every normative rule in any future adopted protocol must carry one provenance class:

- `MATHEMATICALLY_DERIVED` — follows from explicit time/interval definitions;
- `STANDARD_METHODOLOGY` — supported by a public, cited method;
- `PROSPECTIVE_DESIGN_CHOICE` — deliberately fixed before protected results;
- `TECHNICAL_CONSTRAINT` — imposed by the frozen object or data contract.

No rule may be labeled `HISTORICAL_PHASE5C_AUTHORITY`.

## 13. Decision and stop condition

This document is a prose candidate only. The exact evaluation population, primary endpoint, model probability contract, thresholds, source dataset identity, split dates and chronology, training recipe/seeds, receipt-based target maturity, calendar/contract policy, synchronization tolerance, statistical family, and multiple-comparison plan remain unresolved. Current v3 feature and target calculations are recorded as code-level technical facts in the inventory; their real-time availability and fold/population integration are not established. Thus two engineering teams cannot yet be expected to construct the same complete evaluation populations and inferential claims from this document alone.

Do not create the JSON companion unless two fresh, independent prose-completeness reviewers both answer YES to the prescribed reproducibility question. If either answers NO, record blockers, revise the prose prospectively, and repeat independent review. Even a passing review does not adopt the protocol or open protected data; adoption is a separate formal gate.
