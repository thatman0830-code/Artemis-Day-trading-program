# R12 — Loss functions, optimization and regularization

**Status:** independent specialist first pass completed (R12); coordinator synthesis pending.

| Objective | Prospective fit | Main caveat |
|---|---|---|
| Cross-entropy / Brier | Direction/state probabilities | Imbalance and calibration; accuracy is not a proper economic objective. |
| Huber / robust regression | Returns/volatility with outlier resistance | Threshold is a tuned choice; robust loss can downweight important tail events. |
| Quantile / pinball | Return intervals/quantiles | Quantile crossing, sparse tail data and conditional calibration. |
| Gaussian/Student-t NLL | Parametric distribution | Distribution assumptions can underfit skew/jumps; tails need checking. |
| CRPS / proper scores | Full predictive distributions | Depends on valid forecast distribution and correct scoring protocol [S36]. |
| Focal/weighted loss | Rare class emphasis | Changes probability calibration and must be justified without test tuning. |
| Contrastive/masked reconstruction | Self-supervised representation | Lower reconstruction error does not imply future predictive value; augmentations can alter financial semantics. |
| Multi-task weighting | Shared tasks may reuse signal | Negative transfer; learned loss weights may suppress hard but important targets [S37]. |
| Direct decision/utility loss | Optimize a sequential policy objective | Moves from forecasting into policy learning and requires causal position state, costs, turnover and realistic execution; it is not authorized here [S116]. |

The loss defines the estimand: MSE targets a conditional mean; MAE a median; quantile/pinball loss a specified quantile; probability scores reward honest probability forecasts. VaR and expected shortfall may require joint scoring. QLIKE can be useful for conditional-variance comparison under assumptions on a noisy variance proxy; that does not make the proxy ground truth [S85–S87,S112,S113]. Self-supervised contrastive/reconstruction objectives evaluate representation behavior, not forecast quality or economic utility [S114].

Adam/AdamW, SGD, warmup and schedules are engineering choices, not expected-return guarantees. Decoupled weight decay is not generally equivalent to L2 regularization in Adam, but AdamW’s benchmark findings are not financial evidence [S115]. Dropout, weight decay, early stopping and stochastic depth create further search dimensions. Fix a small configuration per family, count each attempted run, use training-only stopping, and validate repeated seeds only in a later authorized phase. Under drift, expanding/rolling windows and recency weighting encode different assumptions; no window or optimizer is universally superior [S117]. Do not select loss/optimizer by protected OOS or P&L in R0.

Lower training loss, accuracy, forecast calibration, or convergence is evidence about model fit/forecast properties, not by itself about executable value. A trading-value claim would require a separately authorized policy and later cost-/fill-aware evaluation; no such work is allowed here [S47,S48,S118].

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** if future R1 permits model evaluation, compare a minimal classification loss and robust/quantile return forecast with proper probabilistic scoring and predeclared task weighting; keep the search grid small. No exact loss, optimizer, regularization level or task weight is chosen now.

Sources: matched point/probability scoring [S85–S87]; tail risk and noisy volatility proxies [S112,S113]; self-supervised, optimizer and online-learning context [S114,S115,S117]; decision-objective distinction [S116,S118]. These sources do not identify an optimal ES/NQ loss or profitable objective.
