import ast
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.analytics import AnalyticsConfiguration, CanonicalAnalyticsOrchestrator
from backtesting.orchestrator import TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from backtesting.simulation import HistoricalTradeSimulator
from backtesting.test_phase3 import build, continuation_data
from backtesting.test_phase4 import configuration, run_phase4, target, touch
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel


def analytics(run):
    return CanonicalAnalyticsOrchestrator(run=run, configuration=AnalyticsConfiguration(
        "analytics-config", run.strategy_configuration_version, "5m",
        SetupModel.CONTINUATION, StructuralRegime.BULLISH, "simulation-v1",
        "phase5b-source-v1", "phase5b-v1", "phase5b-history-v1", "UTC"))


def completed():
    data, run, replay, strategy, simulator, strategy_state, state, commits = run_phase4((touch(), target()))
    return data, run, replay, strategy, simulator, strategy_state, state,


def zero_trade():
    data, run = build(continuation_data())
    replay = DeterministicReplay(dataset=data, run=run)
    strategy = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
        minimum_tick=Decimal("0.25"), calculation_version="phase3-v1")
    simulator = HistoricalTradeSimulator(run=run, configuration=configuration(run))
    ss, xs = strategy.initial_state(), simulator.initial_state()
    for publication in replay:
        evaluated = strategy.evaluate(publication=publication, state=ss, request=None); ss = evaluated.state
        xs = simulator.evaluate(publication=publication, evaluation=evaluated.result, state=xs).state
    return data, run, replay, strategy, simulator, ss, xs


def test_zero_trade_result_preserves_null_and_empty_canonical_outcomes():
    _, run, _, _, _, _, state = zero_trade()
    result = analytics(run).calculate(state=state, as_of=run.replay_end_exclusive)
    assert result.finalized_trade_count == result.win_count == result.loss_count == result.breakeven_count == 0
    assert result.starting_equity == result.ending_equity == run.starting_equity
    assert result.reference("#29.7.2.3").record.expectancy_net_pnl is None
    assert result.reference("#29.7.2.4").record.profit_factor is None
    distribution = result.reference("#29.7.2.10").record
    assert distribution.net_pnl_distribution == ()


def test_winning_trade_core_references_and_exact_equity_are_canonical():
    _, run, _, _, _, _, state = completed()
    result = analytics(run).calculate(state=state, as_of=run.replay_end_exclusive)
    assert (result.finalized_trade_count, result.win_count, result.loss_count, result.breakeven_count) == (1, 1, 0, 0)
    assert result.ending_equity == state.equity_ledger.latest.equity
    for owner in ("#29.7.2.1", "#29.7.2.2", "#29.7.2.3", "#29.7.2.4",
                  "#29.7.2.5", "#29.7.2.6", "#29.7.2.7", "#29.7.2.8",
                  "#29.7.2.9", "#29.7.2.10", "#29.7.2.12", "#29.7.2.13",
                  "#29.7.2.14", "#29.7.2.15"):
        assert result.reference(owner).status == "COMPLETE"
    assert result.reference("#29.7.2.5").record.final_cumulative_net_pnl == state.trades[0].accounting.net_pnl
    assert result.reference("#29.7.2.6").record.ending_equity == result.ending_equity


def test_drawdown_recovery_streak_distribution_and_path_records_are_referenced_not_copied():
    _, run, _, _, _, _, state = completed()
    result = analytics(run).calculate(state=state, as_of=run.replay_end_exclusive)
    assert result.reference("#29.7.2.7").record.equity_curve_snapshot_id == result.reference("#29.7.2.6").record.id
    assert result.reference("#29.7.2.12").record.source_drawdown_series_id == result.reference("#29.7.2.7").record.id
    assert result.reference("#29.7.2.14").record.source_streak_snapshot_id == result.reference("#29.7.2.8").record.id


def test_multi_strategy_analytics_are_explicitly_not_applicable_without_definition():
    _, run, _, _, _, _, state = completed()
    result = analytics(run).calculate(state=state, as_of=run.replay_end_exclusive)
    for owner in ("#29.7.2.16", "#29.7.2.17", "#29.7.2.19", "#29.7.2.20"):
        assert result.reference(owner).status == "NOT_APPLICABLE"
        assert result.reference(owner).record is None
    assert result.reference("#29.7.2.18").status == "COMPLETE"


def test_no_lookahead_scope_run_and_incomplete_lifecycle_fail_closed():
    _, run, _, _, _, _, state = completed()
    with pytest.raises(ValueError, match="completed replay"):
        analytics(run).calculate(state=state, as_of=run.replay_start_inclusive)
    with pytest.raises(ValueError, match="scope"):
        bad = replace(analytics(run).configuration, input_version="wrong")
        CanonicalAnalyticsOrchestrator(run=run, configuration=bad).calculate(
            state=state, as_of=run.replay_end_exclusive)
    active_state = replace(state, trades=(replace(state.trades[0], exit=None),))
    with pytest.raises(ValueError, match="incomplete"):
        analytics(run).calculate(state=active_state, as_of=run.replay_end_exclusive)


def test_result_identity_is_deterministic_immutable_and_checkpoint_resume_exact():
    _, run, _, _, simulator, _, state = completed()
    engine = analytics(run)
    first = engine.calculate(state=state, as_of=run.replay_end_exclusive)
    second = engine.calculate(state=state, as_of=run.replay_end_exclusive)
    assert first == second
    checkpoint = engine.checkpoint(state=state, result=first)
    engine.validate_resume(state=state, result=first, checkpoint=checkpoint)
    with pytest.raises(ValueError, match="checkpoint"):
        engine.validate_resume(state=replace(state, id="forged"), result=first, checkpoint=checkpoint)
    with pytest.raises(FrozenInstanceError):
        first.ending_equity = Decimal("0")


def test_analytics_are_terminal_and_have_no_exchange_wallet_network_dependencies():
    tree = ast.parse((Path(__file__).parent / "analytics.py").read_text(encoding="utf-8"))
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    forbidden = ("orchestrator", "p29_1", "p29_2", "exchange", "requests",
                 "websocket", "wallet", "signing", "private_key", "hyperliquid")
    assert not any(any(word in name.lower() for word in forbidden) for name in imports)
