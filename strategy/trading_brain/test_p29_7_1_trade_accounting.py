from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_3_protective_orders import ProtectiveOrderEngine
from strategy.trading_brain.p29_4_exit_resolution import ExitResolutionEngine
from strategy.trading_brain.p29_5_execution_costs import *
from strategy.trading_brain.p29_6_position_lifecycle import PositionLifecycleEngine, PositionState
from strategy.trading_brain.p29_7_1_trade_accounting import *
from strategy.trading_brain.test_p29_3_protective_orders import protective_inputs
from strategy.trading_brain.test_p29_4_exit_resolution import candle


def completed(direction=StructuralRegime.BULLISH, target=True, costs=False, model=SetupModel.CONTINUATION, multiplier="1"):
    values=protective_inputs(direction, model)
    if Decimal(multiplier) != 1:
        values["sizing"] = replace(values["sizing"], contract_multiplier=Decimal(multiplier))
    protective=ProtectiveOrderEngine(); created=protective.create(**values)
    active=protective.activate(protective_set=created.protective_set, activation_time=25, history=created.history)
    lifecycle=PositionLifecycleEngine(); opened=lifecycle.open(entry_order=values["entry_order"], fill=values["fill"], sizing=values["sizing"], protective_set=active.protective_set, protective_history=active.history)
    if direction == StructuralRegime.BULLISH:
        market=candle(high="104") if target else candle(low="98")
    else:
        market=candle(low="96") if target else candle(high="102")
    exit_result=ExitResolutionEngine().evaluate(protective_set=active.protective_set, protective_history=active.history, position=lifecycle.open_boundary(opened.position), market=market)
    closed=lifecycle.close(position=opened.position, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=opened.history)
    if costs:
        spec=ExecutionCostSpecification("costs", "BTC", "v1", 1, Decimal("0.5"), Decimal(multiplier), CommissionModel.PERCENT_NOTIONAL, Decimal("0.1"), CommissionModel.FIXED_ORDER, Decimal("1"), SlippageModel.FIXED_PRICE, Decimal("0.1"), SlippageModel.FIXED_TICKS, Decimal("0.8"))
    else:
        spec=ExecutionCostSpecification("costs", "BTC", "v1", 1, Decimal("0.5"), Decimal(multiplier), CommissionModel.ZERO, Decimal("0"), CommissionModel.ZERO, Decimal("0"), SlippageModel.NONE, Decimal("0"), SlippageModel.NONE, Decimal("0"))
    cost=ExecutionCostEngine().calculate(entry_fill=values["fill"], sizing=values["sizing"], exit_execution=exit_result.resolution, specification=spec, calculated_time=27)
    return dict(strategy_id="canonical", position=closed.position, entry_fill=values["fill"], sizing=values["sizing"], exit_execution=exit_result.resolution, costs=cost.record, accounting_time=28)


@pytest.mark.parametrize("direction,target,gross,result", [
    (StructuralRegime.BULLISH, True, Decimal("100"), TradeResult.WIN),
    (StructuralRegime.BULLISH, False, Decimal("-50"), TradeResult.LOSS),
    (StructuralRegime.BEARISH, True, Decimal("100"), TradeResult.WIN),
    (StructuralRegime.BEARISH, False, Decimal("-50"), TradeResult.LOSS),
])
def test_profitable_and_losing_long_short(direction, target, gross, result):
    record=TradeAccountingEngine().calculate(**completed(direction, target)).record
    assert record.gross_pnl == record.net_pnl == gross
    assert record.trade_result == result
    assert record.gross_r == record.net_r == gross / Decimal("100")


@pytest.mark.parametrize("model", [SetupModel.CONTINUATION, SetupModel.REVERSAL_1])
def test_model_semantics_and_source_identities(model):
    values=completed(model=model); record=TradeAccountingEngine().calculate(**values).record
    assert record.model == model
    assert record.entry_fill_id == values["entry_fill"].id
    assert record.position_id == values["position"].id
    assert record.exit_execution_id == values["exit_execution"].id


def test_nonzero_costs_and_price_friction_not_double_counted():
    record=TradeAccountingEngine().calculate(**completed(costs=True)).record
    assert record.economic_entry_price == Decimal("100.5")
    assert record.economic_exit_price == Decimal("103.5")
    assert record.gross_pnl == Decimal("75.0")
    assert record.explicit_cash_costs == Decimal("7.100")
    assert record.net_pnl == Decimal("67.900")
    assert record.gross_r == Decimal("0.75") and record.net_r == Decimal("0.679")


def test_breakeven_classification_uses_exact_net_not_exit_label():
    values=completed(); base=values["costs"]
    values["costs"]=replace(base, entry_commission=Decimal("100"), commission=Decimal("100"), explicit_cash_costs=Decimal("100"))
    record=TradeAccountingEngine().calculate(**values).record
    assert record.net_pnl == 0 and record.trade_result == TradeResult.BREAKEVEN


def test_contract_multiplier_applies_once_to_gross_pnl():
    record=TradeAccountingEngine().calculate(**completed(multiplier="2")).record
    assert record.contract_multiplier == 2 and record.gross_pnl == Decimal("200")


@pytest.mark.parametrize("field", ["position", "entry_fill", "sizing", "exit_execution", "costs"])
def test_missing_inputs_fail_closed(field):
    values=completed(); values[field]=None
    assert TradeAccountingEngine().calculate(**values).error.reason == "REQUIRED_ACCOUNTING_INPUT_MISSING"


def test_nonclosed_nonpositive_risk_and_nonfinite_inputs_fail_closed():
    engine=TradeAccountingEngine(); values=completed(); values["position"]=replace(values["position"], state=PositionState.OPEN)
    assert engine.calculate(**values).error.reason == "POSITION_NOT_CANONICALLY_CLOSED"
    values=completed(); values["sizing"]=replace(values["sizing"], actual_risk_dollars=Decimal("0"))
    assert engine.calculate(**values).error.reason == "NON_POSITIVE_ACCOUNTING_INPUT"
    values=completed(); values["costs"]=replace(values["costs"], economic_exit_price=Decimal("NaN"))
    assert engine.calculate(**values).error.reason == "NON_FINITE_ACCOUNTING_INPUT"


def test_identity_version_cost_aggregation_and_chronology_fail_closed():
    engine=TradeAccountingEngine(); values=completed(); values["position"]=replace(values["position"], setup_id="other")
    assert engine.calculate(**values).error.reason == "ACCOUNTING_SOURCE_IDENTITY_MISMATCH"
    values=completed(); values["costs"]=replace(values["costs"], input_version="v2")
    assert engine.calculate(**values).error.reason == "ACCOUNTING_INPUT_VERSION_MISMATCH"
    values=completed(costs=True); values["costs"]=replace(values["costs"], explicit_cash_costs=Decimal("8"))
    assert engine.calculate(**values).error.reason == "EXECUTION_COST_DOUBLE_COUNT_OR_AGGREGATION_INVALID"
    values=completed(); values["accounting_time"]=25
    assert engine.calculate(**values).error.reason == "ACCOUNTING_CHRONOLOGY_INVALID"


def test_idempotent_replay_conflict_and_immutability():
    engine=TradeAccountingEngine(); values=completed(); first=engine.calculate(**values)
    replay=engine.calculate(**values, history=first.history)
    assert replay.record == first.record and replay.history == first.history
    conflict=dict(values); conflict["accounting_time"]=29
    assert engine.calculate(**conflict, history=first.history).error.reason == "CONFLICTING_TRADE_ACCOUNTING_RECORD"
    with pytest.raises(FrozenInstanceError):
        first.record.net_pnl = Decimal("0")


def test_post_trade_equity_is_a_fact_without_upstream_mutation():
    values=completed(); sizing=values["sizing"]
    record=TradeAccountingEngine().calculate(**values).record
    assert record.pre_trade_equity == Decimal("10000")
    assert record.account_equity_change == record.net_pnl
    assert record.post_trade_equity == record.pre_trade_equity + record.net_pnl
    assert values["sizing"] == sizing
