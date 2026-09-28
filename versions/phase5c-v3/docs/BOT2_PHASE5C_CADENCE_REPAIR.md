# BOT 2.0 Phase 5C-P — Cadence Repair and Data Eligibility

## Scope and safety

This work repairs elapsed-time semantics and measures data eligibility for the frozen Pass B ES/NQ archive. It does not fit A0/A1/A2, produce predictions or model-performance scores, inspect OOS performance, alter production risk/execution, or grant trading authority. No synthetic bars or timestamp fills are created.

## Source and cadence contract

The source is the promoted Databento Pass B v3 normalized OHLCV archive, pinned by Phase 5B dataset-manifest SHA-256 `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`, for 2025-06-02 through 2026-08-26 inclusive. Bars are one-minute aggregates. The archive's normalized timestamp is the bar close, sourced from exchange-event windows. Local receipt timestamps are unavailable and remain null; they are not reconstructed.

`expected_interval=60 seconds`. `actual_elapsed_interval=right.exchange_time-left.exchange_time`, computed only within the same exact listed contract, source session, and archive-calendar active interval. Exchange bars are timestamped by close, so a close at the active interval's exclusive end is associated with that interval. `missing_interval_count=ceil(actual_elapsed_interval/60)-1` for positive within-interval deltas; an exact 60-second delta is cadence-valid. Irregular non-minute deltas are `CADENCE_VIOLATION`; longer exact-minute deltas are `MISSING_INTERVALS`. Duplicate/regressing times fail before the audit. The first observation in each active interval has no preceding in-interval pair and is reported separately, not imputed or counted as a valid adjacent pair. Calendar-declared closures, session boundaries, and roll-contract boundaries are not gaps because comparisons never cross those boundaries. Consecutive observations straddling a calendar closure are counted separately as excluded closure crossings.

The archive records `SPARSE_NO_ELIGIBLE_TRADE_AGGREGATE`. That source classification does not prove whether an absent minute had no eligible trade or was omitted by the provider/archive. The audit preserves this uncertainty. It does not relabel these minutes as confirmed feed outages or confirmed no-trade intervals.

## Feature audit

The Phase 2 feature set now uses registry v3 (`bot2-feature-registry-v3`) with explicitly elapsed-time names. Return and range windows require the endpoint and every intervening exact one-minute timestamp. Realized volatility requires exactly the named number of one-minute returns. Relative volume uses the current observation divided by the mean of the three exact prior one-minute observations; volume acceleration compares only the exact prior minute. Session cumulative volume/VWAP and session extrema summarize observed bars only and do not insert zero-volume bars. Cross-market values require exact same-session ES/NQ timestamps; rolling correlation requires six synchronized timestamps/five returns. A missing own or counterpart timestamp yields null plus a reason code; there is no forward fill.

The immutable registry is `config/bot2_feature_registry_v3.json`; schema is `bot2-feature-row-v3`. Older row-count feature keys remain compatibility aliases for Phase 4 callers only and are expressly excluded from the v3 model registry. Feature eligibility percentage is the fraction of source observations with every registered input non-null (finite numeric values are guaranteed by archive validation); partial feature rows remain descriptive but cannot enter a model sequence.

## Sequence and target audit

Sequence length is eight observations with exactly 60 seconds between every pair, one session and exact listed contract only, and all 24 registered v3 inputs present at every timestep. A missing minute is not compressed. Rejections are counted as `SEQUENCE_GAP`, `CADENCE_VIOLATION`, `SESSION_BOUNDARY`, `CONTRACT_BOUNDARY`, `REQUIRED_FEATURE_UNAVAILABLE`, `INVALID_TARGET`, or `INSUFFICIENT_CONTIGUOUS_HISTORY`.

Targets use Phase 5B's frozen `bot2-future-market-state-v3` formulas and 5/15/30 elapsed-minute horizons. Each future window must contain exactly H subsequent one-minute observations in the same session and listed contract. Its causal volatility reference requires the prior 30 consecutive one-minute returns, ending at T. Missing future/reference observations invalidate that label with a machine-readable reason; horizon is never shortened and no fill is used. Labels remain future-only and are not inputs. Target generation was audited for eligibility only; no target distributions were re-estimated here.

## ES/NQ synchronization

Synchronization is exact session plus timestamp, preserving each listed contract identity. One market missing a timestamp makes that pair unavailable. There is no nearest-neighbor match, tolerance, forward fill, or future fill. The eligible-data audit reports root-specific aligned percentages using each root's archive observation count as denominator.

## Results

The complete machine-readable output, including archive-wide gap sizes/reasons, sessions affected, per-feature eligibility, target eligibility by horizon, sequence eligibility by horizon, and exact alignment rates, is `docs/BOT2_PHASE5C_DATA_ELIGIBILITY.json`. The report pins the Phase 5B dataset manifest and is generated by `scripts/bot2_phase5c_cadence_audit.py`. It performs deterministic data/label eligibility checks only; it does not run any baseline or neural scoring.

| Measure | ES | NQ |
|---|---:|---:|
| Archive observations | 438,873 | 438,806 |
| Valid within-active-interval adjacent pairs | 438,503 / 438,551 | 438,387 / 438,484 |
| Invalid within-active-interval gap pairs | 48 | 97 |
| Missing minutes between observed bars (within active intervals) | 104 | 211 |
| Calendar-closure crossings excluded | 9 | 9 |
| Sessions with observed cadence gaps | 33 | 27 |
| Source quality episodes / source-classified missing minutes | 53 / 2,217 | 101 / 2,284 |
| All 24 feature rows eligible | 99.4144% | 99.4296% |
| 8-step sequences eligible, 5m / 15m / 30m targets | 97.1622% / 96.3436% / 95.1205% | 97.0832% / 96.2441% / 94.9926% |
| Targets eligible, 5m / 15m / 30m | 97.0828% / 96.2581% / 95.0314% | 96.9100% / 96.0618% / 94.8039% |
| Exact ES/NQ timestamp alignment | 99.9658% | 99.9811% |

The adjacent-bar gap counts differ from source quality episode counts because source quality includes missing runs at active-interval edges that cannot be represented as a pair between two observed bars. The report preserves both measures and their meanings. The source reason remains ambiguous, so the archive's missing-minute totals are not described as confirmed feed outages.

The audit uses historical exchange timestamps and the exact active intervals from the archive's hash-pinned session calendar. This distinction matters: the first exploratory pass that grouped solely by session date incorrectly counted holiday/maintenance closures as thousands of missing minutes. The final implementation splits cadence checks at each archived active interval and separately counts the excluded calendar-closure crossings. It does not infer closures from adjacent rows. The source's sparse-gap label remains ambiguous as described above.

## Changed implementation

- `bot2/data_foundation/cadence.py`: expected one-minute cadence, explicit elapsed intervals, missing-slot counts, and reason-coded gaps.
- `bot2/features_labels/contracts.py`, `features.py`, schema, and registry: v3 elapsed-time contracts and exact-window feature generation.
- `bot2/features_labels/targets_v3.py`: contract identity is checked in past-reference and future windows; elapsed horizon checks remain fail-closed.
- `bot2/neural/sequences.py`: cadence/session/contract/input/target gates and deterministic rejection counts.
- `bot2/regimes/assign.py`: maps old Phase 4 names to the corresponding v3 inputs without changing v3 model registry membership.
- Tests cover missing/irregular cadence, exact elapsed feature windows, future gaps and contract/session boundaries, causal mutation, exact cross-market inputs, deterministic sequence gates, and cadence gap statistics.

Verification: focused cadence/features/neural/regime tests passed (41 passed); full repository regression passed (5,582 passed, 10 skipped, 0 failed). No A0/A1/A2 model scoring was executed.

The unrelated pre-existing workspace modifications are not part of this phase and were not staged.
