# R7 — Target and label research

**Status:** independent specialist first pass completed (R7); coordinator synthesis pending. No labels or BOT 2.0 registries changed.

| Candidate output | What it can answer | Main caveat |
|---|---|---|
| Future return at fixed horizons | Magnitude/direction at a stated maturity | Heavy tails, overlap, horizon dependence and very small predictable component; class thresholds can erase magnitude. |
| Return quantiles/distribution | Conditional location, tails and uncertainty | Must be evaluated with proper scores/calibration; distribution misspecification and drift remain. |
| Realized volatility / range | Future risk state | Estimator window/maturity must be explicit; realized measures can use future data only as target, never input. |
| Direction | Sign class | Imbalanced/noise labels; accuracy alone can mislead. |
| Structure/regime | Trend/range or event categories | Labels are definitions with judgment/measurement noise, not objective truths by virtue of names. |
| MFE/MAE / barrier outcomes / time-to-event | Path and risk/opportunity descriptions | Requires high-integrity intrabar path, barrier tie-breaking, and overlapping-event treatment. |
| Meta-label/opportunity/risk | Conditional quality of an independently generated hypothesis | Risks entangling prediction and policy; any later formulation must be pre-specified and non-authoritative. |

Each target is a distinct estimand: fixed-horizon return, sign probability (with any neutral band changing class balance), conditional quantile/distribution, realized variance/range/downside risk, barrier/path event, time-to-event with censoring, state probability, or meta-label conditional on a separately defined candidate signal. None is a synonym for “trade quality.”

The evaluation score must match the forecast functional: e.g. quantile loss for quantiles and proper scores for distributions. Volatility, direction, and tail-risk forecasts provide different information. ES-specific work supports attention to session-dependent intraday volatility, but it does not establish one target as best or transfer automatically to NQ [S36,S82–S86].

Every example needs both a prediction timestamp and label-resolution/maturity timestamp. Fixed-horizon labels overlap when predictions are frequent; barrier labels have variable maturity. Purge any training example whose target window crosses the held-out interval, and justify any extra embargo by dependence/feature windows rather than a fixed arbitrary gap. Meta-labeling predicts success conditional on a candidate signal and chosen outcome definition; it does not independently validate the signal’s direction [S35,S87].

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** compare the existing conceptual direction/volatility/structure tasks against a return-distribution task in a later authorized research phase; do not assume the existing three tasks are sufficient or replace them now. Distinguish forecasting target from trading decision. Use proper probabilistic scores alongside class metrics. **INSUFFICIENT_EVIDENCE:** which target conveys useful information for an allowed future action.

Foundational references include triple-barrier/financial labeling methodology (book source, practitioner methodology, not evidence of superiority), realized-risk measurement, and proper forecast scoring [S35,S36,S82–S87]. Transfer limits: reviewed target-design methods do not prove ES/NQ intraday edge, optimal horizon, or trading policy.
