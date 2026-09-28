from __future__ import annotations

import ast
import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from backtesting.file_runner import build_pipeline, execute, load_inputs
from backtesting.orchestrator import TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from strategy.trading_brain.p23_liquidity import LiquidityPoolEngine


ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples" / "backtesting"


def paths(name="canonical_trade"):
    root = EXAMPLES / name
    return root / "dataset_manifest.json", root / "backtest_config.json"


def test_canonical_zero_and_genuine_trade_examples_use_full_pipeline():
    zero = load_inputs(*paths("canonical_zero"))
    _, _, zero_state, zero_result = execute(*zero)
    assert zero_result.finalized_trade_count == 0 and not zero_state.trades

    trade = load_inputs(*paths())
    _, _, state, result = execute(*trade)
    assert result.finalized_trade_count == 1
    assert len(state.trades) == 1
    lifecycle = state.trades[0]
    assert lifecycle.accounting is not None
    assert lifecycle.created_batch_sequence < lifecycle.filled_batch_sequence
    assert lifecycle.exit is not None
    assert lifecycle.accounting.closed_time > lifecycle.fill.fill_time
    assert state.equity_ledger.latest.equity == lifecycle.accounting.post_trade_equity
    readiness = result.reference("OWNER_WIN_RATE_OBJECTIVE_V1").record
    assert readiness.outcome.value == "INSUFFICIENT_SAMPLE"
    assert not readiness.live_trading_authorized
    assert result.risk_reward_policy_id == "OWNER_MIN_RR_V1"
    assert result.performance_objective_id == "OWNER_WIN_RATE_OBJECTIVE_V1"


def test_structural_and_prior_period_references_reach_existing_23_pool_engine():
    dataset, raw, config = load_inputs(*paths())
    _, run, simulation = build_pipeline(dataset, raw, config)
    replay = DeterministicReplay(dataset=dataset, run=run)
    engine = TradingBrainEvaluationOrchestrator(
        dataset=dataset, run=run, minimum_tick=simulation.instrument.minimum_tick,
        calculation_version=config["calculation_version"], account_timezone="UTC",
        canonical_mode=True, enabled_prior_period_reference_types=("PDH", "PDL"),
    )
    state = engine.initial_state()
    for publication in replay:
        state = engine.evaluate(publication=publication, state=state).state
    structural = state.liquidity_reference_ledger.active_references
    prior = state.prior_period_reference_ledger.active_references
    inventory = LiquidityPoolEngine(minimum_tick=simulation.instrument.minimum_tick).build_inventory(
        references=structural + prior, active_range=None,
    )
    assert any(
        {"STRUCTURAL_SWING", "PDH"} <= set(pool.component_source_types)
        for pool in inventory.pools
    )
    with pytest.raises(FrozenInstanceError):
        state.canonical_mode = False


def test_canonical_validation_rejects_unknown_mode_prebuilt_and_policy(tmp_path):
    manifest, configuration = paths()
    config = json.loads(configuration.read_text())
    for key, value, match in (
        ("setup_request_mode", "UNKNOWN", "unknown setup_request_mode"),
        ("prebuilt_setup", {"armed": True}, "configuration fields invalid"),
        ("displacement_policy_id", "OTHER", "displacement policy"),
        ("risk_reward_policy_id", "OTHER", "risk-to-reward policy"),
        ("performance_objective_id", "OTHER", "performance objective"),
    ):
        changed = dict(config); changed[key] = value
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps(changed), encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            load_inputs(manifest, path)
    requires_week = dict(config)
    requires_week["enabled_prior_period_reference_types"] = ["PDH", "PDL", "PWH", "PWL"]
    path = tmp_path / "week.json"
    path.write_text(json.dumps(requires_week), encoding="utf-8")
    with pytest.raises(ValueError, match="prior week warm-up"):
        load_inputs(manifest, path)


def test_canonical_run_is_deterministic_and_no_pyramiding():
    inputs = load_inputs(*paths())
    first = execute(*inputs)
    second = execute(*inputs)
    assert first[1:] == second[1:]
    state = first[2]
    active_by_batch = [row.active_trade_id for row in state.batch_results]
    assert all(value is None or isinstance(value, str) for value in active_by_batch)
    assert len({trade.setup_fact_id for trade in state.trades}) == len(state.trades)


def test_canonical_checkpoint_binds_all_five_producer_ledgers():
    dataset, raw, config = load_inputs(*paths())
    _, run, simulation = build_pipeline(dataset, raw, config)
    replay = DeterministicReplay(dataset=dataset, run=run)
    engine = TradingBrainEvaluationOrchestrator(
        dataset=dataset, run=run, minimum_tick=simulation.instrument.minimum_tick,
        calculation_version=config["calculation_version"], canonical_mode=True,
        enabled_prior_period_reference_types=("PDH", "PDL"),
    )
    state = engine.initial_state()
    for _ in range(30):
        publication = next(replay)
        state = engine.evaluate(publication=publication, state=state).state
    checkpoint = engine.checkpoint(state=state, replay_checkpoint=replay.checkpoint())
    engine.validate_resume(
        state=state, checkpoint=checkpoint, replay_checkpoint=replay.checkpoint(),
    )
    assert state.structural_ledgers
    assert state.displacement_ledger.records
    assert state.prior_period_reference_ledger.evaluations


def test_canonical_runner_has_no_network_exchange_or_secret_dependency():
    modules = ("file_runner.py", "orchestrator.py", "simulation.py")
    imports = set()
    for name in modules:
        tree = ast.parse((ROOT / "backtesting" / name).read_text(encoding="utf-8"))
        imports |= {node.module or "" for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom)}
        imports |= {alias.name for node in ast.walk(tree)
                    if isinstance(node, ast.Import) for alias in node.names}
    forbidden = ("requests", "websocket", "wallet", "signing", "private_key",
                 "hyperliquid.exchange")
    assert not any(any(term in name.lower() for term in forbidden) for name in imports)
