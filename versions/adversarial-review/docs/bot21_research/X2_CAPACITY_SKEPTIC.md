# X2 capacity skeptic review

## 1. Mandate and independence

This is the independent X2 review of capacity and underfitting risk for BOT 2.0’s frozen Phase 5C comparison. The review is limited to claims, protocol sufficiency, and publicly documented methodology. It does not run, score, train, infer, backtest, trade, install, or modify any experiment. I did not inspect X1, X3, or X4 outputs. All objections below are classified **BLOCKER**, **MAJOR**, **MODERATE**, **MINOR**, or **INFORMATIONAL**.

## 2. Frozen identity and scope

The requested review target is branch `bot2-phase5c-z-review-remediation`, HEAD `fe9a9aa536ed36795d52c90a5e9c2b85f564cdb`. The supplied expected R20 artifact hash is `A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE`; the supplied expected review-freeze hash is `F3D295541151A251401E6DED7062D655E2E390B58F0B15C40B87083E097D9553`. These identities are recorded as inputs, not independently reinterpreted.

The comparison context names ES and NQ, walk-forward cells, 5/15/30-minute horizons, three target heads, A0 persistence/majority/transition baselines, A1 MLP, A2 causal TCN, and declared ablations. The inventory and registry establish model and artifact identities but do not, by themselves, establish that any model is adequate or that any result transfers across instruments.

## 3. Evidence classes

I separate four evidence classes. **R20 claim** means the proposition attributed to Cawley and Talbot (2010): model-selection overfitting can bias subsequent performance estimates. **R20 support** means what that paper and the immutable methodology ledger support: selection and evaluation must be separated, and apparent performance after reuse of an evaluation criterion can be optimistic. **Public evidence** means the linked methodological literature, which supports general controls only. **Hypothesis** means a BOT 2.0-specific possibility requiring the frozen ledger or a predeclared analysis; it is not an observed finding.

## 4. R20 claim, support, and boundary

**Classification: INFORMATIONAL.** The R20 claim is methodologically credible and relevant to any capacity comparison with multiple horizons, instruments, folds, seeds, metrics, and ablations. R20 does not show that A1 or A2 is underfit here, does not show that A0 is the correct comparator, and does not establish a preferred architecture, sample size, target, or ES/NQ transfer rule. It also does not supply trading or profitability evidence. Applying R20 to BOT 2.0 is therefore a reason to control selection, not evidence of a particular winner.

## 5. Primary capacity thesis

**Classification: MAJOR.** The frozen model identities permit a capacity question but do not establish whether the available information supports the capacity of A1/A2. A2 may be too small to represent long-range, cross-market, session-dependent structure, or too large relative to effective independent examples; A1 may be too constrained for interactions but still flexible enough to fit noise. A0 may appear competitive when the target is persistence-heavy or class-imbalanced. These are competing hypotheses. They cannot be resolved by architecture names or parameter counts alone.

## 6. Objection register: effective sample size

**Classification: BLOCKER.** Adjacent origins and overlapping 5/15/30-minute labels are dependent, so the number of rows cannot be treated as the number of independent learning examples. Without an authorized effective-sample accounting by instrument, horizon, head, and walk-forward cell, no claim that A1/A2 has enough capacity or that a result indicates underfitting is reviewable. The blocker applies to R1 if R1 is intended to authorize or interpret a model comparison from row counts alone. Required resolution: freeze temporal origins, label overlap, purge/embargo, and a dependence-aware uncertainty/aggregation rule before interpreting capacity.

## 7. Objection register: parameter-to-information ratio

**Classification: MAJOR.** A parameter count, layer count, or receptive-field length does not establish usable capacity. The relevant ratio is between train-only information, class support, temporal dependence, and the number of selected configurations. If that accounting is absent, “A2 is underfit” and “A2 overfits” remain equally plausible hypotheses. R1 is blocked from making a capacity conclusion until fold-level train/validation support and the frozen architecture/configuration identities are paired with the same eligible origins.

## 8. Objection register: target and label geometry

**Classification: MAJOR.** Capacity requirements differ across target heads and horizons. A 5-minute head may reward local persistence; a 30-minute head may require broader context and have fewer independent transitions. A model can be adequate for one head and underfit another while a pooled summary hides the distinction. Every capacity statement must remain cell-specific, retain all declared heads/horizons, and show class support and transition structure. A pooled winner cannot diagnose representation failure.

## 9. Objection register: architecture versus optimization

**Classification: MAJOR.** An apparent capacity gap can be caused by optimization, regularization, early stopping, initialization, loss weighting, or schedule choices rather than representational limits. Conversely, increasing width or depth after viewing outcomes would create a new selected model and invoke R20’s selection concern. R1 is blocked from attributing a difference to architecture unless the training policy, stopping rule, seeds, and permitted tuning partition are frozen before evaluation and reported for every declared run.

## 10. Objection register: baseline saturation and class imbalance

**Classification: MODERATE.** A0 persistence, training-majority, and transition baselines can be strong under persistent or imbalanced labels. That is useful context, but a close A1/A2 comparison does not prove the neural models lack capacity: the target may contain little predictable signal, or the metric may reward the dominant class. Conversely, a neural advantage on accuracy alone may be a prevalence artifact. R1 should remain blocked on any “capacity” conclusion until per-class support, confusion accounting, and a fixed probability metric are available.

## 11. Objection register: selection multiplicity and R20 risk

**Classification: BLOCKER.** The declared grid creates many opportunities for a favorable selection across ES/NQ, horizons, heads, folds, seeds, ablations, metrics, and aggregation choices. Selecting the best cell, seed, or ablation and then describing it as out-of-sample capacity is exactly the type of subsequent evaluation bias R20 warns about. R1 cannot be approved as confirmatory if the primary estimand, selection rule, and untouched evaluation partition are not frozen. Descriptive full-grid reporting may proceed only under an authorized protocol; it does not cure confirmatory selection.

## 12. Objection register: missingness, availability, and sequence length

**Classification: MAJOR.** A sequence model can look capacity-limited when it receives fewer valid context windows, asynchronous cross-market observations, or more missing values than A0. Conversely, permissive imputation or future-arriving synchronization can make A1/A2 appear stronger. Capacity must be assessed on a common, point-in-time eligible ledger with separate statuses for label-unavailable, input-unavailable, abstain, and forecast. R1 is blocked if model-specific coverage is silently folded into a performance comparison.

## 13. ES/NQ transferability

**Classification: MAJOR.** Evidence from ES does not automatically transfer to NQ, and pooled ES/NQ evidence does not establish either instrument’s mechanism. The instruments differ in volatility, liquidity, tick size, session behavior, and cross-market lead/lag; those differences can change effective sample size, label entropy, persistence, and the useful temporal receptive field. Any transfer claim must be conditional on identical information-clock, target, fold, eligibility, and metric rules, with instrument-specific results retained. An ES-only capacity conclusion is insufficient for NQ; an NQ-only conclusion is insufficient for ES.

## 14. Public methodology evidence and limits

**Classification: INFORMATIONAL.** Tashman (2000) supports explicit forecast origins and update rules; Kaufman et al. (2012) supports point-in-time leakage controls; Gneiting and Raftery (2007) supports proper probabilistic scoring; Diebold and Mariano (1995) supports dependence-aware paired forecast comparison under its assumptions; Varma and Simon (2006), White (2000), Bailey et al. (2017), and Cawley and Talbot (2010) support treating repeated selection as a source of optimistic bias. These sources support controls, not this object’s architecture, feature usefulness, profitability, or transferability. The immutable registry records these boundaries.

## 15. Required evidence and disposition for R1

**Classification: BLOCKER.** R1 has four blockers before it can support a capacity or underfitting conclusion: (1) no frozen dependence-aware effective-sample accounting; (2) no complete, predeclared selection and multiplicity rule over the full grid; (3) no proof that model-specific availability, missingness, synchronization, and abstention use a common paired denominator; and (4) no cell-specific evidence separating architecture capacity from optimization and target geometry. The minimum acceptable disposition is “capacity conclusion withheld.” A descriptive protocol review may record these as open controls, but R1 must not promote a selected cell or architecture as validated evidence.

## 16. Freeze, sources, and safety attestation

No new public source was added to the existing registry: **0**. Sources consulted or relied on are the immutable Phase 5C methodology ledger entries R01, R05, R09, R14, R18, R19, R20, and R21, with R20 being Cawley & Talbot (2010), “On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation,” JMLR 11, 2079–2107: https://www.jmlr.org/papers/v11/cawley10a.html.

This memo is the only intended file change. It contains no protected outputs, out-of-scope data/features/labels/manifests, source code, tests, training/inference/scoring/benchmark/backtest/trading instructions, installation actions, or Git mutations. Completion UTC: `2026-09-25T06:23:07Z`. Final file SHA256 is reported in the handoff. Expected identities supplied by the task are preserved verbatim: R20 `A6391B77B2D251B6DB5BB8AF9919316380EDCA7FF80D7B4B1A302887E05827DE`; review freeze `F3D295541151A251401E6DED7062D655E2E390B58F0B15C40B87083E097D9553`.
