# R18 — Adversarial financial-ML review

**Status:** coordinator red-team synthesis only. The requested eight fresh independent X1–X8 reviewers have not yet been run; this is not their substitute.

Assume the observed edge is false until independently replicated. Main attack surfaces:

1. Architecture shopping over many papers/horizons/windows/seeds and reporting only the winner.
2. Dataset or pretraining contamination that makes a “zero-shot” model not genuinely out of time.
3. Label definitions, target maturity, roll/session boundaries, cross-market lookahead or receipt-time mistakes.
4. Full-sample scaling, universe/feature selection and calibrator/checkpoint selection that use future periods.
5. Sharpe/accuracy overinterpretation with small effective sample size, autocorrelation, class imbalance, fat tails and overlapping trades/labels.
6. Hidden dependence on macro-shock memorization or repeated regime episodes rather than persistent generalization.
7. Generic long-horizon benchmark accuracy treated as high-frequency directional value or executable profitability.
8. Cross-market correlations treated as stable causal lead-lag; nearest timestamp joins can leak future information.
9. Transaction costs, spread, queue/fill, latency, market impact, partial fills and rejected orders omitted or tuned optimistically.
10. High-capacity hybrid/MoE systems compared with under-tuned or weak baselines and given many more search attempts.

**Minimum later falsification sequence:** freeze hypotheses/splits/metrics first; validate data provenance/time availability; use naive/linear/regularized and compact causal baselines; lock an untouched future period; record all trials; run negative controls and sensitivity analyses; use dependence-aware intervals and multiple-testing correction; evaluate predictive calibration separately from economics; cost/fill assumptions independently audited. These are design principles only, not permission to run tests now.

Source basis: benchmark contamination [S19,S20], LTSF-linear counterevidence [S04], PBO/DSR/multiple-testing sources [S28,S43–S45], forecast calibration [S22,S25–S27].
