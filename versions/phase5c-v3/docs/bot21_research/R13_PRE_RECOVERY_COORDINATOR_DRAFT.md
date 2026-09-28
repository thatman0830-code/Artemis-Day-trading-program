# R13 — Nonstationarity and adaptation

**Status:** coordinator synthesis; independent specialist pass pending.

Separate covariate drift, label/base-rate drift, concept drift, volatility scaling, structural breaks, seasonal/session changes, and source/contract changes. They are different detection targets and require different measurements. A detected shift is not evidence that a model should retrain or that edge exists. Rapid online updates can learn noise, label revisions, or recent events and can forget robust older behavior [S46,S62,S92,S104].

Intraday volatility periodicity can itself vary over time: ES transaction evidence documents a nonstationary volatility calendar effect, while broader financial-return research documents changing intraday zero-process periodicity. These findings support monitoring calendar/session distributions, not an assumed adaptive trading advantage [S46,S62].

Offline structural-break estimates and full-sample changepoint locations are descriptive, not as-of real-time features. Online detectors can be causal when fed only then-available observations, but prior/hazard/model assumptions, false alarms and detection delay remain [S90,S91]. Residual/loss drift can only be detected after the target matures.

Candidate future approaches: monitor input/forecast/label distributions; rolling-origin retraining with frozen cadence; separate detector and adaptation gates; compare static, rolling, expanding and regime-specific fits; test a chronological replay with delayed label maturity; retain versioned previous models for rollback; measure false alarms, detection delay and post-shift behavior. Expanding and rolling windows imply different bias/variance assumptions; select neither from hindsight. Any test-time adaptation must consume only data available at that time and log state transitions. Do not update on protected future outcomes [S94,S104].

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** begin future work with drift monitoring and a non-adaptive baseline before online learning, regime-specific retraining, or test-time adaptation. Predefine what happens on drift (including abstention/no model change) and validate it on distinct historical shift episodes plus future data. **INSUFFICIENT_EVIDENCE:** a safe, profitable adaptive schedule for ES/NQ intraday signals. Intraday nonstationary-periodicity evidence in FX/equities and adaptive conformal methodology are not finance-specific proof of a beneficial adaptation policy [S25,S46].
