# R11 — Temporal leakage / causality review

**Status:** independent specialist first pass completed (R11); coordinator synthesis pending. No protected outputs accessed.

Red-team the information path from source to output. Critical failure modes include: exchange-event timestamps substituted for local availability/receipt time; ES/NQ joins using future/nearest bars without max-age semantics; revised/corrected data consumed before its historical publish time; global normalization or full-dataset feature selection; session open inferred from first observed row when early bars are missing; roll-adjusted histories that use future roll decisions; partial higher-timeframe candles; bars/windows spanning gaps, contract/session boundaries; target maturity overlap; calibrator/checkpoint selection on test periods; and repeated manual architecture choice after viewing holdout outcomes.

Treat each prediction origin as an availability audit: record event time, source publish/send time, receipt/processing time, data revision/vintage, and earliest usable time. At every model-fit origin, require training-label maturity; at every prediction origin, require every input’s availability to be no later than that decision. A source timestamp’s meaning is venue/feed-specific and should be checked in its contract, not assumed [S109]. Preserve first-seen values and later revisions for any external/macro series; revised current history is not point-in-time history [S110].

For multi-timeframe bars, only use completed bars whose close and receipt are at or before the decision timestamp. If using an in-progress higher bar, reconstruct its then-known partial state rather than using the final historical high/low/close/volume; historical and real-time higher-timeframe values can differ [S111]. Rolling transforms must be trailing, and scaler/normalizer/imputer/seasonal adjustment parameters fit only inside each training window [S102].

For ES/NQ, define the canonical decision time and one-sided as-of join, maximum staleness, tie breaks, and behavior for delayed/missing records. Keep each instrument’s contract and feed clocks. Event time alone does not establish strategy availability; historical archives without receipt time cannot certify latency-causal replay. For sessions/rolls, use the historical applicable exchange schedule and a causal roll rule; keep actual contract identifiers rather than silently modifying past prices with later roll knowledge [S29–S31].

Store each label’s outcome interval and maturity. At each historical fit, only use matured labels. Purge overlap with the held-out target interval; an embargo is justified only by a specified split/dependence structure. Train calibrators on out-of-fold/validation predictions and keep final-test outcomes out of architecture, checkpoint, feature, threshold and calibration selection [S28,S43–S45,S94–S108].

Foundation models add a pretraining contamination surface: record model/version, training cutoff, known corpus provenance and benchmark overlap. A chronological split cannot prove a public TSFM never saw the test period or related derived series; opaque provenance is **UNKNOWN**, not clean by default [S19,S20].

**Required later controls — STANDARD_METHODOLOGY:** record exchange event time, local receipt time and data-version/revision where available; define bitemporal availability; same-as-of joins or one-sided lagged joins with explicit staleness, never nearest-future matching; fit transforms only on training data; freeze calendar/session/roll rules; purge overlapping target intervals; align maturity and label windows; split sequences by causal episode; preserve raw timestamps and audit decisions. If historical receipt time is unavailable, do not claim latency-causal replay.

Foundation-model pretraining introduces an additional contamination surface: training corpora may overlap public benchmarks, calendar shocks, or target periods. Document source/time cutoffs and known overlap; unknown pretraining provenance is **INSUFFICIENT_EVIDENCE**, not clean by assumption [S19,S20].

**Recommendation — STANDARD_METHODOLOGY:** retain an auditable feature-lineage table (source, event/availability time, revision, transformation window, earliest use) and label lineage (start/end/maturity); enforce no-future availability at fit and prediction origins. Use a final chronological holdout only after choices are fixed. Multiple-testing corrections do not repair temporal leakage.

**No code or experiments authorized.**
