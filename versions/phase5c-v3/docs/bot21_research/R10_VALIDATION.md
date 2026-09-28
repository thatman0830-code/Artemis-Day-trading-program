# R10 — Validation and statistical science

**Status:** independent specialist first pass completed (R10); coordinator synthesis pending. Design principles only.

Use point-in-time, chronological rolling-origin/prequential outer evaluations with multiple contiguous future blocks. Put architecture/feature/threshold/hyperparameter selection inside inner chronological folds; preserve a final contiguous untouched period for a single confirmatory test. Fit normalization, imputation, feature selection and calibration inside/after training folds without access to the final test. Specify expanding vs rolling window and refit cadence before outer testing. Rolling-origin tests model the studied history, not future stability [S94,S102–S104].

Purge training rows whose label-information intervals overlap held-out target intervals. An embargo is most relevant to CV designs that can train on observations after the test block; strictly past-to-future splits have no later train rows, though target/feature overlap gaps can still be necessary. Purging does not make shuffled splits deployment-like or repair other data defects. Report fold/time-block dispersion and predeclared session/volatility slices; do not count bars as independent evidence.

At minimum compare zero-change/last-value, autoregressive and same-time-of-day naïve controls with identical timestamps, horizons, folds and metrics. Match scores to the estimand. Compare paired per-origin loss differences; DM/HAC and block/stationary bootstrap approaches handle some serial dependence under assumptions, but few independent days/regimes or structural breaks make intervals fragile [S105–S107]. Sample size should be driven by a predeclared practically meaningful effect and session/day-level variance; there is no universal sufficient bar count.

**RECOMMENDATION — STANDARD_METHODOLOGY:** pre-register hypotheses, primary metric, model universe, context budget, seeds, split dates, stopping and failure criteria; reserve a final untouched period; record every attempted and abandoned configuration; include negative controls where valid; and make future runners reject unauthorized partitions. Reality Check/SPA require the tested universe and dependence assumptions; DSR/PBO are supplementary selection diagnostics, not pass badges. None repairs unlogged researcher degrees of freedom, leakage or future breaks [S28,S43–S45,S108].

ES-to-NQ transfer is a separate generalization claim: validate chronologically on NQ and compare to an NQ-only baseline, with contract, tick/point scaling, session and availability rules fixed. Different underlying indexes and contract economics establish non-equivalence, not proof of transfer failure [S31,S58,S60].

**Non-guarantees:** rolling/nested CV cannot guarantee future performance under distribution shift; purging/embargo cannot catch every timestamp/revision/survivorship defect; dependence-aware inference may fail with few regimes or breaks; multiplicity methods only adjust the known candidate universe; preregistration cannot guarantee valid labels or clean data; ES-to-NQ transfer requires direct evidence.

**INSUFFICIENT_EVIDENCE:** exact amount of history or independent sessions needed to validate ES/NQ forecasting; derive via power/uncertainty and data-quality analysis in a future phase, not by arbitrary trade-count targets. No validation or model test was performed in R0.
