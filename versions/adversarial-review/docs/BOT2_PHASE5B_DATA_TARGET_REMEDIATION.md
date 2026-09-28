# BOT 2.0 Phase 5B — Data and Future-Target Remediation

Status: **READY FOR PHASE 5C REAL-DATA MODEL A EVALUATION.** Phase 5B corrected historical timestamp semantics, exact-contract/root synchronization, and circular current-state targets. This readiness decision is based on the data/target/protocol gates only; no Model A performance results were produced or inspected. The 5C manifest is frozen and committed with this report before any future model evaluation. This is a research readiness statement, not evidence of trading skill, profitability, or execution readiness.

## 1. Timestamp remediation

Phase 1's versioned market-event contract explicitly distinguishes `event_timestamp`, nullable `receive_timestamp`, `receive_timestamp_available`, and `timestamp_source`. Historical promoted Databento bars are marked `HISTORICAL_EXCHANGE_EVENT`, with receipt time unavailable; event time is never copied into the receipt field. Tests reject a historical event that claims a genuine receipt time, and live events retain separate exchange/receipt times and measured latency when supplied. Research work that does not need latency uses event time. Receipt-latency/staleness-at-receipt analyses remain unavailable for these archives.

The archive adapter's normalized one-minute bar close is used as the observation timestamp. This is exchange-event timing, not the original packet arrival time.

## 2. Contract inventory

Canonical identity keeps `root_symbol`, exact `contract_symbol`, `expiry`, `venue`, and source `instrument_id` distinct. All 313 sessions per market retain the six actual listed contracts; exact inventory, row counts, and session spans are in the [real research dataset manifest](../outputs/bot2_phase5b/real_es_nq_research_dataset_manifest_v2.json).

| Root | Contracts in archive |
|---|---|
| ES | ESM5, ESU5, ESZ5, ESH6, ESM6, ESU6 |
| NQ | NQM5, NQU5, NQZ5, NQH6, NQM6, NQU6 |

No contract symbols are collapsed to `ES`/`NQ` in the source observations, and no contracts are silently concatenated into a synthetic price history.

## 3. Roll methodology

The promoted archive's frozen `OWNER_TWO_SESSION_VOLUME_CROSSOVER_SPARSE_V2` metadata uses two consecutive finalized-volume crossover observations; the decision is made from the preceding evidence sessions and takes effect on the next session. This Phase 5B work inspected and preserved that pre-existing policy; it did not select or tune a roll rule from model outcomes. ES effective transitions were 2025-06-18, 2025-09-17, 2025-12-17, 2026-03-18, and 2026-06-17. NQ transitions were 2025-06-18, 2025-09-18, 2025-12-17, 2026-03-18, and 2026-06-17. Each market traverses six expiries and five transitions. The source archive reports no continuous adjustment and zero synthesized rows. Original OHLCV and contract IDs remain unadjusted; rollover is session-selection metadata only.

## 4. Synchronization results

Synchronization uses exact `(root, session_id, exchange bar-close timestamp)` keys; the ES and NQ contract symbols and expiry identities remain available on both matched sides. No nearest-time substitution and no future forward-fill are allowed.

| Measure | ES | NQ |
|---|---:|---:|
| Source observations | 438,873 | 438,806 |
| Exact paired observations | 438,723 | 438,723 |
| Unmatched | 150 | 83 |
| Exact match rate | 99.9658% | 99.9811% |
| Unmatched observations on an effective roll session | 26 | 3 |

There are 1,350 exact root/session/time matches where ES and NQ expiries differ. This is recorded rather than hidden; the pair is synchronized in time/root, not asserted to be the same expiry. Remaining unmatched observations reflect sparse/missing archive minutes and other boundary effects. Session mismatch count is zero. Full statistics and source hashes are in the dataset manifest.

## 5. Future-target mathematical specification

Phase 4's deterministic regime remains a causal, interpretable current-state baseline, but it is not used as a neural target. The first independent-target draft (v2) used train-sample volatility quantiles; that draft was superseded before any performance evaluation because sample-balanced cutpoints were not the desired market-state semantics. The frozen target contract is **`bot2-future-market-state-v3`** (`future-target-row-v3`):

- **Direction:** `UP` if `close[T+H] - close[T] >= one tick`, `DOWN` if at most minus one tick, otherwise `FLAT`.
- **Volatility:** future realized volatility is `sqrt(mean(r²))` over exactly H future one-minute log returns. Divide by realized volatility over the 30 consecutive one-minute returns ending at T, same exact contract and session. Fixed thresholds are ratio `<0.8 LOW`, `0.8–1.2 NORMAL` inclusive, and `>1.2 HIGH`; no data-derived class balancing or OOS-fitted thresholds.
- **Structure:** path efficiency is `abs(log(close[T+H]/close[T])) / sum(abs(future one-minute log returns))`. `TREND` requires efficiency ≥0.60 and displacement ≥4 ticks; `RANGE` requires efficiency ≤0.25; otherwise `TRANSITION`.
- Future observations are closes T+1 through T+H, exactly one minute apart, same session and exact listed contract. Gaps, insufficient history, session/contract boundaries, and invalid trailing-volatility references produce reason-coded invalid targets; no fill is used.
- For valid v3 rows, the full label-information interval is `[T−30 minutes, T+H]` because of the causal volatility reference; the future-only subinterval is `[T+1, T+H]`. `label_end_time` is the final future close.

## 6. Input/target dependency audit

The feature engine receives bars at or before T only. Its cross-market lookups use the exact current session/time and exact prior-minute timestamp under canonical ES/NQ root groups; absent pairs remain unavailable rather than filled. Synthetic mutation tests change post-T data and prove `FEATURES(T)` is byte/value-stable while the future label may change.

The v3 direction/structure targets are computed only from prices after T. No input feature directly computes these future outcomes, so they are not Phase 4 self-label imitation. The v3 volatility target does intentionally compare future volatility with a trailing, causal 30-minute reference; that reference overlaps conceptually with past realized-volatility features and may be a learnable proxy, but it contains no information after T and does not algebraically determine future volatility. This near-dependency is disclosed for Phase 5C ablation/interpretation. Adjacent samples have overlapping future windows by design, so target persistence is high at longer horizons; the reported persistence is label autocorrelation, **not predictive accuracy**. The label-information interval is carried into split purging.

## 7. Horizons

The frozen set is 5, 15, and 30 one-minute bars. Five minutes captures short intraday movement; 15 minutes spans a modest intraday swing; 30 minutes represents a broader but still intraday state. These are fixed in the target spec before any model evaluation; no horizon search was performed.

## 8. Target distributions and class-collapse audit

The [target-distribution artifact](../outputs/bot2_phase5b/target_distributions_v3.json) records all 18 root × chronological split × horizon cells, every head's counts/shares, invalid reason codes, and session segments. Target labels are reported for the chronological OOS date window only as requested class-frequency diagnostics; **no OOS model output or score was generated**.

Across the archive, direction is broadly balanced between up/down, with FLAT especially rare for NQ at 15/30 minutes. Fixed-reference volatility states remain represented across splits (roughly 23–28% HIGH, 25–42% LOW, and 34–48% NORMAL depending on root/horizon/split). Thirty-minute TREND is rare (about 0.5–0.7%) for both roots. The analyzer flags 13 root/split/horizon/head cells as severe when a class is under 1% or one class reaches 95%; no target cell is completely collapsed to a single class. Thresholds were not changed to equalize classes. Phase 5C must report per-class metrics and uncertainty, and must not interpret macro-averages as sufficient when these rare classes are present.

Per-split valid counts, frequencies, shares, and invalid-reason counts are in the JSON to avoid hiding ES/NQ or chronological-window differences. The key stable observation is that rare NQ FLAT and 30-minute TREND classes remain rare in TRAIN, VALIDATION, and OOS_TEST rather than appearing only in one period.

## 9. Target stability and session dependence

Across adjacent valid one-minute anchors within the same exact contract/session, observed persistence (transition frequency in parentheses) was:

| Horizon | Direction ES / NQ | Volatility ES / NQ | Structure ES / NQ |
|---|---|---|---|
| 5m | 73.7% / 77.7% (26.3% / 22.3%) | 75.7% / 75.7% (24.3% / 24.3%) | 51.3% / 51.0% (48.7% / 49.0%) |
| 15m | 84.7% / 87.1% (15.3% / 12.9%) | 87.1% / 87.2% (12.9% / 12.8%) | 78.2% / 78.4% (21.8% / 21.6%) |
| 30m | 89.1% / 90.9% (10.9% / 9.1%) | 91.2% / 91.2% (8.8% / 8.8%) | 90.3% / 90.3% (9.7% / 9.7%) |

Longer-horizon persistence is expected from the overlapping target windows and is why Phase 5C includes past-label persistence and train-only transition baselines. Session dependence is tabulated by first 120 observed minutes, middle, and last 120 observed minutes (relative to each actual archive session's first/last bar, not a guessed exchange schedule). Direction and volatility frequencies vary by segment, especially near the session ends; the detailed counts are in the JSON. The archive windows are similar across chronological splits for the common direction/volatility heads, while the sparse classes above remain an evaluation caveat.

## 10. Purge and embargo changes

`chronological_split` now uses each row's `label_end_time`: it purges TRAIN rows whose label end plus the configured purge reaches the validation boundary, and VALIDATION rows whose label end plus purge reaches the test boundary. Embargo applies at the start of both validation and test. Phase 5C freezes 30-minute purge and 30-minute embargo, covering the maximum 30-minute future horizon; boundary tests prove labels touching protected periods are removed. No feature or label may use future-forward-fill.

## 11. Future-prediction baselines

The frozen Phase 5C manifest specifies three non-neural references, all scored with the same eligible rows and split boundaries as Model A:

1. **Previous-label persistence:** carry forward the most recent same-head label whose entire information interval ended no later than the prediction time; abstain if unavailable.
2. **TRAIN majority:** per root/head/horizon class majority computed on TRAIN only, with lexical tie-break.
3. **TRAIN transition matrix:** one-step label transition probabilities estimated on TRAIN only with fixed Laplace α=1 smoothing, conditioned only on the most recent eligible past label.

Uniform probability remains an additional no-skill reference. Phase 5C candidate A1/A2 must be compared to these baselines, with calibration fitted only on validation; the manifest pins log loss, Brier, per-class/balanced metrics, confusion matrix, reliability/coverage, and latency. No baseline or model has been run in Phase 5B.

## 12. Reproducible research dataset manifest

The regenerated [dataset manifest](../outputs/bot2_phase5b/real_es_nq_research_dataset_manifest_v2.json) records the 313-session common window, ES 438,873 rows, NQ 438,806 rows, 438,723 exact alignments, 2025-06-02–2026-08-26 date range, full contract inventory, frozen roll version/transitions, event-only timestamp provenance, feature registry v2, target v3 and 5/15/30 horizons, data-quality/missing-minute counts, Phase 1 validation hashes, archive fingerprints, raw archive/roll/calendar hashes, target spec/distribution hashes, code commit, canonical manifest SHA-256, and `trading_authority: false`. Hashing is SHA-256 over canonical sorted compact JSON excluding the self-hash field.

## 13. New frozen Phase 5C experiment specification

The new [Phase 5C manifest](../config/bot2_phase5c_experiment_manifest_v1.json) references the regenerated dataset-manifest hash and target spec v3; it fixes chronological dates, three seeds, sequence length 8, baselines, candidate models, metrics, validation-only calibration, purge/embargo, and the requirement for separate architecture review before OOS evaluation. It is distinct from and does not modify Phase 5A. The new manifest and this report are committed before any Phase 5C performance evaluation.

## 14. Tests

Command: `.venv\Scripts\python.exe -m pytest bot2 backtesting\test_core_v1_production_adapters.py -q -p no:cacheprovider`

Result: **71 passed**. Coverage includes historical-vs-live timestamp provenance, unavailable receipt timestamps, canonical contract/root/expiry normalization, exact-root synchronization/no-forward-fill/expiry mismatch, deterministic target regeneration, future mutation affecting labels but not features at T, fixed causal-volatility semantics, strict future window/horizon boundary, gap/session rejection, and purge/embargo boundaries. Existing Phase 1–5A and production-adapter regression tests in the selected suite also passed. The tests are synthetic engineering fixtures, not ES/NQ predictive evidence.

## 15. Remaining limitations

- Genuine local receipt timestamps are absent from the historical archives. Exchange-time research is possible; receipt latency and arrival-time freshness remain unmeasurable.
- Thirteen target-frequency cells meet the predeclared severe-imbalance flag (mostly rare NQ FLAT and 30-minute TREND). Preserve the definitions and treat those head/cells cautiously; do not rebalance labels after looking at results.
- Phase 5B generated and audited real future-target distributions, not model performance or full inference latency. Phase 5C must validate/materialize its exact feature inputs and their availability before scoring.
- ES/NQ time-aligned pairs sometimes have different expiries; exact IDs and the 1,350 mismatch count remain explicit. No claim is made that different-expiry contracts are interchangeable.

These are declared evaluation constraints, not unresolved structural blockers to a bounded Phase 5C research evaluation. The Phase 5C manifest also requires a separate architecture review before OOS scoring. No Phase 5C evaluation is authorized by this completion report.

## 16. Files changed

Phase 5B changes are in the commits listed below. New generated artifacts are the target-distribution JSON, research-dataset manifest, Phase 5C manifest, and this report. The Phase 5A frozen manifest and archived artifacts were not edited. Pre-existing unrelated worktree modifications were left untouched and are not included in the Phase 5B commits.

## 17. Branch and commits

- Branch: `bot2-phase5b-data-target-remediation`, descended from the Phase 5A line.
- Phase 5A frozen-manifest commit: `bd6312c`; canonical manifest SHA-256 remains `35188dd73aa2fc94b3e2a4ecffcd7e750d367205e7abeed86de863e6a23181b4`.
- Phase 5B commits: `fb0f0dd` (timestamp/identity/synchronization and initial future target), `bac49b0` (causal fixed-threshold target v3), `da5b1db` (determinism test and frozen baselines/analyzer output naming).
- The Phase 5C manifest and report are committed together after this report is finalized; the resulting commit is shown in the completion summary.

**READY FOR PHASE 5C REAL-DATA MODEL A EVALUATION**

Phase 5B is complete. Stop here. No Model A scores, Model B, execution, production risk, broker behavior, or live-trading settings were changed.
