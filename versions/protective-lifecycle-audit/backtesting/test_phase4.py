import ast
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.orchestrator import TradingBrainEvaluationOrchestrator
from backtesting.replay import DeterministicReplay
from backtesting.simulation import (
    HistoricalTradeSimulator, SimulationAccountInput, SimulationInstrumentInput,
    TradeSimulationConfiguration,
)
from backtesting.test_phase3 import BASE, active_range, build, candle, structure, continuation_data, continuation_request, ms
from backtesting.orchestrator import ContinuationEvaluationRequest
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p23_liquidity import LiquidityReference, LiquiditySide
from strategy.trading_brain.p29_1_entry_execution import ExecutionMode, OrderState
from strategy.trading_brain.p29_4_exit_resolution import ExitReason, PriceObservation
from strategy.trading_brain.p29_5_execution_costs import (
    CommissionModel, ExecutionCostSpecification, SlippageModel,
)
from strategy.trading_brain.position_state_contract import PositionState


def configuration(run, *, risk="1", minimum="0.01", costs=True):
    version = "simulation-v1"
    account = SimulationAccountInput("account-input", "simulated-account", run.starting_equity,
                                     Decimal(risk), version)
    instrument = SimulationInstrumentInput(
        "instrument-input", "BTC", Decimal("0.25"), Decimal("1"), Decimal("1"),
        Decimal(minimum), Decimal("0.01"), Decimal("1000"), version,
    )
    specification = ExecutionCostSpecification(
        run.execution_cost_configuration_id, "BTC", version, ms(BASE), Decimal("0.25"),
        Decimal("1"), CommissionModel.PERCENT_NOTIONAL,
        Decimal("0.1") if costs else Decimal("0"), CommissionModel.ZERO, Decimal("0"),
        SlippageModel.NONE, Decimal("0"),
        SlippageModel.FIXED_TICKS if costs else SlippageModel.NONE,
        Decimal("1") if costs else Decimal("0"),
    )
    return TradeSimulationConfiguration("phase4-config", account, instrument,
                                        specification, "phase4-v1", ExecutionMode.PAPER)


def run_phase4(extra, *, config_factory=configuration, observations=None):
    items = continuation_data() + tuple(extra)
    data, run = build(items)
    replay = DeterministicReplay(dataset=data, run=run)
    strategy = TradingBrainEvaluationOrchestrator(
        dataset=data, run=run, minimum_tick=Decimal("0.25"), calculation_version="phase3-v1")
    simulator = HistoricalTradeSimulator(run=run, configuration=config_factory(run))
    strategy_state = strategy.initial_state(); simulation_state = simulator.initial_state()
    commits = []
    for publication in replay:
        request = continuation_request() if publication.batch.sequence < 3 else None
        evaluated = strategy.evaluate(publication=publication, state=strategy_state, request=request)
        strategy_state = evaluated.state
        simulated = simulator.evaluate(publication=publication, evaluation=evaluated.result,
            state=simulation_state, finer_observations=observations or {})
        simulation_state = simulated.state; commits.append((publication, evaluated, simulated))
    return data, run, replay, strategy, simulator, strategy_state, simulation_state, commits


def touch():
    return candle(minute=15, timeframe="5m", open_="100", high="101", low="96.5", close="98")


def target():
    return candle(minute=20, timeframe="5m", open_="98", high="122", low="96", close="121")


def bearish_data():
    return (
        candle(minute=0, timeframe="5m", open_="106", high="110", low="105", close="106"),
        candle(minute=5, timeframe="5m", open_="104", high="106", low="95", close="96"),
        candle(minute=10, timeframe="5m", open_="96", high="101", low="90", close="95"),
    )


def bearish_request():
    refs = (
        LiquidityReference("short-target-a", "5m", LiquiditySide.LSL, Decimal("78"), ms(BASE), "PDL", True),
        LiquidityReference("short-target-b", "5m", LiquiditySide.LSL, Decimal("78"), ms(BASE), "PDL", True),
    )
    return ContinuationEvaluationRequest("request-short", "setup-short", StructuralRegime.BEARISH,
        structure(StructuralRegime.BEARISH), active_range(StructuralRegime.BEARISH), refs)


def test_long_flow_uses_future_touch_sizes_protects_exits_costs_and_closes():
    *_, state, commits = run_phase4((touch(), target()))
    trade = state.trades[0]
    assert trade.order.limit_price == Decimal("97.00") and trade.order.state is OrderState.FILLED
    assert trade.fill.candle_id == touch().id and trade.sizing.authorized is False
    assert trade.sizing.actual_risk_dollars <= trade.sizing.maximum_risk
    assert trade.protective_set.stop_order.price == Decimal("89.75")
    assert trade.protective_set.target_order.price == Decimal("122.00")
    assert trade.exit.exit_reason is ExitReason.TARGET
    assert trade.position.state is PositionState.CLOSED
    assert trade.costs.entry_slippage == Decimal("0.25")
    assert trade.costs.price_friction_cash_cost == Decimal("0")
    assert len(state.cost_history.records) == 1


def test_no_touch_stays_active_and_later_touch_is_not_retroactive():
    miss = candle(minute=15, timeframe="5m", open_="100", high="101", low="98", close="99")
    later = candle(minute=20, timeframe="5m", open_="99", high="100", low="96.75", close="98")
    *_, state, commits = run_phase4((miss, later))
    trade = state.trades[0]
    assert [e.touched for e in state.entry_history.evaluations] == [False, True]
    assert trade.fill.candle_id == later.id
    assert trade.created_batch_sequence < trade.filled_batch_sequence


def test_same_fill_candle_cannot_also_exit_and_collision_is_stop_priority():
    collision_fill = candle(minute=15, timeframe="5m", open_="100", high="123", low="89", close="100")
    collision = candle(minute=20, timeframe="5m", open_="100", high="123", low="89", close="100")
    *_, state, commits = run_phase4((collision_fill, collision))
    trade = state.trades[0]
    assert trade.fill.candle_id == collision_fill.id
    assert len(state.exit_history.evaluations) == 1
    assert trade.exit.market_data_id == collision.id
    assert trade.exit.exit_reason is ExitReason.OHLC_AMBIGUOUS_STOP_PRIORITY


def test_adverse_gap_and_finer_observation_precedence_are_canonical():
    gap = candle(minute=20, timeframe="5m", open_="89", high="90", low="88", close="89")
    *_, gap_state, _ = run_phase4((touch(), gap))
    assert gap_state.trades[0].exit.exit_reason is ExitReason.STOP_LOSS_GAP
    collision = candle(minute=20, timeframe="5m", open_="100", high="123", low="89", close="100")
    observations = {collision.id: (
        PriceObservation("first", Decimal("100"), ms(collision.open_time)),
        PriceObservation("target-first", Decimal("122"), ms(collision.open_time) + 1),
        PriceObservation("stop-later", Decimal("89.75"), ms(collision.open_time) + 2),
    )}
    *_, ordered_state, _ = run_phase4((touch(), collision), observations=observations)
    assert ordered_state.trades[0].exit.exit_reason is ExitReason.TARGET


def test_below_minimum_size_fails_closed_without_protective_or_position():
    def too_large_minimum(run):
        return configuration(run, minimum="100")
    *_, state, commits = run_phase4((touch(),), config_factory=too_large_minimum)
    trade = state.trades[0]
    assert trade.fill is not None and trade.sizing is None
    assert trade.protective_set is None and trade.position is None
    assert any(m.owner == "#29.2" for m in commits[-1][2].result.missing)


def test_configuration_identity_and_starting_equity_fail_closed():
    data, run = build(continuation_data())
    config = configuration(run)
    with pytest.raises(ValueError, match="starting equity"):
        HistoricalTradeSimulator(run=run, configuration=replace(
            config, account=replace(config.account, starting_equity=Decimal("9999"))))
    with pytest.raises(ValueError, match="cost"):
        HistoricalTradeSimulator(run=run, configuration=replace(
            config, execution_costs=replace(config.execution_costs, id="wrong")))


def test_state_and_outputs_are_immutable_and_replay_is_deterministic():
    *_, first, _ = run_phase4((touch(), target()))
    *_, second, _ = run_phase4((touch(), target()))
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.trades[0].position.state = PositionState.OPEN


def test_identical_batch_replay_is_idempotent_without_duplicate_history():
    data, run = build((continuation_data()[0],))
    replay = DeterministicReplay(dataset=data, run=run)
    strategy = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
        minimum_tick=Decimal("0.25"), calculation_version="phase3-v1")
    simulator = HistoricalTradeSimulator(run=run, configuration=configuration(run))
    publication = next(iter(replay))
    evaluated = strategy.evaluate(publication=publication, state=strategy.initial_state(), request=None)
    first = simulator.evaluate(publication=publication, evaluation=evaluated.result,
                               state=simulator.initial_state())
    repeated = simulator.evaluate(publication=publication, evaluation=evaluated.result, state=first.state)
    assert repeated == first


def test_global_one_position_and_duplicate_setup_are_not_reopened():
    *_, state, commits = run_phase4((touch(), target()))
    assert len(state.trades) == 1 and len(state.consumed_setup_ids) == 1
    assert sum(p.state is PositionState.OPEN for p in state.position_history.snapshots) == 1
    assert sum(p.state is PositionState.CLOSED for p in state.position_history.snapshots) == 1


def test_phase4_has_no_accounting_analytics_exchange_wallet_or_network_dependencies():
    tree = ast.parse((Path(__file__).parent / "simulation.py").read_text(encoding="utf-8"))
    imports = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
    imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    forbidden = ("p29_7_2", "analytics", "requests", "websocket", "hyperliquid", "wallet", "signing")
    assert not any(any(word in name.lower() for word in forbidden) for name in imports)


def test_atomic_unrelated_timeframe_does_not_change_execution_outcome():
    hold = candle(minute=20, timeframe="5m", open_="98", high="100", low="96", close="99")
    later_target = candle(minute=25, timeframe="5m", open_="99", high="122", low="98", close="121")
    same_close_15m = candle(minute=15, timeframe="15m", open_="100", high="101", low="99", close="100")
    *_, state, _ = run_phase4((touch(), hold, later_target, same_close_15m))
    assert state.trades[0].fill.candle_id == touch().id
    assert state.trades[0].exit.exit_reason is ExitReason.TARGET


def test_checkpoint_binds_open_position_and_exact_phase2_phase3_cursor():
    data, run = build(continuation_data() + (touch(),))
    replay = DeterministicReplay(dataset=data, run=run)
    strategy = TradingBrainEvaluationOrchestrator(dataset=data, run=run,
        minimum_tick=Decimal("0.25"), calculation_version="phase3-v1")
    simulator = HistoricalTradeSimulator(run=run, configuration=configuration(run))
    ss, xs = strategy.initial_state(), simulator.initial_state()
    for publication in replay:
        evaluated = strategy.evaluate(publication=publication, state=ss,
            request=continuation_request() if publication.batch.sequence < 3 else None)
        ss = evaluated.state
        xs = simulator.evaluate(publication=publication, evaluation=evaluated.result, state=xs).state
    replay_checkpoint = replay.checkpoint()
    orchestration_checkpoint = strategy.checkpoint(state=ss, replay_checkpoint=replay_checkpoint)
    checkpoint = simulator.checkpoint(state=xs, replay_checkpoint=replay_checkpoint,
                                      orchestration_checkpoint=orchestration_checkpoint)
    assert checkpoint.open_position_id == xs.trades[0].position.id
    assert checkpoint.active_order_id == xs.trades[0].order.id
    assert checkpoint.protective_set_id == xs.trades[0].protective_set.id
    assert checkpoint.equity_snapshot_id == xs.equity_ledger.latest.id
    simulator.validate_resume(state=xs, checkpoint=checkpoint,
        replay_checkpoint=replay_checkpoint, orchestration_checkpoint=orchestration_checkpoint)
    with pytest.raises(ValueError, match="checkpoint"):
        simulator.validate_resume(state=replace(xs, id="forged"), checkpoint=checkpoint,
            replay_checkpoint=replay_checkpoint, orchestration_checkpoint=orchestration_checkpoint)
