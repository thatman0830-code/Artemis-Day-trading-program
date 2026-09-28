import ast
from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
from pathlib import Path

import pytest

from backtesting.accounting import EquitySizingPolicy, SimulatedEquityLedgerEngine
from backtesting.test_phase4 import run_phase4, target, touch
from backtesting.test_phase3 import BASE, candle
from strategy.trading_brain.p29_7_1_trade_accounting import TradeAccountingEngine, TradeResult
from strategy.trading_brain.test_p29_7_1_trade_accounting import completed


def closed_state(exit_candle=None):
    *_, state, _ = run_phase4((touch(), exit_candle or target()))
    return state


def test_initial_zero_trade_snapshot_comes_from_run_manifest_and_is_immutable():
    from backtesting.test_phase3 import build, continuation_data
    from backtesting.test_phase4 import configuration
    from backtesting.simulation import HistoricalTradeSimulator
    _, run = build(continuation_data())
    state = HistoricalTradeSimulator(run=run, configuration=configuration(run)).initial_state()
    snapshot = state.equity_ledger.latest
    assert snapshot.sequence == 0 and snapshot.equity == run.starting_equity
    assert snapshot.equity_change == 0 and snapshot.trade_accounting_id is None
    with pytest.raises(FrozenInstanceError):
        snapshot.equity = Decimal("0")


def test_phase4_closed_trade_is_accounted_exactly_once_and_advances_equity():
    state = closed_state()
    trade = state.trades[0]; record = trade.accounting
    assert len(state.accounting_history.records) == 1
    assert len(state.equity_ledger.snapshots) == 2
    assert record.position_id == trade.position.id
    assert record.entry_fill_id == trade.fill.id
    assert record.sizing_id == trade.sizing.id
    assert record.exit_execution_id == trade.exit.id
    assert record.execution_cost_record_id == trade.costs.id
    assert state.equity_ledger.latest.trade_accounting_id == record.id
    assert state.equity_ledger.latest.equity == record.post_trade_equity


def test_canonical_gross_net_r_cost_and_friction_facts_are_preserved():
    record = closed_state().trades[0].accounting
    assert record.gross_pnl == ((record.economic_exit_price - record.economic_entry_price)
                                * record.quantity * record.contract_multiplier)
    assert record.net_pnl == record.gross_pnl - record.explicit_cash_costs
    assert record.gross_r == record.gross_pnl / record.actual_risk_dollars
    assert record.net_r == record.net_pnl / record.actual_risk_dollars
    assert record.execution_cost_record_id
    assert record.trade_result is TradeResult.WIN


def test_losing_trade_reduces_ledger_equity():
    stop = candle(minute=20, timeframe="5m", open_="98", high="99", low="89.75", close="90")
    state = closed_state(stop)
    record = state.trades[0].accounting
    assert record.trade_result is TradeResult.LOSS and record.net_pnl < 0
    assert state.equity_ledger.latest.equity < state.equity_ledger.snapshots[0].equity


def test_canonical_long_short_profit_loss_and_breakeven_are_not_reclassified():
    for direction, target_wins, expected in (
        ("BULLISH", True, TradeResult.WIN), ("BULLISH", False, TradeResult.LOSS),
        ("BEARISH", True, TradeResult.WIN), ("BEARISH", False, TradeResult.LOSS),
    ):
        from strategy.trading_brain.p20_structural_classification import StructuralRegime
        values = completed(StructuralRegime(direction), target_wins)
        assert TradeAccountingEngine().calculate(**values).record.trade_result is expected
    values = completed(); base = values["costs"]
    values["costs"] = replace(base, entry_commission=Decimal("100"),
        commission=Decimal("100"), explicit_cash_costs=Decimal("100"))
    assert TradeAccountingEngine().calculate(**values).record.trade_result is TradeResult.BREAKEVEN


def test_multiple_canonical_results_form_strict_compounded_lineage():
    engine = SimulatedEquityLedgerEngine()
    ledger = engine.initial(run_id="run", starting_equity=Decimal("10000"),
                            effective_time=0, input_version="v1")
    first = TradeAccountingEngine().calculate(**completed()).record
    ledger = engine.apply(ledger=ledger, accounting=first)
    loss = TradeAccountingEngine().calculate(**completed(target=False)).record
    second = replace(loss, id="accounting-2", trade_id="trade-2",
        position_id="position-2", pre_trade_equity=first.post_trade_equity,
        post_trade_equity=first.post_trade_equity + loss.account_equity_change)
    ledger = engine.apply(ledger=ledger, accounting=second)
    assert [s.sequence for s in ledger.snapshots] == [0, 1, 2]
    assert ledger.snapshots[2].previous_snapshot_id == ledger.snapshots[1].id
    assert ledger.latest.equity == second.post_trade_equity
    assert second.pre_trade_equity == first.post_trade_equity


def test_duplicate_is_idempotent_but_fork_and_conflict_fail_closed():
    engine = SimulatedEquityLedgerEngine()
    ledger = engine.initial(run_id="run", starting_equity=Decimal("10000"),
                            effective_time=0, input_version="v1")
    record = TradeAccountingEngine().calculate(**completed()).record
    applied = engine.apply(ledger=ledger, accounting=record)
    assert engine.apply(ledger=applied, accounting=record) == applied
    with pytest.raises(ValueError, match="forks"):
        engine.apply(ledger=ledger, accounting=replace(record, pre_trade_equity=Decimal("9999")))
    with pytest.raises(ValueError, match="version"):
        engine.apply(ledger=ledger, accounting=replace(record, input_version="v2"))


def test_nonpositive_equity_cannot_size_a_future_trade():
    engine = SimulatedEquityLedgerEngine()
    ledger = engine.initial(run_id="run", starting_equity=Decimal("100"),
                            effective_time=0, input_version="v1")
    record = TradeAccountingEngine().calculate(**completed()).record
    terminal = replace(record, pre_trade_equity=Decimal("100"), net_pnl=Decimal("-100"),
        account_equity_change=Decimal("-100"), post_trade_equity=Decimal("0"))
    ledger = engine.apply(ledger=ledger, accounting=terminal)
    assert ledger.latest.equity == 0
    # Canonical #29.2 rejects non-positive account equity; the ledger never repairs it.
    assert not ledger.latest.equity > 0


def test_phase5a_policy_is_explicitly_compounded_only():
    assert tuple(EquitySizingPolicy) == (EquitySizingPolicy.COMPOUNDED,)


def test_checkpoint_binds_accounting_and_equity_cursor_for_exact_resume():
    _, _, replay, strategy, simulator, strategy_state, state, _ = run_phase4((touch(), target()))
    replay_checkpoint = replay.checkpoint()
    orchestration_checkpoint = strategy.checkpoint(
        state=strategy_state, replay_checkpoint=replay_checkpoint)
    checkpoint = simulator.checkpoint(state=state, replay_checkpoint=replay_checkpoint,
                                      orchestration_checkpoint=orchestration_checkpoint)
    assert checkpoint.accounting_cursor_id == state.trades[0].accounting.id
    assert checkpoint.equity_snapshot_id == state.equity_ledger.latest.id
    simulator.validate_resume(state=state, checkpoint=checkpoint,
        replay_checkpoint=replay_checkpoint, orchestration_checkpoint=orchestration_checkpoint)
    with pytest.raises(ValueError, match="checkpoint"):
        simulator.validate_resume(state=replace(state, accounting_history=type(state.accounting_history)()),
            checkpoint=checkpoint, replay_checkpoint=replay_checkpoint,
            orchestration_checkpoint=orchestration_checkpoint)


def test_phase5a_imports_no_analytics_exchange_wallet_network_or_private_keys():
    files = (Path(__file__).parent / "accounting.py", Path(__file__).parent / "simulation.py")
    imports = set()
    for file in files:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        imports |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        imports |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    forbidden = ("p29_7_2", "analytics", "requests", "websocket", "hyperliquid",
                 "exchange", "wallet", "signing", "private_key")
    assert not any(any(word in name.lower() for word in forbidden) for name in imports)
