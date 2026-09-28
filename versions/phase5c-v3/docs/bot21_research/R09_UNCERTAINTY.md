# R9 — Uncertainty and calibration

**Status:** independent specialist first pass completed (R9); coordinator synthesis pending. R0 itself makes no prediction.

Uncertainty should be understood as forecast-distribution reliability under temporal/local shift, not a single confidence scalar. Aleatoric/epistemic distinctions are useful but not a uniquely additive decomposition: omitted inputs, data quality and misspecification blur them. A softmax score or ensemble spread is not automatically calibrated. Evaluate calibration together with sharpness using proper scores; an uninformatively wide forecast may calibrate marginally without useful precision [S36,S95–S97].

Separate model fit, calibration/recalibration and final evaluation chronologically. In online use, only recalibrate after outcome maturity. Standard conformal marginal coverage does not mean conditional coverage for a specific session/regime; exact distribution-free conditional coverage generally requires extra assumptions. Weighted conformal relies on covariate-shift assumptions and an adequate likelihood ratio; it does not automatically handle concept shift. Adaptive Conformal Inference targets long-run frequency, not the next interval or immediate post-break coverage [S98–S100].

An emerging 2026 online calibration method studies certificate-driven guarantees under covariate/concept shift and temporal dependence; it is a general-method lead, not ES/NQ validation [S101]. Intraday nonstationarity in zero-return periodicity further cautions against assuming volatility scaling alone makes forecast errors comparable over time [S46].

**“I don’t know” design hypothesis:** make abstention/selective prediction an explicit future output based on a frozen, validated uncertainty/quality policy; report risk-versus-coverage and subgroup/session/regime calibration. Under drift, conventional conformal exchangeability assumptions fail; adaptive conformal methods can target long-run coverage under shifting distributions but do not guarantee each ES/NQ regime or finite-sample conditional coverage [S25]. ICLR 2026 TSFM calibration study is encouraging but domain-limited [S22].

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** compare calibrated return quantiles or distributions plus a separately measured selective-abstention layer. Record calibration error, interval coverage/width and risk-coverage curves by horizon/session/volatility bucket, with uncertainty intervals. Abstention cannot silently become order suppression/release logic in R0.

**INSUFFICIENT_EVIDENCE:** reliable conditional calibration/abstention thresholds under changing intraday futures distributions. Report risk–coverage with accepted share, horizon/instrument/session/regime slices, confidence intervals and counts; a selective subset is not automatically safe or profitable [S22,S25–S27,S95–S101].
