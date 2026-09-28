# R3 — Financial machine-learning evidence

**Status:** independent specialist first pass completed (R3); coordinator synthesis pending. No performance claims or evaluation artifacts from BOT 2.0 were inspected or used.

Financial time series have low signal-to-noise, heavy tails, serial dependence, nonstationarity, rare jumps, asynchronous sources, and delayed/overlapping labels. A very large number of apparent research claims disappear when target definitions, chronological splits, costs, and the full model-search history are accounted for. Cross-sectional equity, daily futures, crypto, and index-futures evidence are not interchangeable.

| Issue | Evidence class | Research implication |
|---|---|---|
| Nonstationarity and signal decay | FOUNDATIONAL_EVIDENCE | Monitor distribution and conditional performance; a one-time fit or pooled historical score cannot guarantee forward validity. Drift detectors themselves have false alarms and cannot establish useful adaptation. |
| Rare events / imbalance / heavy tails | STANDARD_METHODOLOGY | Report class prevalence, per-class calibration, tails and uncertainty; accuracy alone rewards majority-class predictions. |
| Labels and overlapping horizons | STANDARD_METHODOLOGY | Treat label maturity/overlap explicitly; purge spans that overlap evaluation targets and embargo where justified. A fixed-horizon direction label is not equivalent to an economic opportunity label. |
| Multiple testing | FOUNDATIONAL_EVIDENCE | Record every tried architecture, target, feature, seed, context and selection decision. Deflated Sharpe / PBO answer distinct questions and do not repair contaminated OOS. |
| Financial neural results | RECENT_EMPIRICAL_EVIDENCE, LIMITED | A 2026 arXiv benchmark compares architectures on daily multi-asset futures; a separate 2024 GCN-LSTM preprint studies ES/VX term-structure contracts. Neither directly establishes ES/NQ 1-minute edge; both require replication and cost/method scrutiny [S119,S120]. |
| Limit-order-book prediction | FOUNDATIONAL_BUT_NARROW | DeepLOB and FI-2010 report mid-price direction classification on non-US-equity LOB data; labels/accuracy are not economic returns. A separate supervised execution study uses Level-II E-mini S&P data, but its historical assumptions do not establish present-day alpha or transfer to NQ [S38,S47,S51]. |
| Equity ML evidence | DOMAIN-SPECIFIC | Gu, Kelly & Xiu document useful nonlinearities for daily cross-sectional equity returns; this is not intraday index futures evidence [S49]. |
| Execution economics | TECHNICAL_CONSTRAINT | Forecasting accuracy does not imply net tradability. Later evaluation must account for fees, spread, market impact, latency, queue position, rejected/partial fills and opportunity cost; no cost optimization is authorized here. |

**Bottom line:** classify all AI-trading profitability claims as **INSUFFICIENT_EVIDENCE** until a sealed, pre-registered, leakage-safe, prospective experiment with realistic costs exists. Do not turn classification results into trade authority. Execution-cost evidence and multiple-testing safeguards are distinct requirements, not substitutes for one another [S43–S50]. Detailed sources include S24–S28, S38, S43–S51.
