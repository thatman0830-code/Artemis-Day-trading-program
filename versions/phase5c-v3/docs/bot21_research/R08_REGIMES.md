# R8 — Regime intelligence

**Status:** independent specialist first pass completed (R8); coordinator synthesis pending.

Regime can be observed context, a supervised future-outcome target, a filtered latent state, a change point, or a router for experts; these concepts are not interchangeable. Start with causal, continuous observed context (session/time, lagged volatility/range, contemporaneous liquidity only if available) and direct forecasts. A “regime” label is a constructed representation rather than a unique ground truth. Supervised future volatility/path bins require mature labels and purging; thresholds must not be computed on full history.

HMM/Markov and state-space models offer probabilistic latent states, but only filtered state probabilities using observations through time t are valid as-of t. Smoothed or Viterbi full-sequence state assignments use later observations and leak. Retrospective structural-break estimates similarly cannot be treated as real-time signals. Online change-point detectors are causal in operation but depend on priors/hazard assumptions, can false-alarm, and detect with delay; detectors on residual loss cannot warn before the target matures [S88–S92,S94].

Learned routing/MoE can blend experts, but adds a gate to fit and can collapse or create unstable state assignments; basic MoE architecture evidence is not market-specific [S93]. Fit scaler, clusters, state model and router only on each training window; apply causal filtered inference to the following window.

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** study observable, causal regime/context variables first; compare against a small HMM/filtering baseline and a model without regime conditioning. Learned routing/MoE comes later only if stable improvement is replicated across prespecified windows. Treat regime boundaries as uncertain, and test false change alerts and transition periods separately. Regime is not a direction forecast or an exemption from uncertainty/risk controls.

**INSUFFICIENT_EVIDENCE:** whether explicit or latent regime representation helps ES/NQ. Intraday periodicity in S&P futures supports attention to session conditioning, not a profitable classifier. No retrieved paper proves that a particular real-time ES/NQ regime taxonomy is stable or tradable [S68].
