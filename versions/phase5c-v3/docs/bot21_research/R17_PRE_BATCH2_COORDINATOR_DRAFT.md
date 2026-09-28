# R17 — Prediction versus decision architecture

**Status:** coordinator synthesis; independent specialist pass pending.

Separate predictive quantities from any future action layer. A model may estimate conditional return distributions, direction probabilities, realized-volatility/range distributions, market-state probabilities, forecast quality and uncertainty. A deterministic, separately specified policy/risk layer can later decide whether those estimates are eligible for use. End-to-end action prediction may optimize a simulator-specific reward and hide dependence on cost, fill assumptions, or allowed risk.

This separation aids attribution, calibration, audit, abstention, policy review and strict disconnection from broker/order authority. But it does not guarantee interpretability: an output probability is not a causal explanation, and uncertainty does not ensure safety. All policy thresholds and risk controls remain outside R0 and unchanged.

**Recommendation — BOT21_PROSPECTIVE_DESIGN_HYPOTHESIS:** if R1 is authorized, keep model outputs descriptive and read-only; evaluate them using proper predictive metrics before any separately authorized decision-policy study. No trade generation, sizing, paper order, broker connection or risk integration is allowed in this phase.
