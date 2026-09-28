# BOT 2.0 Phase 5A — Real ES/NQ Validation

Status: **STOPPED BEFORE MODEL EVALUATION — C / INCONCLUSIVE.** The promoted archive is substantial and integrity-verified, but the current inputs do not support the requested independent, apples-to-apples regime-learning test. No OOS labels, model outputs, or OOS metrics were inspected or generated. No conclusion about trading performance is made.

Branch: `bot2-phase5a-real-esnq-validation`  
Frozen protocol commit: `bd6312c` (`Freeze BOT2 Phase 5A ES NQ experiment protocol`)  
Manifest: [`config/bot2_phase5a_experiment_manifest_v1.json`](../config/bot2_phase5a_experiment_manifest_v1.json)  
Canonical manifest SHA-256: `35188dd73aa2fc94b3e2a4ecffcd7e750d367205e7abeed86de863e6a23181b4`

The manifest was committed before any OOS result inspection. It fixes source identities, features/targets, seed set, sequence length, A0/A1/A2 candidates, chronological and walk-forward windows, purge/embargo, controls, and intended metrics. It explicitly excludes the short connectivity probe and prohibits continuous-contract stitching. No later result was used to alter the frozen protocol.

## 1. Real dataset inventory

Read-only `PassBV3ArchiveAdapter.validate()` checks succeeded for both promoted Databento Pass B v3 archives. The validated normalized data is one-minute OHLCV, not tick/order-book data.

| Market | Exact contracts | Bars | Trading sessions | Trading-date coverage |
|---|---|---:|---:|---|
| ES | ESM5, ESU5, ESZ5, ESH6, ESM6, ESU6 | 438,873 | 313 | 2025-06-02–2026-08-26 |
| NQ | NQM5, NQU5, NQZ5, NQH6, NQM6, NQU6 | 438,806 | 313 | 2025-06-02–2026-08-26 |

The archive metadata's UTC coverage begins `2025-06-01T22:00Z` because the first exchange session begins on the prior UTC date; its final available bars are on 2026-08-26. Contract observations are kept under their exact listed symbols. The frozen calendar and active-window/roll decisions identify which contract is active in each session. The archive audit reports `continuous_adjustment: false` and `synthesized_rows: 0`: there is no continuous or back-adjusted series. Rollover is metadata describing a switch between actual listed contracts; it is not a price adjustment or permission to merge them silently.

The separate live historical connectivity probe is `GLBX.MDP3 / ohlcv-1m`, two micro instruments (`MES.v.0`, `MNQ.v.0`), 10 records over five minutes. It is excluded from this historical evaluation and is not a substitute for the 15-month archive.

## 2. Dataset hashes and provenance

| Market | Dataset ID | Promoted normalized archive fingerprint |
|---|---|---|
| ES | `bc3dc017c7e871942873e63bd8e552860fb6b8e835e341ad7441dca5274f6464` | `857fbdcfe324db45b88a364ac3923a5f23ae12017851d93140be3e23a6bd13d4` |
| NQ | `831ba675ee5fb1aeb00a8b4cb43f19064d3487bd50a6c743ce8acc68e1fb7d7e` | `8cc8cb7f803e2de7f7d63f3652feafe8162d16106fd05f11f60cba5dcf7fc323` |

The archive adapter rechecks its signed-by-hash promoted audit, tree fingerprint, plan/calendar/rollover artifacts, request manifests, checkpoints, raw-to-normalized economic lineage, exact contract IDs, session intervals, ordering, row totals, and sparse missing-minute classifications before yielding bars. The Phase 5A manifest also pins these archive identities and its own canonical hash. The repository Phase 1 `DatasetManifest` was **not** emitted: its `MarketEvent` requires a receipt timestamp, which these historical normalized records do not contain. Assigning receipt=exchange time would fabricate zero latency and is intentionally not done.

## 3. Quality report and Phase 1 gate

The promoted archive adapter accepted all 877,679 observed bars and reported no malformed geometry, hash/lineage conflict, duplicate, or out-of-order normalized row. Sparse trade-aggregate absences remain explicit quality data, not silently filled bars:

| Market | Missing-aggregate episodes | Missing one-minute intervals | Sessions containing episodes |
|---|---:|---:|---:|
| ES | 53 | 2,217 | 36 |
| NQ | 101 | 2,284 | 29 |

The archive classifies these as `SPARSE_NO_ELIGIBLE_TRADE_AGGREGATE`. They must be preserved/reported and are not evidence of continuous minute-by-minute trades. Historical local receipt time is unavailable, so staleness-at-receipt and exchange-to-local latency cannot be validated from this archive. For that reason, Phase 1's full raw `MarketEvent` validation/manifest gate is **not passed** for this source; no synthetic timestamp was introduced to make it pass.

## 4. ES/NQ synchronization integrity

Exact `(session_id, one-minute bar close timestamp)` set comparison found 438,723 aligned bars across the 313 common sessions. ES had 150 unmatched bars and NQ had 83 unmatched bars. No forward fill or nearest-neighbor substitution was used. This is strong bar-level synchronization evidence, but it does not restore missing local receipt clocks or make every row pairable.

There is also a Phase 2 integration gap: current cross-market feature lookup is keyed to literal instruments `ES` and `NQ`, while the verified archive correctly exposes exact tickers such as `ESU6` and `NQU6`. The existing feature call therefore cannot safely derive cross-market fields from this archive without a contract-aware synchronization adapter. Those fields were not fabricated, and no all-features Model A run was attempted.

## 5. Real feature statistics

Not generated. The Phase 1 receipt-clock requirement is unmet, and the frozen `ALL` feature set includes cross-market inputs that do not currently resolve against exact-contract archive identifiers. A per-contract Phase 2 run could produce non-cross-market features, but it would not satisfy the approved all-family experiment in the frozen manifest. Feature invalid/missing rates, distributions, and warm-up/synchronization loss are therefore **not measured** in this Phase 5A stop.

## 6. Real regime statistics

Not generated. Without an approved completed Phase 1 → Phase 2 data path for the frozen inputs, regime frequencies, durations, persistence, transitions, churn, and per-head degeneracy would be incomplete and potentially misleading. No class definition was changed to compensate.

## 7. Frozen experiment specification

The committed manifest sets: feature registry `bot2-feature-registry-v1`; target config `bot2-regime-config-v1`; endpoint sequence length 8 with session/contract boundaries; seeds 1, 2, 3; A0 Phase 4 deterministic rule, A1 existing NumPy multihead MLP (width 8, learning rate 0.01, 50 epochs), and A2 the existing fixed causal temporal transform plus the same NumPy multihead head. No Transformer/LSTM/GRU or learned convolution was added.

Chronological train/validation/OOS and four walk-forward windows are frozen in the JSON. Splits are by trading date per instrument, with five-observation purge and five-minute embargo. The manifest also freezes per-head/per-instrument metrics, majority/uniform no-skill references, validation-only temperature scaling, 10 reliability bins, entropy-ordered abstention coverage, train-only shuffled-label control (seed 17), and six named feature-family ablations. The protocol's target caveat below prevents those model steps from being run against the present target source.

## 8. Critical target-validity finding

Phase 4 `RegimeAssignment` derives direction, volatility, structure, and primary state deterministically from the same endpoint features (including `log_return_3`, realized volatility, and rolling range). Phase 5A's current A1/A2 training targets are proposed to be those same Phase 4 outputs. Thus A1/A2 would be trained to imitate a deterministic function of their inputs; A0 is that exact rule. This is **self-label imitation**, not independent evidence that Model A learned a regime relationship that generalizes beyond the baseline. Perfect A0 agreement would be true by construction, not a meaningful OOS discovery. A neural score relative to this oracle cannot satisfy the stated scientific question.

This is a target-design blocker, not a class-balance issue. Replacing labels, changing the Phase 4 definitions, or relabeling them after seeing results would violate the frozen protocol. No label shuffle, calibration, abstention, ablation, or model run was used to disguise the problem.

## 9–20. Model results, controls, calibration, and latency

| Required result | Phase 5A status |
|---|---|
| A0/A1/A2 OOS metrics and confusion matrices | Not run: no valid independent target/evaluation question |
| Multiple-seed and walk-forward results | Not run |
| Direction / volatility / structure head comparison | Not run |
| ES / NQ separate model results | Not run |
| Calibration and reliability bins | Not run |
| Entropy / disagreement / abstention coverage-reliability | Not run |
| Shuffled-label leakage control | Not run; no model evaluation reached |
| Controlled feature ablations | Not run |
| Real-sequence inference latency / throughput | Not run |
| Overfit/seed instability assessment | Not available |

These are marked unavailable rather than estimated or inferred. No classification score would establish profitable trading, expectancy, entry accuracy, execution viability, or future profitability.

## 21. Limitations

1. The archive has no original local receipt timestamp; Phase 1 cannot truthfully validate dual-clock latency/freshness or produce its canonical manifest for these rows without a schema/provenance decision.
2. Phase 2 cross-market lookup does not currently map exact futures contract tickers through active-window roll facts; synchronized bars exist, but cross-market features are not yet safely produced from this archive.
3. The Phase 4 regime states are self-generated labels from the same endpoint features. A0 is consequently the target-generating rule, making the requested “improvement beyond baseline” test circular.
4. Missing aggregate minutes remain in the archive and must be handled explicitly by any future window/feature eligibility policy.
5. The historical adapter eligibility is `VERIFIED_RESEARCH_ARCHIVE`, not final acceptance; the manifest does not upgrade that status.

## 22. Acceptance classification

**C — INCONCLUSIVE.** The real archive volume and duration are substantial, but the requested scientific evaluation is blocked by receipt-clock/schema limitations, unimplemented exact-contract cross-market feature joining, and—most importantly—self-derived targets that make A0 an oracle. No result supports proceeding to Model B or changing the trading system.

Safest next prerequisite: architecture review must define an independently meaningful regime target/evaluation question (without tuning definitions to outcomes), and decide how historical receipt-time absence is represented. Separately, implement and test contract-aware paired-market feature joins while retaining exact listed contract/session IDs. Freeze a new manifest before any OOS result inspection only after those decisions are complete.

## 23. Files created/changed

- `config/bot2_phase5a_experiment_manifest_v1.json` — frozen protocol, committed before OOS inspection.
- `bot2/phase5a/gate.py`, `bot2/phase5a/__init__.py` — fail-closed blockers for missing receipt clocks, self-label imitation, and absent paired-market coverage.
- `bot2/phase5a/test_gate.py` — gate tests.
- `docs/BOT2_PHASE5A_REAL_ESNQ_VALIDATION.md` — this report.

Existing user changes elsewhere in the worktree were not staged or modified for Phase 5A.

## 24. Branch, commits, and tests

- Branch: `bot2-phase5a-real-esnq-validation`, created from Phase 5 branch `bot2-phase5-neural-model-a` at `a155a67`.
- Frozen manifest commit: `bd6312c`.
- Later Phase 5A gate/report commit: recorded in Git history after review.
- Automated tests: `\.venv\Scripts\python.exe -m pytest bot2 backtesting\test_core_v1_production_adapters.py -q` — **54 passed**.
- No full neural-model benchmark was run. Model B and Phase 6 were not started. Execution, paper order authority, deterministic risk, broker behavior, and live trading were not modified or enabled.
