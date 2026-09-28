# BOT 2.0 Migration Map

Classification is based on the Phase 0 repository audit. No classification grants execution authority.

| Existing component | Location | Classification | Migration decision |
|---|---|---|---|
| Databento live ES/NQ capture | `scripts/capture_databento_live_es_nq.py` | KEEP + HARDEN | Preserve raw/event and receipt timestamps; add unified quality-contract output and retention policy. |
| Databento historical/recovery archive | `futures_data/`, `data/databento_recovery_staging` | KEEP + HARDEN | Preserve hashes, raw-first behavior, caps, and lineage; expose a versioned dataset manifest. |
| Provider-neutral market feed/replay | `backtesting/provider_neutral_market_feed_v1.py` | KEEP + HARDEN | Make replay/live adapter contract explicit and reusable by shadow models. |
| Canonical bars/latency/mapping | `backtesting/databento_live_*`, provider-neutral latency tests | KEEP | Required data-quality gate for all planes. |
| Deterministic strategy brain | `strategy/trading_brain/`, `backtesting/orchestrator.py` | KEEP + HARDEN | Remain champion baseline and source of setup/label hypotheses; do not replace with a neural black box. |
| Legacy strategy modules | `strategy/` | REFACTOR | Wrap behind feature/setup interfaces incrementally; preserve behavior with regression fixtures. |
| Provider-neutral paper ledger | `backtesting/provider_neutral_paper_trial_v1.py` | KEEP + HARDEN | Preserve three-profile accounting and non-authority invariant; add completed simulated-fill lifecycle only through approved paper adapter. |
| Paper engine/gateway/OCO | `execution/paper_*` | KEEP + HARDEN | Make `PaperBrokerAdapter` contract explicit; add reconciliation/failure-injection coverage. |
| Existing risk engine/guards | `risk/`, `config/provider_neutral_hard_risk_controls.json` | KEEP | Absolute authority; neural proposals cannot bypass it. |
| Authority configuration | `config/provider_neutral_paper_authority.json` | KEEP + HARDEN | Version configuration and require independent promotion checks; live remains false. |
| Supervisor/watchdogs | `scripts/run_provider_neutral_pipeline_supervisor.ps1`, `scripts/guard_provider_neutral_supervisor.ps1`, `monitoring/` | KEEP + HARDEN | Add verifiable task/process identity, bounded retries, circuit breaker, and SAFE_HALT evidence. |
| Decision ledger/cockpit | `scripts/publish_provider_neutral_decision_ledger.py`, `scripts/publish_provider_neutral_cockpit.py` | KEEP + HARDEN | Extend to standardized BOT2 decision packet and black-box record. |
| BTC recorder | `execution/coinbase_btc_shadow_recorder_v1.py`, BTC scripts | KEEP + HARDEN | Keep as separate evidence lane; never use as ES/NQ model authority. |
| Forex Factory shadow lane | `scripts/run_forex_factory_shadow_trial.ps1`, `outputs/forex_factory_shadow_trial` | KEEP + HARDEN | Keep non-directional/news diagnostic boundary and hash-validated snapshots. |
| NinjaTrader evidence | `execution/ninjatrader_*`, `backtesting/ninjatrader_*` | DEPRECATE (active dependency) / KEEP (archive) | Preserve archived evidence and tests; do not make it a BOT2 live dependency. |
| Rithmic contract boundary | `backtesting/rithmic_provider_contract_v1.py` | KEEP + HARDEN | Keep provider-neutral contract; add adapter only after paper-only validation and credentials review. |
| Hyperliquid exchange client | `exchange/` | DEPRECATE for ES/NQ / KEEP for scoped BTC research | Isolate from BOT2 ES/NQ interfaces; do not delete until dependency audit is complete. |
| IBKR/other broker artifacts | `execution/ibkr_*` | UNKNOWN / INVESTIGATE | Preserve, inventory credentials and intended scope before reuse. |
| Feature engineering | scattered `strategy/`, `backtesting/` modules | REFACTOR | Consolidate into versioned feature contracts with no-future-data tests. |
| Labels/outcomes | replay and lifecycle modules | REFACTOR | Create explicit horizon/cost/cutoff label builders and temporal split manifests. |
| Model training | no current unified package | REPLACE (new subsystem) | Add simple baselines first, then specialized models only after dataset validation. |
| Model registry | no current unified registry | REPLACE (new subsystem) | Add model/version/feature/label/code lineage and approval lifecycle. |
| Calibration/uncertainty | partial analytics only | REFACTOR | Add calibration metrics, ensemble disagreement, uncertainty, and abstention contracts. |
| Fusion/decision packet | not yet standardized | REFACTOR | Add interpretable fusion and `LONG/SHORT/WAIT/BLOCK` proposal schema; no direct order path. |
| Monitoring/model drift | operational monitoring exists; model drift absent | REFACTOR | Add feature/prediction/calibration/regime drift reports without auto-deployment. |
| Research database | reports/artifacts distributed across repo | REFACTOR | Add experiment manifest and ACCEPT/REJECT/RETEST record. |
| Tests | broad unit/integration/adversarial suite | KEEP + HARDEN | Add BOT2 contract, leakage, model, calibration, replay, stress, and failure-injection tests. |
| Secrets/config | `.env` ignored; settings uses environment variables | KEEP + HARDEN | Keep secrets out of source; add configuration profiles and secret-presence audits. |
| Runtime outputs | `outputs/` (ignored, very large) | REFACTOR | Establish retention, immutable run manifests, and artifact indexing. |

## BOT 2.0 plane mapping

### Research plane

Uses historical/replay data, feature/label builders, training, ablation, calibration, walk-forward, holdout, stress, and Monte Carlo analysis. It may never mutate champion production configuration automatically.

### Shadow/validation plane

Consumes live validated data, emits model outputs, uncertainty, regime, setup probabilities, and proposals into the existing non-authoritative ledger. It cannot submit orders and remains comparison-only until explicit gates pass.

### Production/paper plane

Keeps deterministic risk, authority, paper adapters, reconciliation, and recorder controls. BOT2 proposals enter through a risk-approved adapter; live authority remains disabled unless separately authorized and evidenced.

## First implementation gate after Phase 0

Create a branch, then implement only:

1. `bot2/contracts/decision_packet_v1.json` and data-quality state contract.
2. Dataset/feature/label lineage manifest types.
3. Read-only adapter interfaces for market data and paper execution.
4. Contract tests proving stale data, unknown model, missing lineage, and unsafe authority produce `BLOCK`/`SAFE_HALT`.

Do not install a neural framework, modify broker connectivity, alter deterministic risk, or change paper execution until those contracts and tests are reviewed.
