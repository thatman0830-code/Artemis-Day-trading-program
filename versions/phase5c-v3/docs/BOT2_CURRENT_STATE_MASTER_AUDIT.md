# BOT 2.0 — Current-State Master Architecture & Capability Audit

**Audit date:** 2026-09-24 (America/Phoenix)  
**Scope:** Read-only current-tree inspection of `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`, on the existing branch only.  
**Purpose:** Baseline for future BOT 2.1 architecture assessment; this is not an implementation or trading authorization.

## Scope, method, and confidence

Inspected source, tests, configuration schemas/manifests, selected phase-status and provenance documents, Git metadata, and local interpreter/hardware metadata. No branch was switched. No source, model, configuration, dataset, manifest, result, or Git history was changed. Nothing under `outputs/` was enumerated, searched, opened, or hashed. No archive/data payload, checkpoint, protected result, prediction, probability, metric, P&L, or order was generated or inspected. No test, replay, training, inference, scheduler action, market-data request, or trading process was run.

The repository is **dirty**. Findings describe the checked-out working tree as well as identifying when the cited material is only a committed baseline or a historical report. `UNKNOWN` means the evidence was insufficient; it is not a positive or negative finding. Static source proves a code path exists, not that it currently runs or is operationally safe.

Parallel-review constraint: one dedicated read-only market-data/replay specialist completed a static review. New specialist allocation for further reviewers was rejected because the environment's agent-thread limit was reached. The coordinator performed the remaining reviews sequentially from source. No specialist opened protected outputs. The S4/provenance conclusions below are grounded in the current untracked provenance-boundary documents and are not independently re-proven by opening any protected artifact.

## SECTION 1 — EXECUTIVE SUMMARY

BOT 2.0 is a research/data foundation and a collection of paper-trading, risk, operations, and legacy exchange components in a repository originally named for a Hyperliquid bot. It is not one integrated ES/NQ model-to-order service. The ES/NQ lane has versioned raw/feature/target contracts, Databento-derived one-minute historical-bar metadata, deterministic causal feature/label logic, baseline and regime research, a NumPy A1 MLP candidate, and a Phase 5C NumPy causal-TCN A2 candidate. Those research outputs declare no trading authority.

The most important current-state facts are:

- **Phase 5C is paused and protected OOS remains closed.** The v3 manifest sets evaluation/scoring/trading flags false; the checked-in execution-harness document calls the real-data path preflight-only. The newer V5 contamination-boundary/reconciliation documents say no clean scientific-source boundary can be established and no scientific source is approved. Do not resume or score it based on this audit.
- **The repository is dirty at `fe9a9aa`** with 46 status entries and no staged files. Do not treat that tree as a clean reviewed candidate. The source includes uncommitted Phase 5C controls and tests.
- **Model evidence is not predictive evidence.** Phase 3/4 reports describe synthetic-fixture demonstrations, not market performance. No model is shown here to be profitable or to have a validated live edge.
- **There is no verified active ES/NQ paper session.** Config permits a supervised ES/NQ paper scope, and offline paper gateways exist, but this audit did not observe a running feed, current bars, a connected Rithmic adapter, or a running simulator. Runtime readiness is UNKNOWN.
- **No BOT 2.1 integration should touch the Phase 5C protocol, manifests, data adapters, risk, or execution.** A later isolated shadow-only package is plausible, but requires a fresh source/provenance gate and review first.

**Bottom line:** preserve BOT 2.0; do not start BOT 2.1 implementation or Phase 5C scoring from this audit. The next action is architecture assessment only after the owner resolves the source-boundary/provenance blocker and establishes a clean, reviewable baseline.

## SECTION 2 — MACHINE / ENVIRONMENT

| Item | Observed | Evidence / limitation |
|---|---|---|
| OS | Windows 10 Pro; `WindowsVersion` 2009 | `Get-ComputerInfo`; build number fields unavailable in this sandbox. |
| CPU | 32 logical processors visible to this process | `[Environment]::ProcessorCount`; model and physical-core count UNKNOWN because CIM access was denied. |
| RAM | UNKNOWN | CIM access denied; no reliable total-memory reading obtained. |
| GPU | NVIDIA GeForce RTX 5060 Ti; 16,311 MiB reported; WDDM | Read-only `nvidia-smi`. |
| Driver / CUDA | Driver 610.88 reported by GPU query. CUDA toolkit/runtime availability UNKNOWN; `nvcc` was not found. | `nvidia-smi`; no CUDA Python framework installed in the active interpreter. |
| Python | 3.11.9 at `C:\Users\fjone\AppData\Local\Programs\Python\Python311\python.exe` | `python --version`, `Get-Command python`. |
| Virtual environment | No repository `.venv`/`venv` was visible in the inspected root inventory; active interpreter is global user Python. | No environment activation or package installation performed. |
| pip | 24.0 | `python -m pip --version`. |
| Installed packages | `pip` and `setuptools` only appeared in `pip list`; NumPy, pandas, scikit-learn, PyTorch, TensorFlow, JAX, Databento, IBKR clients, XGBoost, LightGBM, and psutil were not present in that interpreter. | Read-only package inventory; the command emitted an index TLS warning. No package was installed. |
| Declared dependencies | `requirements.txt` pins NumPy 2.4.6, pandas 3.0.5, Hyperliquid SDK, pytest, and supporting packages. | Declaration is not proof of installation. |
| Git / PowerShell | Git 2.55.0.windows.3; PowerShell 7.6.5 | Read-only commands. Git warned it could not access the user-level ignore file; repository status still returned. |
| Disk | C: free space reported about 1,643.6 GB | `Get-PSDrive`; available space at other mounted/archive locations UNKNOWN. |
| Network / broker connectivity | Not tested | No connection, handshake, or data request attempted. |

The current interpreter cannot run BOT 2.0's NumPy-dependent test/model paths as-is. Tests were not run and dependencies were not installed.

## SECTION 3 — REPOSITORY STATE

- **Repository root:** `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`
- **Current branch:** `bot2-phase5c-z-review-remediation`
- **HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb` (`fe9a9aa`), commit subject `Complete BOT2 Phase 5C-Y runner blocker closure`.
- **Worktree:** dirty, 46 status entries: 8 modified tracked files, 38 untracked files, 0 staged files. Changes include `bot2/neural/model.py`; Phase 5C `calibration.py`, `data_integrity.py`, `experiment_matrix.py`, `experiment_runner.py`, `model.py`; Phase 5C tests; and untracked authorization/preflight modules and multiple Z/V4/V5 review documents. Full status was intentionally not copied here because it is extensive; the Git status is the source of truth.
- **Audit-artifact delta:** the 46-entry count is the pre-report baseline. This new master audit is one additional untracked file; final status after report creation is 47 entries (8 modified tracked, 39 untracked, 0 staged).
- **Remote configuration:** no remotes were listed. **Tags:** 0.
- **Recent relevant commits:** `fe9a9aa` (Y runner closure), `f867bf4` (synthetic Phase 5C safeguards), `b0a889b` (fixed-dimension ablations), `bc2af76` (V executable controls), `4f1d706` (v3 independent-review findings), `66caddf` (S remediation), `9a1ecfa` (v3 protocol/A2 preflight), `ff81aa3` (v2 protocol).
- **Branches:** `main` is at `19dd9d5` (`add shareable project overview`); milestone branches exist for Phases 1–5B and several 5C iterations. `bot2-phase5c-v3-protocol` is at `9a1ecfa`; `bot2-phase5c-y-protected-experiment-runner`, `bot2-phase5c-clean-slate-protocol`, `p5-adversarial-leakage`, and the current Z branch point at `fe9a9aa`. Other Hermes/audit worktrees also exist. No branch was checked out or inspected by changing worktree state.
- **Baseline classification:** `main` is the oldest visible general baseline, not established as a current stable ES/NQ production baseline. Phase 5B is a historical data-validation milestone; v3 is the frozen 5C protocol anchor; current Z is the latest named 5C review/remediation branch but is dirty. A “latest stable engineering baseline” and “paper-trading-capable branch” are **UNKNOWN**—there are no release tags, remote tracking state, or owner-approved promotion record establishing them.
- **Current candidate:** current Z branch/HEAD only as a repository identity, **not a clean or approved candidate**.

## SECTION 4 — REPOSITORY ARCHITECTURE

Major directories include `bot2/` (versioned BOT 2 data, features/labels, modeling, regimes, neural and Phase 5C research); `futures_data/` (Databento/other source probes, archives, roll/session and forward collection); `backtesting/` (canonical and provider-neutral adapters/replay/accounting); `strategy/` (structural strategy modules); `risk/`; `execution/`; `exchange/`; `database/`; `monitoring/`; `scripts/`; `config/`; `docs/`; `integrations/`; `research/`; `hermes_audit/`; and `outputs/`.

`outputs/`, market-data archives, SQLite databases, checkpoints, and protected results were deliberately not inspected. Root `README.md` and `main.py` are both zero bytes in this checkout. That, plus the large script inventory and separate BTC/ES-NQ modules, means there is no documented single root application entry point that wires the whole BOT 2 system.

The repository contains both a read-only Hyperliquid market-data client and paper-only trading components, plus separate ES/NQ research and provider-neutral paper infrastructure. These are adjacent subsystems, not evidence that the BOT 2 A2 model is connected to the existing strategy or order path.

## SECTION 5 — SYSTEM DATA FLOW

**ES/NQ research path (static implementation):**

```text
Databento-derived Pass B archive (historical 1-minute OHLCV)
        |
        v
PassBV3ArchiveAdapter validation (archive/plan/hash/row lineage)
        |
        v
close-time MarketEvent / exact contract + session identity
        |
        +--> exact ES/NQ time/session synchronization; no synthetic fill
        |
        v
24 causal features --> future-only 5/15/30-minute target rows
        |
        v
manifest-bound split + train-only preprocessing + purge/embargo
        |
        +--> A0 baseline / A1 MLP / A2 causal TCN research candidates
        |
        v
calibration / abstention / hashed experiment artifacts
        [Phase 5C real-data CLI currently documents preflight only;
         no approved protected scoring path]
```

**Legacy/operational paper path (separate):** read-only exchange/feed clients and strategy proposals → pre-trade/risk/portfolio guards → offline paper engine/gateway → SQLite ledger and monitoring. BOT 2 model output is not shown connected into this chain. No actual live or paper process state was observed.

## SECTION 6 — MARKET DATA

- **Provider / instruments:** Phase 5C manifest names Databento and ES/NQ listed futures. A source-level `PassBV3ArchiveAdapter` validates raw/normalized archives, request/contract identity, active windows, OHLCV geometry, and row lineage (`backtesting/core_v1/production_adapters.py`, `PassBV3ArchiveAdapter.validate`). Manifest coverage is 2025-06-02 through 2026-08-26 and lists ESM5/ESU5/ESZ5/ESH6/ESM6/ESU6 and corresponding NQ contracts.
- **Frequency / types:** frozen real-data protocol is normalized one-minute OHLCV. BOT 2 raw `MarketEvent` is a scalar price/volume event, with exchange and optional local-receipt timestamp, event type, sequence, session, and contract fields. Tick/depth/order-book integration into this BOT 2 experiment is not demonstrated. No exchange receipt timestamp is available for the historical set.
- **Contract / roll / sessions:** exact listed contract identity retained; continuous stitching and price adjustment are prohibited by manifest; archived session IDs are explicit. Session calendar correctness is not independently validated in this audit. `generate_features` and the preflight adapter derive `session_open` from the first observed row, not a separately verified official calendar open. Missing early bars can therefore distort “since session open” and session-phase features.
- **Validation:** `bot2/data_foundation/validation.py::validate_events` checks schema, duplicates, positive price, nonnegative volume, future/stale timestamps, regressions, expected intervals, and optional sequence continuity, with machine-readable `QualityReason` codes and fail-closed `DataQualityError`. `sync.py::synchronize_contract_roots` pairs exact timestamp/session events without forward-fill. A second helper, `synchronize_es_nq`, uses nearest timestamp within max skew and is weaker: it does not itself enforce exact timestamp/session/contract identity. Prefer the strict contract-root path for any future research.
- **Dataset quality:** the frozen manifest and historical preflight document report missing-minute and cadence-quality counts; gaps are not filled. Source-gap reason is explicitly ambiguous between no eligible trade and source omission. The stated counts/hash were not independently rechecked because archives and outputs were intentionally not opened.
- **Operational freshness:** no active Databento/Rithmic connection or feed freshness was tested. `databento` is not installed in the active Python interpreter. `futures_data/` contains probes, recovery and recorder modules; this is not proof of an active subscription or working current feed. No Rithmic Python adapter was found in the inspected integration inventory; `backtesting/test_rithmic_provider_contract_v1.py` is a test, not an adapter.

## SECTION 7 — DATASETS

Metadata only; data payloads and `outputs/` were not inspected.

| Dataset metadata | Manifest/document declaration |
|---|---|
| Source | Databento; “Promoted Pass B v3 normalized ES/NQ OHLCV one-minute bars” |
| Inclusive range | 2025-06-02 to 2026-08-26 |
| Contracts | Six listed ES and six listed NQ quarters, exact IDs retained |
| Rows | Historical audit document declares 877,679 normalized rows (438,873 ES + 438,806 NQ) |
| Schema | `bot2-feature-row-v3`, target `bot2-future-market-state-v3`; Phase 1 raw schema v1/v2 and dataset manifest v1/v2 |
| Identity | Phase 5C source manifest SHA-256 `e03e02906c8033d825d39844aaf4cf9aa3184b613e5c10974c23722531e92b67`; manifest pins an archive-tree hash and data eligibility report hash |
| Split declaration | TRAIN 2025-06-02–2025-12-31; VALIDATION_AND_CALIBRATION 2026-01-01–2026-02-27; OOS_TEST 2026-03-01–2026-08-26 |
| Storage size / actual present bytes / current hash verification | UNKNOWN in this audit; payload was not opened |
| Protected designation | OOS_TEST is the declared holdout; protected outputs remain unopened and evaluation is false in the manifest |

The declared OOS window ends 2026-08-26. No protected result content was accessed to characterize it. A future BOT 2.1 dataset can be logically separated by a new dataset/manifest identity, but physical isolation and access controls are not verified.

## SECTION 8 — REPLAY

`bot2/data_foundation/replay.py::deterministic_replay` filters events to `exchange_time <= cutoff`, preserves source order, invokes an optional callback, and hashes canonical serialized outputs. It excludes future events rather than filling them. `bot2/data_foundation/sync.py` has exact-pair and max-skew synchronization helpers.

Limits: replay does not sort/canonicalize input order itself; reproducibility therefore assumes the same already ordered source stream. It is a simple callback/event replay, not a fully wired exchange clock, order-book, network-latency, or fill simulator. The Phase 5C real-data preflight builds from archive rows; no Phase 5C event-by-event replay clock is wired into its documented preflight path. Historical receipt-time is unavailable, so replay cannot reconstruct actual live arrival availability. No replay was run in this audit.

## SECTION 9 — FEATURES

`bot2/features_labels/features.py::FEATURE_NAMES_V3` defines 24 fields: price; 1/3/5-minute log returns; 3/5-minute range and realized volatility; session open/high/low distances; cumulative and relative volume; volume acceleration; session VWAP and price-to-VWAP; seconds since session open; session phase; time sine/cosine; and four ES/NQ cross-market fields (1-minute return, relative return, 5-minute correlation, divergence).

Exact cadence windows are used; gaps result in unavailable/invalid reasons rather than imputation. Session statistics accumulate through the current row. Cross-market fields require same-session exact-time current/prior observations. **Causal in the intended contract**; session-open feature semantics remain fragile because open is first observed row. Feature order is frozen in registry/manifest. No feature drift monitor or production feature store was demonstrated. Raw price and cumulative volume are scale-sensitive and depend on the train-only scaler downstream.

## SECTION 10 — LABELS / TARGETS

`bot2/features_labels/targets_v3.py::generate_future_targets` creates separate, explicitly future-only targets at 5, 15, and 30 minutes: direction (UP/DOWN/FLAT by instrument tick); future realized-volatility state (LOW/NORMAL/HIGH relative to prior 30 returns); and future structure (TREND/RANGE/TRANSITION from path efficiency/displacement). Targets require exactly spaced future closes, same session and exact contract, with no fill; immature/boundary rows carry reason codes. Schema is `bot2-future-target-row-v3`.

These are research labels, not live-time inputs. Target information intervals are explicitly recorded. No separate MFE/MAE/barrier target is part of the frozen v3 target spec, although other legacy strategy/backtesting components contain related constructs. No target values were generated in this audit.

## SECTION 11 — REGIMES

`bot2/regimes/assign.py::assign_regime` implements deterministic threshold regimes on current causal features. The representation has direction, volatility, structure, and primary state; missing/weak inputs can become `UNCERTAIN`. `analytics.py` provides durations, transitions, conditional outcomes, and cross-market comparisons. It is rule-based, not a trained transition model; no model-driven strategy effect or trading authority is established. Phase 4 report describes the synthetic-fixture validation only and explicitly reports no real-data regime report.

## SECTION 12 — STRATEGIES

`strategy/trading_brain/` contains many structural setup components and tests (liquidity, FVG/iFVG, OTE, displacement, conflict resolution, setup qualification, position lifecycle/accounting). `strategy/` also contains setup/market-structure modules. Their presence does not prove a currently selected ES/NQ strategy or end-to-end connection to BOT 2 models. The Phase 5C research candidates are A0/A1/A2 model comparisons, not execution-authorized trading strategies. `config/es_nq_research_quarantine.json` explicitly keeps opening-range continuation/failure, trend-pullback resumption, and regime classification `research_only`, comparison-only, and unauthorized for signal/execution. Simultaneous strategy behavior and production selection are UNKNOWN for the BOT 2.1 lane.

## SECTION 13 — A0

Phase 5C matrix code names A0 candidates `A0_PREVIOUS_LABEL_PERSISTENCE`, `A0_TRAIN_MAJORITY`, and `A0_TRAIN_TRANSITION_MATRIX`. These are deterministic reference baselines. V5 source-boundary failure means there is no presently approved scientific protocol authority to select/tune/score an A0 comparison; old A0 tie-break discussions are untracked review material. **A0 implementation exists; valid comparative market-performance status is UNKNOWN/not established.**

## SECTION 14 — A1

`bot2/neural/model.py::MultiHeadMLP` is a small NumPy shared-encoder MLP with direction/volatility/structure 3-class heads and a simple gradient-descent `fit`; the Phase 5C matrix labels the candidate `A1_NUMPY_MULTIHEAD_MLP`. It is experimental research code, not a promoted baseline. The current checked-out file is modified and imports the untracked no-score guard. Training status, calibrated performance, and live integration are not established.

## SECTION 15 — A2 / NEURAL NETWORK

The Phase 5C A2 implementation is `bot2/phase5c_v3/model.py::CausalTemporalConv`, a NumPy causal TCN; it is distinct from the basic MLP in `bot2/neural/model.py`. The v3 manifest and current model code agree on:

- Input contract: `[batch, 8 timesteps, 24 features]` (`[8,24]` per sample), cadence 60 seconds.
- Three causal Conv1D blocks: `24→32`, `32→32`, `32→16`; kernel width 3; dilations 1, 2, 4; left-only zero padding; ReLU.
- Final valid timestep readout, shared dense `16→16`, ReLU, then direction/volatility/structure heads `16→3` each; no dropout or batch normalization.
- `expected_parameter_count(24)` / `parameter_count`: 7,417. The arithmetic matches the architecture: convolution weights+biases, shared layer, and three heads.
- Declared theoretical receptive field: 15 timesteps, greater than the 8-timestep sample. Inputs are left-padded; effective available context is still bounded by the 8 input rows. This mismatch deserves architecture review, not an audit-time change.
- Training settings are manifest-gated: Adam, learning rate 0.001, batch 256, max 50 epochs, patience 5 on validation/calibration partition, equal summed categorical cross-entropies, global gradient clipping at 1.0, seeds 1/2/3, deterministic chronological batches without shuffle. No real A2 training was run in this audit.

The A2 code is research-only, provenance-bound, and its score path is guarded. No A2 checkpoint, calibration artifact, inference-latency evidence, or model-to-order adapter was verified. PyTorch is neither installed nor required by the implemented NumPy architecture.

## SECTION 16 — OTHER ML EXPERIMENTS

Confirmed in BOT 2 code: deterministic majority/prior/persistence/transition baselines; small logistic and ridge-style baselines in `bot2/modeling/baselines.py`; A1 NumPy MLP; A2 NumPy causal TCN. No current BOT 2 implementation was found for Transformers, TFT, PatchTST, iTransformer, TimesNet, state-space models, mixture-of-experts, reinforcement learning, XGBoost, LightGBM, random forests, or SVMs. Those remain future ideas or absent; this audit did not execute experiments.

## SECTION 17 — TRAINING

Phase 3 generic modeling provides `TrainOnlyStandardizer`, chronological splits, baseline runner, and append-only experiment registry. Phase 5C `TrainingOnlyStandardizer.fit_observations` binds unique training rows to the verified external manifest, data/feature hashes, listed contracts, TRAIN dates, canonical order, exact feature schema, and commit; validation/OOS are transformed using that fit. `CausalTemporalConv.fit` consumes authorized partitions and manifest-gated training settings.

Implementation exists, but current execution status is **not trained/unknown** for real data. No fit, checkpoint, or metric was produced in this audit. Model selection/early stopping and calibration sharing the `VALIDATION_AND_CALIBRATION` partition is declared by the frozen manifest; later protocol governance must explicitly assess selection multiplicity and contamination before any evaluation.

## SECTION 18 — WALK-FORWARD

Phase 3 `bot2/modeling/splits.py` has chronological split and walk-forward helper code; Phase 5C `experiment_matrix.py::derive_walk_forward_windows` derives windows from a verified manifest and `validate_walk_forward_rows` enforces window identity and boundaries. V3 dates are fixed in the manifest. The actual real-data runner is documented as preflight-only, and no windows were executed or scored here. Window definitions/selection must not be inferred from a synthetic coverage check.

## SECTION 19 — LEAKAGE DEFENSES

Implemented controls include causal exact-window features; future-only, same-session/same-contract target construction; cutoff guards (`bot2/modeling/guards.py`); train-only scaling; exact sequence identity/cadence checks; cross-partition disjointness; purge/embargo and label-end validation; manifest-bound dataset/schema/commit fingerprints; causal TCN left padding; post-standardization fixed-width ablations; no-score guards; and no-forward-fill alignment.

Tests exist for future mutation, gaps, duplicates, order/cadence regression, session/contract boundaries, label maturity, purge/embargo, and data lineage. **Tests were not executed now.** Remaining weaknesses: historical receipt-time is unavailable; `deterministic_replay` preserves rather than canonicalizes input order; first-observed-row session-open issue; no independent source-boundary certainty for 5C; full selection/leakage proof cannot be certified from source alone.

## SECTION 20 — CALIBRATION / UNCERTAINTY

Phase 5C `calibration.py` implements validation-partition temperature calibration and threshold/abstention artifacts bound to manifest/model/split identity. The MLP inference path computes entropy and can abstain on high entropy/low maximum class probability; prediction contracts expose raw/calibrated distributions, uncertainty, reasons, and `trading_authority: false`. A2 Phase5C scoring/inference is guarded in current code and no real calibrator or threshold artifact was verified. Implemented capability is not evidence of calibrated confidence.

## SECTION 21 — ABLATIONS

Frozen v3 manifest lists `ALL`, `MINUS_CROSS_MARKET`, `MINUS_VWAP`, `MINUS_VOLUME`, `MINUS_VOLATILITY`, and `MINUS_SESSION_TIME`. `experiment_controls.py::apply_ablation_mask` standardizes using TRAIN-only preprocessing, applies a zero mask after standardization, and preserves canonical feature order and channel width. This is fixed-dimension channel ablation, not deleting input channels. The contract is versioned and hashed. Current worktree has uncommitted changes; no ablation was executed here. V4 proposal is explicitly quarantined and not adopted.

## SECTION 22 — MODEL REGISTRY

`bot2/modeling/registry.py::ExperimentRegistry` is an append-only experiment-result registry that rejects duplicate IDs. Phase 5C artifacts carry manifest, dataset, feature/target spec, preprocessing, model weights, code commit, calibration/result hashes and authority flags; artifact save uses content hashes and immutable-create semantics. `config/es_nq_research_artifact_registry.json` references trader-research package files. No central BOT 2 model-promotion registry, signed approval chain, production rollout, or tested model rollback was verified. No output registry contents were inspected.

## SECTION 23 — SIGNAL PIPELINE

The research pipeline ends at feature/target rows and model/regime prediction contracts. The existing separate `strategy/` code generates setup-level decisions, while the risk/execution subsystem accepts typed proposals/authorizations. No concrete caller was found that routes A1/A2 output through regime→strategy→pretrade→paper execution. Therefore model-based signal generation and conflict resolution are **not integrated/UNKNOWN**, and model outputs must not be used to trade.

## SECTION 24 — RISK MANAGEMENT

Safety components include `risk/risk_engine.py::RiskEngine` (proposal validation/position size), `risk/pretrade.py::PreTradeAuthorization`, `risk/portfolio_guard.py::PortfolioRiskGuard`, provider-neutral hard-control configuration, paper-gateway stale/future data checks, kill switch, exposure/open-order limits, duplicate idempotency, reconciliation, and paper-session supervisors. `provider-neutral_hard_risk_controls.json` declares 0.5% max risk/trade, 1.5% daily loss, 2% portfolio exposure, one position, max data age/latency 5s, 3% drawdown, and fail-closed unknown-state halt. These are static declarations, not runtime checks.

Separate legacy risk classes have different defaults (e.g. 0.25% per trade, 1% daily loss, max 3 consecutive losses, 100% notional/position defaults). This is scope fragmentation and a high blast-radius issue: BOT 2.1 must not bypass, reconfigure, or assume a single effective policy without tracing the specific production path. No risk values were changed. No live-order path or automatic flatten behavior was verified as an active ES/NQ capability.

## SECTION 25 — EXECUTION

`execution/paper_gateway_v2.py` describes a fail-closed offline paper gateway; `paper_exchange_adapter_v1.py` adds immutable snapshots/idempotent receipts; `paper_engine.py` simulates fills, fees and slippage after pretrade authorization. There are Rithmic-related contract tests, IBKR read-only collectors/preflight, a read-only `exchange/hyperliquid_client.py`, and many integration/launch scripts. In the inspected code, no connected Rithmic order adapter or BOT 2.1 execution adapter is established. IBKR's inspected native transport is explicitly read-only. Hyperliquid client is Info-only; `PaperExecutionEngine` explicitly says it does not submit Hyperliquid orders.

No live execution route was established for ES/NQ. Settings expose `TRADING_ENABLED` and `LIVE_TRADING_ENABLED` environment switches defaulting false, but runtime environment values/process state were not sampled. Therefore global runtime trading authority is UNKNOWN; this report grants none.

## SECTION 26 — PAPER TRADING

Paper-only primitives exist: `PaperExecutionEngine`, `PaperGatewayV2`, `PaperExchangeAdapterV1`, bounded/supervised workflows, ES/NQ provider-neutral authority configuration with three profiles and `$50,000` profile equity, and collection/health scripts. Config `provider_neutral_paper_authority.json` says paper execution permitted, live false, trading authority false, manual stop required, one concurrent position. Separate ES/NQ research quarantine says candidate research modules are not paper-authorized. Those have different scopes and are not evidence of an integrated launch.

No paper session was started or checked. No current feed freshness, connected paper account, fill simulation quality, ledger state, day reset, persistence recovery, or readiness decision was verified. **Not safe to claim “ready to run” from this static audit.**

## SECTION 27 — LIVE-TRADING STATUS

BOT 2 model contracts and paper gateway explicitly set trading authority false; ES/NQ configs set live trading false. Current settings default both global trading flags false. The inspected Hyperliquid client is read-only, and the paper engine is offline. This supports: **ES/NQ live trading is not an implemented/approved BOT 2 capability in the reviewed path.** Because no full runtime/environment or every legacy module was activated/validated, system-wide impossibility is **UNKNOWN**. No live mode was enabled.

## SECTION 28 — LEDGER

`database/trade_ledger.py::TradeLedger` uses SQLite at default relative path `database/trading_bot.db`, with entry/exit records, open/recent trades, and performance summary. Newer provider-neutral paper components have event/order snapshots and immutable receipts. The database file and ledger contents were not inspected. Cross-reconciliation of paper gateway events, broker state, positions, fees/slippage and this legacy SQLite ledger is not established as one unified ledger. No P&L is reported by this audit.

## SECTION 29 — MONITORING

Static monitoring modules include `monitoring/market_health.py::MarketDataHealthGate`, `operational_resilience.py::evaluate_operational_readiness`, paper dashboards/views, owner-context health/watchdog adapters, recorder/clock/data-quality collectors, alert-delivery verification, and PowerShell task audit/collection scripts. They cover feed age/latency, process/service state, data integrity, operational events, and delivery concepts. No scheduler/task query or live process inspection was performed; task state, last result, alert delivery, recorder freshness, disk thresholds, and actual dashboard health are **UNKNOWN** now.

## SECTION 30 — RECOVERY

Recovery code and scripts exist for Databento history/backfill, gap rechecks, archive integrity, feed/recorder supervision, Windows clock guards, paper session supervision, and restart/reconciliation drills. This proves designed recovery paths only. Automatic restart under the current user's Windows scheduler, recovery authority/bounds, persistent state correctness, and recovery after a machine restart were not verified. Unknown/unhealthy state should remain fail-closed per the relevant controls.

## SECTION 31 — LOGGING

The repository contains data-quality reports, hash-chained/manifest-style archives, paper order events/receipts, audit/experiment artifacts, recovery records, and monitoring snapshots. Exact production log destinations, retention/rotation, correlation IDs across the distinct BOT 2/legacy subsystems, and current write health are not known because runtime/output paths were not inspected. `outputs/` is intentionally excluded from this report's audit evidence.

## SECTION 32 — TESTING

- Static inventory found **346 `test_*.py` files** outside `outputs/`, `.git`, virtual environments, and `hermes_audit` reports. There are 15 test files under `bot2/` by the same inventory method. Test functions/cases were not counted across the entire suite.
- **Current pass/fail/skip counts:** UNKNOWN; no tests were run.
- Reason: the active interpreter only listed pip/setuptools; NumPy is absent, `main.py` is empty, the tree is dirty, and the suite includes paths capable of touching archives/results or external services. Phase 5C must not be evaluated or run; first inspect a narrow test's side effects and use the project's intended isolated environment only after allowed.
- Historical phase docs report focused test passes (e.g. Phase 3/4 synthetic and unit suites, and 14 Phase5C-V control tests). Those are dated reports on prior states and do not establish current test health at dirty HEAD. Do not quote them as a current green build.

## SECTION 33 — DETERMINISM

Determinism mechanisms include manifest and config SHA-256, canonical JSON, fixed NumPy RNG seeds, deterministic canonical sequence/row ordering checks, no-shuffle chronological batches, immutable artifacts, dataset/partition fingerprints, and hash-bound replay outputs. The TCN declares deterministic NumPy CPU operations. Thread/BLAS control, cross-version numeric reproducibility, GPU determinism, and environment lock attestation are not demonstrated. Replay preserves caller input order rather than sorting; this is deterministic only for identical ordered input.

## SECTION 34 — PROVENANCE

Phase 1 dataset manifests include source, instrument/date bounds, schema/validation state, source and normalized SHA-256, commit, config hash, count, quality report, timestamp provenance, and no-trading authority. Phase 5C manifest pins dataset, feature registry, target spec, architecture, split dates, training, calibration/abstention and ablation identities. A separate external anchor is required by `manifest.py`; it is unsigned and explicitly not cryptographically custody-proven in the reviewed code. Hashes establish byte integrity against declared digests, not independent origin/custody.

**Major provenance defect:** current V5 contamination-boundary documentation says an earlier S4 audit reportedly surfaced an unidentified serialized artifact under `outputs/`; exact artifact/time/task/transcript and downstream derivation chain are not established. It concludes clean source authority cannot be established, identifies V4 as quarantined/not adopted, and states zero scientific sources approved. Protected content was not opened to resolve this.

## SECTION 35 — PHASE 5C STATUS

- Intended scope: compare A0/A1/A2 with frozen real ES/NQ archive, causal features/targets, walk-forward, calibration/abstention, ablations, provenance, and protected holdout controls.
- Current committed v3 manifest says `protocol_status: FROZEN_NOT_APPROVED_PENDING_INDEPENDENT_REVIEW`, `evaluation_permitted: false`, `oos_model_scoring_performed: false`, `trading_authority: false`.
- `docs/BOT2_PHASE5C_V3_EXECUTION_HARNESS.md` says current real-data CLI is `scripts/run_phase5c_v3_preflight.py --dry-run`; no model-evaluation command; successful result means preflight-ready only.
- Current HEAD is a Phase 5C-Y runner-blocker closure commit. Current dirty/untracked tree includes Phase 5C Z remediation, no-score boundary, authorization and preflight work. Source edits do not supersede a frozen protocol by themselves.
- V4 proposal/JSON are untracked and the V5 coordinator document labels them `QUARANTINED_NOT_ADOPTED`; V5 source boundary says stop because no clean source authority set can be certified. Phase 5C remains paused.
- The historical preflight document states no protected scoring, but this audit did not open protected artifacts. Current code/protocol declares scoring false and preflight-only; a complete project-wide historical proof that no protected scoring ever occurred is **UNKNOWN**, especially given the unbounded S4 provenance incident.
- V1/V2/V3 anchors exist in Git history; the V3 source identity is committed. F3's prior lineage review notes a feature-registry raw-file hash differs from the manifest's pinned registry hash and the digest reconciliation procedure is undocumented; incident-relative pre-S4 status is unknown. Treat provenance discrepancies as blockers.

**Disposition:** paused; no resumption, model evaluation, protected OOS, or adoption of V4/V5 protocol. This audit did not change that state.

## SECTION 36 — PERFORMANCE EVIDENCE

**Known engineering evidence:** historical docs report archive audit of 877,679 normalized ES/NQ rows, hash/lineage validation, no duplicate/synthesized rows, and data eligibility counts. Those are document declarations, not freshly revalidated data. There are tests and code for validation, replay, risk, paper accounting, operational recovery, and provenance. No current suite was run. GPU is available as hardware but no ML framework is installed in the active interpreter.

**Known model evidence:** historical Phase 3 and Phase 4 docs report synthetic-fixture baselines/regimes and test results. They explicitly disclaim real ES/NQ predictive or profitability conclusions. No current real-data model score, calibration result, or strategy profitability evidence is authorized/verified here.

**Unproven:** any claim of positive predictive edge, profit, stable paper/live results, or superiority of A1/A2. No model should be described as profitable.

## SECTION 37 — KNOWN FAILURES

High-confidence current blockers/weaknesses:

1. Phase 5C cannot proceed because source contamination boundary is unbounded and V5 reconciliation approves no scientific authorities.
2. Worktree is dirty, including research code/tests and untracked control documents; current candidate does not satisfy clean baseline assumptions.
3. Current Python environment lacks NumPy and test/model suite is not runnable without changing environment.
4. No confirmed active ES/NQ data source/feed/session or live freshness.
5. Historical receipt timestamps unavailable; cannot prove point-in-time live availability.
6. Feature `session_open` is first observed row rather than verified calendar open.
7. Generic nearest-skew ES/NQ synchronizer is weaker than exact session/timestamp/contract join.
8. No integrated BOT 2 model→strategy→paper execution path is established.
9. No runtime status for Windows tasks, recorder, supervisor, paper session, or Obsidian backup was checked.
10. Stable/paper-capable promoted branch is not identified; repository has no remotes/tags.

The scoped source/docs search found no `TODO`, `FIXME`, `BUG`, or `HACK` markers in BOT 2, futures data, execution, risk, monitoring, and named BOT 2 docs. That narrow search is not a guarantee that no defects exist.

## SECTION 38 — TECHNICAL DEBT

Main debt: mixed project identity (Hyperliquid-era root and ES/NQ BOT2 research/operations); empty root `README.md`/`main.py`; no single startup/health entrypoint; legacy and provider-neutral risk classes with different defaults; multiple data/recording/replay lanes; source and runtime responsibilities spread across many scripts; a generic nearest-skew synchronizer alongside stricter exact join; runtime `MarketObservation` lacks a standalone persisted schema; session open inferred from first observed event; uncommitted control evolution; unbounded Phase 5C review provenance; no release tags/remotes; and no verified dependency lock/environment reproducibility. No cleanup was performed.

## SECTION 39 — SECURITY

`config/settings.py` loads `.env` and reads `HL_ACCOUNT_ADDRESS`, `HL_API_WALLET_PRIVATE_KEY`, `TRADING_ENABLED`, and `LIVE_TRADING_ENABLED`; code defaults network to testnet and trading flags false. `.env` was not present at repository root when checked. No secret values or process environment values were read or emitted. Credentials are intended to be environment-supplied; static source contains credential-boundary tests for Databento. Secret-store/ACL posture, other environment files, terminal history, installed app credentials, and scheduled task principals were not audited. Do not paste API keys into the report or repository.

## SECTION 40 — HARDWARE LIMITATIONS

GPU: RTX 5060 Ti, 16 GB class device. No PyTorch/TensorFlow/JAX/NumPy in the active Python environment and no `nvcc`; actual CUDA development/runtime suitability is UNKNOWN. 32 logical processors visible. RAM/physical core count and archive I/O throughput UNKNOWN. There is no basis for a purchase recommendation. The current NumPy research model is small; software environment/reproducibility and data governance, not raw GPU capacity, are the immediate constraints.

## SECTION 41 — CAPABILITY MATRIX

Ratings describe code evidence in this tree, not runtime readiness. Each BOT2 research output has no trading authority.

| Capability | Rating | Evidence / caveat |
|---|---|---|
| Data ingestion | FUNCTIONAL (historical contract) | Databento archive adapter and Phase1/Phase5 schemas; actual source availability not checked. |
| Recording | PARTIAL | Recorder/forward-capture code and scripts exist; current process/task/feed state UNKNOWN. |
| Replay | FUNCTIONAL (basic deterministic utility) | `deterministic_replay`; input order assumed, not wired to Phase5C preflight. |
| Feature engine | FUNCTIONAL (research) | Versioned 24-feature causal engine; session-open semantic weakness. |
| Label engine | FUNCTIONAL (offline research) | Versioned future-only targets, horizons 5/15/30. |
| Regime engine | FUNCTIONAL (rule-based) | Deterministic thresholds/analytics; no trained/live integration. |
| A0 | EXPERIMENTAL | Candidate baselines exist; current comparison authority/status blocked. |
| A1 | EXPERIMENTAL | NumPy MLP code; no validated real-data performance. |
| A2 | EXPERIMENTAL | Causal TCN code, shape/parameter identity; no approved evaluation. |
| Training | PARTIAL | train-only scaler and training code; dependency missing and execution unauthorized now. |
| Walk-forward | PARTIAL | split/window validation exists; real windows not evaluated. |
| Calibration | PARTIAL | validation temperature/abstention code; no live/real artifact verified. |
| Abstention | PARTIAL | contracts and thresholds exist; not production-integrated. |
| Risk | FUNCTIONAL (separate controls) | Distinct risk gates/configs exist; effective path/policy consistency not verified. |
| Paper trading | PARTIAL | Offline paper engine/gateway and permission config; no current ES/NQ feed/session evidence. |
| Execution | PARTIAL | Simulated gateway and read-only adapters; no connected Rithmic ES/NQ order adapter verified. |
| Live trading | NOT IMPLEMENTED for reviewed BOT2 ES/NQ path; system-wide runtime UNKNOWN | BOT2 flags false; no approved/live route established. |
| Monitoring | PARTIAL | Health/task/report code exists; current process/task state not queried. |
| Recovery | PARTIAL | recovery scripts and controls exist; automatic current deployment not verified. |
| Testing | UNKNOWN current | 346 test files inventoried, none run; active interpreter lacks dependencies. |
| Provenance | PARTIAL / BLOCKED | Strong versioned hashes/manifest code, but unsigned custody and unbounded S4 lineage defect. |
| Protected evaluation | BLOCKED / NOT AUTHORIZED | Manifest evaluation false, harness preflight-only, V5 says no clean authority. |

## SECTION 42 — DEPENDENCY / BLAST-RADIUS MAP

```text
futures_data + PassBV3ArchiveAdapter
  -> bot2.data_foundation contracts/validation/sync
  -> bot2.features_labels + feature/target registries
  -> bot2.phase5c_v3 data_integrity + verified manifest + scaler
  -> A0/A1/A2 + calibration/ablation/result provenance

strategy proposals
  -> risk.pretrade / risk_engine / portfolio_guard
  -> offline paper gateway / adapter / engine
  -> ledger + monitoring + recovery
```

**DO_NOT_TOUCH WITHOUT INTEGRATION TEST + OWNER REVIEW:** raw/data schemas; archive adapters and pinned data identity; feature and target registries/specs; session/contract/cadence logic; Phase 5C manifest/anchor/split/no-score controls; risk defaults/authorization gates; paper gateway/order accounting; ledger schemas; scheduler/recovery authority; environment and provider credentials. The highest blast radius is any shared timestamp/session, contract identity, scaler, risk authorization, or paper-gateway change.

## SECTION 43 — BOT 2.0 PRESERVATION ZONE

Initially preserve/read-only: `bot2/data_foundation/` schemas and validators; `futures_data/` and `backtesting/core_v1/production_adapters.py` archive lineage; feature/target registries and causal functions; Phase 5C frozen V1/V2/V3 manifests, lock and protocol source (without treating them as approved after S4); risk/pretrade controls; `execution/paper_gateway_v2.py` and adapters; ledger and operational resilience/recovery. The repository's dirty copies must first be reconciled by the owner; do not overwrite them to match this report.

## SECTION 44 — BOT 2.1 SAFE REUSE ZONE

Potential **read-only** reuse after new independent review: versioned raw event and dataset-manifest contracts; exact-contract normalization; strict no-forward-fill synchronization; causal feature-row interface; sequence identity validation; cutoff/replay utility with explicit sorted-input precondition; source adapter output interface; structured reason codes; logging/metrics contracts; and paper-only prediction contract shapes. Do not reuse data/results as clean research authority until the provenance boundary is resolved. Do not use BOT2 predictions to drive existing strategies.

## SECTION 45 — BOT 2.1 ISOLATION OPTIONS

`research/bot21/` does not exist in the current tree. If later approved, a separate package/worktree and separate dataset/manifest namespace are safer than modifying `bot2/phase5c_v3/`. Keep no order/broker imports, no write access to `outputs/` or protected archives, independent dependencies/checkpoints, shadow-only typed input/output, immutable manifests, and owner-controlled read-only source adapters. This is an option, not an implementation decision; do not create it now.

## SECTION 46 — SHADOW-MODE READINESS

Contracts already carry prediction timestamps, instrument/model identity, uncertainty/abstain and `trading_authority: false`, so a conceptual shadow-output interface is plausible. But no verified stable live ES/NQ feed, runtime consumer, operational isolation, logging sink, or canary/health contract was demonstrated. **Readiness: partial concept only; not ready to run a BOT 2.1 shadow process.**

## SECTION 47 — ROLLBACK READINESS

Git history/worktrees provide local source rollback points, and hashed model artifacts/manifests are designed for identity checking. There are no tags/remotes and the current tree is dirty; no clean deployable stable baseline is established. Model/config registry promotion, feature-flagged dual-run, production routing rollback, and tested BOT 2.1 emergency disable are UNKNOWN/not established. Safest future rollback is separate process/package with no trading authority; do not retrofit into production now.

## SECTION 48 — SPECIALIST DISAGREEMENTS

- **Market-data specialist and coordinator: AGREED.** Historical data contracts/lineage are strong at source level, but receipt-time is unavailable, runtime feed freshness is unknown, Phase5C is preflight-only, and session-open uses first observed row.
- **Phase 5C status: AGREED.** Manifest/harness say no scoring permission; V5 coordinator says Phase 5C paused because the clean-source boundary cannot be established. No source read here supports resuming it.
- **Historical “no protected scoring ever”: UNRESOLVED.** Current manifest and harness declare no scoring; this audit intentionally did not inspect sealed results or historical task transcripts. The V5 provenance document itself says exposure/time/derivation cannot be bounded. Therefore project-wide historical non-exposure/non-scoring cannot be certified from this audit.
- **Stable/paper-ready branch: UNKNOWN.** Branch names and commit graph provide candidates, but no release/promotion or runtime evidence.
- **Machine RAM/CPU model: UNKNOWN.** Sandboxed CIM denied access; only logical processors visible and GPU details were available.

Only one new specialist could be allocated in this audit because the environment rejected further tasks at its thread limit. Other section conclusions are coordinator static inspection, not falsely attributed independent reviews.

## SECTION 49 — RED-TEAM FINDINGS

1. **Do not mistake manifests for active data.** We did not open archives or validate current hashes; all freshness/availability is unknown.
2. **Do not mistake historical test reports for current green status.** The checkout is dirty and the active interpreter is missing NumPy.
3. **Do not mistake the v3 manifest's `oos_model_scoring_performed: false` for a complete global history proof.** The S4 exposure chain and task transcripts are unbounded in V5 records.
4. **Do not treat the V3 hash anchor as custody proof.** It is unsigned and not cryptographically custody-proven; F3 review additionally reports an undocumented feature-registry digest discrepancy.
5. **Do not assume “session open” means exchange-calendar open.** It is first observed timestamp and can shift when bars are absent.
6. **Do not assume the two ES/NQ synchronizers are equivalent.** The nearest-skew helper is weaker than exact session/time matching.
7. **Do not connect research predictions to existing order authority.** No reviewed integration boundary enforces model-output isolation end to end.
8. **Do not assume configured paper permission means a running/safe session.** The three-profile config and research quarantine have distinct scopes; runtime feed, fills, accounts and supervised approvals were not verified.
9. **Do not call BOT 2 live-ready.** Read-only Hyperliquid and offline paper components do not constitute a real ES/NQ broker route.
10. **Do not change shared contracts or risk settings from a future research branch.** The mixed repository and multiple defaults create large regression/blast radius.

## SECTION 50 — COORDINATOR CONCLUSION

The project has a valuable data/research and paper-safety foundation, but current operational readiness and predictive quality are not established. The defensible current status is **research infrastructure present; real-data Phase 5C paused; no protected scoring authorization; no verified ES/NQ paper session; no BOT 2.1 implementation**. Preserve existing work and do not resume Phase 5C, inspect protected results, or connect model output to execution. First establish an auditable scientific source boundary and clean reviewed baseline, restore a reproducible Python environment without changing it during this audit, and obtain explicit architecture review. Those are review prerequisites, not actions authorized by this report.

# CHATGPT ARCHITECT HANDOFF

Copy/paste baseline. Fields marked UNKNOWN were not established; static declarations are not runtime attestations.

1. **Repository root:** `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`
2. **Current branch:** `bot2-phase5c-z-review-remediation`
3. **HEAD:** `fe9a9aa536ed36795d52cb90a5e9c2b85f564cdb`
4. **Dirty/clean:** DIRTY — 47 final status entries after creating this report (8 tracked modifications, 39 untracked, 0 staged); pre-report baseline was 46; no remote; 0 tags.
5. **OS:** Windows 10 Pro; OS build UNKNOWN.
6. **CPU:** 32 logical processors visible; CPU model/physical cores UNKNOWN.
7. **RAM:** UNKNOWN (sandbox denied CIM query).
8. **GPU:** NVIDIA GeForce RTX 5060 Ti; 16,311 MiB reported; driver 610.88; CUDA runtime/toolkit UNKNOWN; `nvcc` not found.
9. **Python:** 3.11.9 global user interpreter; pip 24.0; only pip/setuptools appeared installed; NumPy missing.
10. **Core data provider:** Databento in Phase5C manifest; historical archive is documented, actual current feed/data not checked.
11. **Execution provider:** ES/NQ connected provider UNKNOWN. Rithmic adapter not found in inspected code; IBKR path is read-only; legacy Hyperliquid client is Info/read-only.
12. **Instruments:** ES and NQ listed contracts (six quarters each in Phase5C manifest). Paper authority config names ES/NQ, three profiles.
13. **Data frequencies:** Phase5C normalized 1-minute OHLCV; generic BOT2 raw event schema price/volume; tick/depth not established for this lane.
14. **Historical-data coverage:** Manifest declares 2025-06-02–2026-08-26; 877,679 normalized rows in historical audit document. Payload/hash not rechecked.
15. **Current feature count:** 24 versioned causal features (`bot2-feature-row-v3`).
16. **Current target set:** Direction, volatility state, structure at horizons 5/15/30 minutes.
17. **Regime system:** deterministic threshold-based, multi-axis, can emit UNCERTAIN; no learned/live coupling.
18. **Active strategies:** No selected integrated ES/NQ BOT2 strategy established. Existing structural strategy modules exist; candidate OR/trend-pullback/regime ideas are research-only and execution unauthorized.
19. **A0 status:** baseline candidate code exists; no currently approved comparison/scoring authority; tie-break/protocol source gate unresolved.
20. **A1 status:** experimental NumPy multi-head MLP candidate; no validated market result or live integration.
21. **A2 status:** experimental NumPy causal TCN; Phase5C real-data evaluation blocked.
22. **A2 architecture:** three causal Conv1D blocks, channels 24→32→32→16, kernel 3, dilations 1/2/4, shared dense 16, three 3-class heads.
23. **A2 input shape:** `[batch, 8, 24]` / per-sample `[8,24]`.
24. **A2 parameter count:** 7,417, verified from code/manifest contract.
25. **Training status:** Implementation only; no training performed in this audit; current environment lacks NumPy.
26. **Walk-forward status:** code and frozen dates exist; no real-data walk-forward scores authorized/executed here.
27. **Calibration status:** validation-bound temperature/abstention code exists; real artifacts/results UNKNOWN.
28. **Abstention status:** thresholds/contracts exist in research inference; not production integrated.
29. **Paper-trading status:** offline engines/gateways and config exist; current ES/NQ supervised session/feed/runtime not verified; not safe to claim ready.
30. **Live-trading status:** no approved BOT2 ES/NQ live route established; global process authority UNKNOWN; no live trading enabled by this audit.
31. **Risk status:** multiple risk/pretrade/portfolio controls exist; defaults differ by subsystem; runtime effective policy UNKNOWN.
32. **Monitoring status:** feed, health, watchdog, dashboard and task-audit code exists; actual task/process states not checked.
33. **Recovery status:** recovery/restart/reconciliation code exists; deployment and current recovery readiness UNKNOWN.
34. **Test-suite status:** 346 `test_*.py` files inventoried outside outputs/virtual env/Hermes reports; current pass/fail/skip UNKNOWN; no tests run.
35. **Provenance status:** versioned hashes/manifests/lineage code; external anchor unsigned/no custody proof; S4 contamination boundary unbounded.
36. **Phase 5C status:** paused; v3 frozen but not approved; preflight only; V4 quarantined/not adopted; V5 source gate fails.
37. **Protected-OOS status:** closed/not authorized; current manifest says scoring false. Project-wide historical non-scoring cannot be certified from unopened outputs/task lineage.
38. **Known predictive evidence:** none established for real ES/NQ; old docs are synthetic fixture evidence only.
39. **Known engineering evidence:** historical archive/data-quality and focused test reports; not freshly revalidated at dirty HEAD.
40. **Top 10 technical risks:** (1) unbounded S4 provenance/source authority; (2) dirty branch; (3) no active feed verification; (4) missing receipt timestamps; (5) first-row session-open semantics; (6) nearest-skew synchronizer weaker than exact; (7) no model→signal→risk integration proof; (8) runtime/trading state unknown; (9) global interpreter lacks dependencies; (10) split legacy/provider-neutral policies and no promoted baseline branch.
41. **Top 10 strongest existing components:** (1) versioned data/feature/target schemas; (2) fail-closed validation reason codes; (3) exact contract/session identities; (4) no-fill synchronization; (5) causal window/target logic; (6) manifest/split/hash bindings; (7) train-only scaler; (8) fixed-dimension ablation contract; (9) offline paper gateway with idempotency/reconciliation; (10) risk/monitor/recovery design artifacts.
42. **Top 10 weakest components:** (1) Phase5C provenance/source gate; (2) unclean worktree; (3) no live data freshness proof; (4) no current automated suite result; (5) historical receipt-time absence; (6) session open derived from first row; (7) dual synchronization semantics; (8) no coherent startup/orchestrator; (9) fragmented effective risk/execution config; (10) no model promotion/rollback/shadow operator path.
43. **Initially untouched:** Phase5C manifests/protocol/anchor/splits/results, data archive/adapters, schemas/registries, session/contract mapping, risk/pretrade, paper gateway/ledger, credential config, monitor/recovery scheduler.
44. **Safe read-only reuse candidates:** data contracts, strict validation, exact synchronization, feature interface, target metadata, sequence identity and paper-only prediction schema—only after independent provenance review; do not reuse the current dataset as clean authority yet.
45. **Safest BOT 2.1 boundary:** separate process/package/worktree (candidate `research/bot21/`), new provenance/data namespace, read-only market-state input, prediction/uncertainty output with no broker/order imports or authority.
46. **Shadow-mode readiness:** conceptual interface only; not operationally ready.
47. **Rollback readiness:** local Git history and hashed artifacts exist, but dirty tree/no tags/no remote means a clean promoted rollback baseline is not established.
48. **Hardware constraints:** RTX 5060 Ti 16 GB and 32 logical CPUs visible; RAM/physical cores unknown; current interpreter lacks numerical/ML packages; data IO unknown.
49. **Biggest unanswered questions:** What exactly was exposed in S4 and when? Which sources/agents were affected? Can a clean source boundary be proven? Where are actual archive bytes and do hashes still match? What is current feed/paper-session state? Which branch is owner-approved stable? What is the effective risk policy? Can the suite run in intended env? Is session calendar open correct? Has any historical protected scoring occurred outside declared artifacts?
50. **Recommended NEXT ACTION — assessment only, NOT implementation:** obtain owner-approved, auditable provenance/incident boundary and independent source review; then nominate a clean BOT 2.0 baseline for a BOT 2.1 architecture assessment. Keep Phase 5C paused and protected OOS closed.

CURRENT STATE PARTIALLY MAPPED — IMPORTANT UNKNOWNS REMAIN
