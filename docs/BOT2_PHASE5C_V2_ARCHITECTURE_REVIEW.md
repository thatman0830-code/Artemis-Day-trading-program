# BOT 2.0 Phase 5C v2 Architecture Review

**Review result:** not approved for scoring. This is a pre-scoring engineering review artifact; no A0, A1, or A2 scores were run and no OOS/walk-forward model performance was inspected.

**Reviewer independence:** this review was prepared by the implementation agent in the same task. No separate independent reviewer was assigned or available. The required independent gate is therefore not satisfied; this document must not be read as independent approval.

## Review checklist

| # | Required check | Finding |
|---:|---|---|
| 1 | Causal inputs | PASS. Feature cutoff is T; v3 feature code reads current/past source timestamps only. Cross-market values require the exact same session/timestamp and prior minute. Future-mutation tests cover the feature prefix. |
| 2 | Future targets | PASS. The v3 target uses future closes only for labels; the target is kept separate from `FeatureRow.values`. |
| 3 | No circular labels | PASS. Feature generation does not consume target rows; sequence construction appends a separate target triplet only after selecting the input values. |
| 4 | Cadence correctness | PASS. 60-second elapsed cadence is explicit and evaluated inside exact archived calendar active intervals, sessions, and listed contracts. Calendar closure crossings are separately counted; no closed interval is called a missing bar. |
| 5 | Rolling-window correctness | PASS. Elapsed windows demand each exact timestamp; feature gaps remain null/reason-coded. |
| 6 | Sequence correctness | PASS. Eight rows require seven exact one-minute deltas and stable session/contract identity; gaps are not compressed. Deterministic rejection counts are tested. |
| 7 | Target-horizon correctness | PASS. 5/15/30-minute labels require exactly H future one-minute observations, a continuous 30-return causal reference, and stable session/contract identity; there is no shortened horizon or fill. |
| 8 | ES/NQ synchronization | PASS. Only exact same-session timestamps match; no forward fill, nearest neighbor, or future observation is used. Missing-side tests cover either ES or NQ. |
| 9 | Split integrity | PASS AS SPECIFIED. Main dates preserve v1 and four fixed walk-forward test windows end before the main OOS period. Actual scoring/row assignment has not been implemented or run. |
| 10 | Purge correctness | SPECIFIED, NOT RUN. The frozen rule uses full label-information end and a 30-minute purge. No Phase 5C partition runner currently proves every row obeys it. |
| 11 | Embargo correctness | SPECIFIED, NOT RUN. A 30-minute post-boundary embargo is defined, but no Phase 5C runner currently applies and audits it. |
| 12 | Training-only preprocessing | PARTIAL. The standardizer is deterministic and its isolation test passes; the v2 protocol specifies unique training rows and fold-specific fit scope. No v2 orchestrator currently guarantees training-only fit in each fold. |
| 13 | Calibration isolation | SPECIFIED, NOT IMPLEMENTED. Validation-only temperature scaling, deterministic search grid, and reliability-bin rules are frozen, but no v2 calibrator/evaluation path enforces isolation. |
| 14 | Baseline fairness | SPECIFIED, NOT IMPLEMENTED. A0 rules and validation baseline-selection tie-break are explicit, and the identical eligible comparison intersection is required. No Phase 5C runner currently creates and verifies that intersection. |
| 15 | Class-imbalance methodology | PASS AS SPECIFIED. No weights, resampling, or synthetic examples; unweighted multihead loss and class reporting are frozen. |
| 16 | Shuffled-label methodology | SPECIFIED, NOT IMPLEMENTED. TRAIN-only within-contract/session/head/horizon permutation, fixed seeds, family size, and stop rule are stated; no executable control harness exists. |
| 17 | Ablation specification | SPECIFIED, NOT IMPLEMENTED. Feature family names and exclusions are frozen; no ablation runner verifies exact projections or common-row comparisons. |
| 18 | Abstention specification | SPECIFIED, NOT IMPLEMENTED. Entropy, disagreement, validation threshold selection, tie policy, and coverage values are frozen; no v2 output path applies them yet. |
| 19 | Immutable protocol completeness | PASS AS FROZEN SPECIFICATION. The new v2 manifest preserves v1 and Phase 5B hashes, pins the implementation, feature registry and final data report, and has a verified canonical manifest SHA-256. Scoring remains prohibited. |
| 20 | Reproducibility | PARTIAL. Deterministic v3 feature/target/sequence tests pass, archive inputs and report hashes are pinned, and the full regression suite passed. The complete Phase 5C experiment runner is absent. |

## Blocking findings

1. **A2 identity mismatch:** the named candidate is a causal temporal-convolution model, but `CausalTemporalConv.transform` is a fixed mean/endpoint/difference summary followed by an MLP. It contains no learned convolutional kernel. The protocol discloses the code as-is, but this does not satisfy the requested A2 architecture identity. The discrepancy requires an explicitly reviewed resolution and a new immutable protocol revision if the architecture changes.
2. **No executable Phase 5C evaluator:** current code does not implement one deterministic v2 run path for fixed splits, purge/embargo, train-only preprocessing, baseline selection, calibration, all-seed aggregation, session bootstrap, shuffled-label control, ablations, and abstention. The written protocol alone is not yet an executable experiment.
3. **No independent architecture reviewer:** this artifact was authored by the implementation agent. A separate reviewer must verify the implementation and protocol before any scoring authorization can be considered.
## Verification evidence

- Implementation commits on this branch: `c47eb3c62aebc3bb7500125f1988377d67b52e70` and `c4e56ed0346e37a3cbb8492f0da3758d771b504d`.
- Phase 5B dataset manifest SHA-256: `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`.
- v3 feature registry SHA-256: `a0c32f664d76bf6e971c5c30cd002fba3aec57826d60f920c24596e70e6fcd3c`.
- Full-archive eligibility report SHA-256: `a6b7b7e398f10de8439c435f48de64468f5843221621be3ef2412e8c1210cba5`.
- Canonical Phase 5C v2 manifest SHA-256: `e805a78d552bc6c04d5665c818a9022dec7eb0a4da5e4db1432f28246e1973bb`.
- Complete repository regression suite: **5,582 passed, 10 skipped, 0 failed** (`pytest -q -p no:cacheprovider`).
- Focused data/features/neural/regime suite: **41 passed** (`bot2/data_foundation/test_cadence.py`, `bot2/features_labels`, `bot2/neural`, `bot2/regimes`).
- OOS, walk-forward model, baseline, A1, and A2 scoring: **not run**.

No model scoring is permitted under this review result. Production strategy, risk, broker execution, paper-order behavior, live-trading behavior, and trading authority were not changed.

NOT APPROVED — BLOCKERS REMAIN
