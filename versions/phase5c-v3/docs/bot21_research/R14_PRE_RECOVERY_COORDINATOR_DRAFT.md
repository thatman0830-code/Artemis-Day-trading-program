# R14 — Ensembles, experts and fusion

**Status:** coordinator synthesis; independent specialist pass pending. No architecture is selected.

Conceptual fusion axes: local temporal encoder (causal CNN/TCN); long context encoder (attention/SSM); regime/context representation; separate ES and NQ streams; optionally cross-market interaction; multi-task or distribution heads; calibrated uncertainty and abstention. Alternatives include early feature fusion, late score fusion, gated/MoE routing and simple weighted ensembles.

These are separate hypotheses. Early fusion can entangle asynchronous/missing inputs; late fusion preserves stream-level diagnostics but adds a meta-model. Cross-attention adds interaction capacity but should be compared to one-sided lagged covariates and simple concatenation under the same as-of contract. Learned expert routing follows the MoE family [S93], while simple deterministic weighting is easier to freeze but can still be tuned on noise.

Cross-market joint encoding can learn lead/lag or common factors, but imposes synchronization and missingness assumptions; separate instrument encoders with late fusion preserve instrument-specific dynamics but increase parameter/search count. Cross-attention is a hypothesis, not inherently superior to lagged covariates or simple concatenation. Gating/MoE may capture specialization but can overfit regimes, collapse or respond to noise. Ensemble gains require diverse forecast errors and frozen weights; correlated errors produce little benefit, and ensemble spread is not epistemic uncertainty without validation. Every additional branch increases experiment multiplicity and must be logged.

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** shortlist simple late fusion and separate/joint-stream comparisons only after a single-stream baseline. Each added branch must win a prespecified incremental ablation under identical information timestamps and compute/context budget. Reserve MoE and multi-branch hybrid for later if simpler ablations show repeatable complementarity. No fusion design can be chosen from correlation alone.
