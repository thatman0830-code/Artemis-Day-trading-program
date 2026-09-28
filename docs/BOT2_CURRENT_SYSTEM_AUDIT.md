# BOT 2.0 Phase 0 — Current System Audit

Audit date: 2026-09-21 (America/Phoenix)

This is an inventory of the existing repository against the supplied BOT 2.0 blueprint. It is an audit artifact only. No neural-network dependency, broker adapter, risk rule, execution path, or paper-trading behavior was changed for this Phase 0 audit.

## A. Current architecture

The repository is a Python 3.11.9 Windows project with these major layers:

| Layer | Current implementation | Evidence | Status |
|---|---|---|---|
| Application/runtime | `main.py` is empty; operation is script/module driven | root inventory | Existing project has no single production entry point |
| Market data | Databento historical/recovery tooling; live GLBX.MDP3 ES/NQ capture; Hyperliquid public BTC capture; archived NinjaTrader bridges | `futures_data/`, `scripts/capture_databento_live_es_nq.py`, `execution/*recorder*`, `backtesting/*market_feed*` | Strong data/replay foundation, multiple legacy lanes |
| Representation/strategy | Canonical market data, structure, liquidity, OTE/FVG, setup qualification, adaptive comparison lane | `strategy/`, `strategy/trading_brain/`, `backtesting/orchestrator.py` | Deterministic and research-oriented; no neural feature store |
| Simulation/paper | Provider-neutral three-profile ledger, paper engine/gateway/OCO/session components, supervised launch gates | `backtesting/provider_neutral_paper_trial_v1.py`, `execution/paper_*`, `config/provider_neutral_paper_authority.json` | Paper-only and fail-closed; current provider-neutral trial accounting is explicitly non-executable |
| Risk | Hard limits, portfolio guard, pretrade checks, risk engine, hard-control validator | `risk/`, `config/provider_neutral_hard_risk_controls.json`, `scripts/validate_provider_neutral_hard_controls.py` | Deterministic authority layer; preserve as-is during ML work |
| Execution/broker | Hyperliquid client/exchange code; Rithmic contract boundary; archived NinjaTrader evidence; paper adapters | `exchange/`, `backtesting/rithmic_provider_contract_v1.py`, `execution/paper_*` | Vendor-specific code exists but provider-neutral boundary is incomplete |
| Recording/ledger | JSON/JSONL outputs, paper ledgers, BTC recorder archives, decision ledger, Obsidian continuity backup | `outputs/`, `database/`, `execution/*ledger*`, `scripts/create_obsidian_continuity_backup.ps1` | Extensive evidence, but output volume is very large and schemas are distributed |
| Monitoring/recovery | Health reports, supervisor, watchdogs, Task Scheduler installers, recorder recovery drills | `monitoring/`, `scripts/run_provider_neutral_pipeline_supervisor.ps1`, `scripts/guard_provider_neutral_supervisor.ps1` | Good controls; scheduled-task permissions and persistence need verification |
| Research/validation | Replay, walk-forward/OOS artifacts, Monte Carlo/scientific validation, research package registry, comparison gates | `backtesting/`, `research/`, `config/es_nq_research_*` | Broad foundation; model registry/training pipeline absent |

## B. Reusable components (KEEP)

- Databento raw/current capture, canonicalization, latency and symbol-mapping checks.
- Historical replay, dataset fingerprints, source hashes, rollover/session handling, and recovery staging.
- Deterministic structure/liquidity/setup pipeline and no-signal behavior.
- Three-profile accounting boundary and $50,000 starting-equity invariant.
- Hard risk controls, authority configuration, fail-closed supervisor, duplicate/order safeguards, and safe-halt semantics.
- Paper adapters, OCO/session accounting, decision ledger, black-box evidence patterns, and Obsidian continuity backups.
- Existing unit, integration, replay, adversarial, recorder, and risk tests (331 `test_*.py` files outside the virtual environment/output tree).
- Research artifact hashes, trader-research quarantine, comparison-only adaptive lane, and non-authoritative scorecards.

## C. Reliability risks / technical debt

1. The repository is on `main`; no isolated BOT 2.0 development branch exists yet.
2. There is no single application entry point or service contract for data → features → models → decision → risk → execution.
3. Runtime output is distributed across approximately 196k generated files; retention and schema discovery need a formal policy.
4. Windows Task Scheduler visibility/permissions have failed in prior diagnostics; continuous supervisor and recorder health need an independently verifiable deployment check.
5. Existing JSON artifacts can be written by Windows PowerShell with a UTF-8 BOM; readers must be BOM-tolerant.
6. Credentials are correctly excluded from Git by `.gitignore`, but `.env`, `.env.txt`, and `.envt` exist locally and require ongoing secret hygiene. Values were not printed or copied.
7. Existing Hyperliquid exchange code and legacy broker artifacts coexist with the ES/NQ provider-neutral lane; ownership and deprecation boundaries must remain explicit.
8. Current provider-neutral live-cycle output is a heartbeat/read-only consumer; it does not by itself provide a complete simulated-fill lifecycle.
9. No model registry, feature/label registry, calibration store, drift monitor, or champion/challenger promotion workflow exists.

## D. Data pipeline status

- Historical ES/NQ Databento recovery and replay artifacts exist with hashes, fingerprints, session calendars, and rollover handling.
- Current Databento capture requests `GLBX.MDP3` and records exchange/event and local receipt timestamps. The last verified live capture mapped `ES.c.0 → ESZ6` and `NQ.c.0 → NQZ6`, passed freshness/latency checks, and kept trading authority false.
- BTC public recorder and Forex Factory shadow-trial evidence are separate operational lanes; they must not be used as ES/NQ directional authority.
- Data-quality checks cover stale data, gaps, duplicates, impossible values, ordering, latency, clock/recorder health, and provider disconnect conditions, but coverage is not yet unified behind one versioned data-quality contract.

## E. ML readiness

Current readiness: **research architecture not yet ready for neural training**.

Present: deterministic market/strategy features, replay data, source lineage, hashes, session boundaries, risk controls, and extensive tests.

Missing or insufficient: leakage-safe feature/label datasets with version IDs, temporal train/validation/test splits for neural targets, baseline model benchmark reports, calibration/uncertainty evaluation, model registry, drift monitoring, GPU/training profile, and champion/challenger promotion controls.

## F. BOT 2.0 gaps

- Plane separation is conceptual but needs explicit package/API boundaries for Research, Shadow/Validation, and Production.
- No standardized feature snapshot or decision-packet schema spanning model outputs, uncertainty, data quality, reason codes, risk response, and execution evidence.
- No specialized regime, temporal, volatility, setup, or microstructure model interfaces.
- No fusion/calibration/uncertainty service.
- No formal dataset, feature, label, configuration, model, or code-commit lineage manifest for training runs.
- No explicit no-trade-first decision API for model disagreement/uncertainty beyond deterministic strategy gates.
- No unified broker-neutral `MarketDataAdapter`, `ExecutionAdapter`, and `PaperBrokerAdapter` protocol shared by every lane.
- No complete end-to-end BOT 2.0 replay that exercises features → model shadow outputs → fusion → decision → risk → paper execution → reconciliation → black-box record.

## G. Proposed migration sequence

1. Create an isolated `bot2/phase0-audit` or equivalent branch from stable `main`.
2. Freeze and version the contracts listed in the migration map.
3. Define plane boundaries and schemas without changing current production behavior.
4. Build a read-only feature/label dataset foundation with temporal splits and lineage manifests.
5. Add simple statistical/ML baselines before any neural framework.
6. Add shadow-only model interfaces and a standardized decision packet.
7. Add calibration/uncertainty and model registry controls.
8. Integrate shadow outputs with the existing deterministic risk engine.
9. Extend the existing paper adapter/reconciliation path only after replay and failure-injection tests pass.
10. Run end-to-end replay, live shadow, then supervised paper; require explicit evidence gates for every promotion.

## H. Files expected to change during Phase 1

Phase 1 should be additive and isolated. Expected areas: `docs/`, `configs/` (new versioned BOT2 config), `validation/` or `bot2/validation/`, dataset/feature/label lineage modules, and tests. Existing `execution/`, `risk/`, broker connectivity, and current paper-trial code should not be modified until the interfaces are reviewed.

## I. New files/directories required later

The blueprint’s target structure is appropriate as a gradual package: `bot2/research`, `bot2/validation`, `bot2/features`, `bot2/labels`, `bot2/models`, `bot2/training`, `bot2/inference`, `bot2/decision`, `bot2/registry`, `bot2/monitoring`, and `bot2/recovery`. Do not create all of it in Phase 0; begin with contracts and lineage manifests.

## J. Risks before implementation

- Introducing PyTorch or other ML dependencies into `.venv` could destabilize the existing paper/replay environment.
- A model score must never bypass deterministic risk, stale-data, authority, or reconciliation gates.
- Small live captures are not sufficient for training or performance claims.
- Adaptive/research modules must remain comparison-only until their own datasets, models, controls, and OOS evidence exist.
- Any future broker adapter must be paper-only first and must not be allowed to infer live authority from connectivity.

## Phase 0 conclusion

The existing system has a substantial deterministic data, replay, risk, paper-accounting, and observability foundation. BOT 2.0 should be an additive research/shadow architecture around those controls, not a replacement. The next authorized action is to create an isolated branch and implement the Phase 1 data/feature/label contracts.
