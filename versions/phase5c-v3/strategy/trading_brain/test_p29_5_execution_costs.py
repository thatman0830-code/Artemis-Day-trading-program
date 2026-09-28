from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p29_2_position_sizing import PositionSizingEngine
from strategy.trading_brain.p29_4_exit_resolution import ExitReason, ExitResolutionEngine
from strategy.trading_brain.p29_5_execution_costs import *
from strategy.trading_brain.test_p29_2_position_sizing import facts
from strategy.trading_brain.test_p29_4_exit_resolution import active_facts, candle


def inputs(direction=StructuralRegime.BULLISH, zero=False):
    source = facts(direction); sizing = PositionSizingEngine().calculate(**source).proposal
    pset, ph, position = active_facts(direction)
    market = candle(high="104") if direction == StructuralRegime.BULLISH else candle(low="96")
    execution = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market).resolution
    if zero:
        spec = ExecutionCostSpecification("costs", "BTC", "v1", 1, Decimal("0.5"), Decimal("1"), CommissionModel.ZERO, Decimal("0"), CommissionModel.ZERO, Decimal("0"), SlippageModel.NONE, Decimal("0"), SlippageModel.NONE, Decimal("0"))
    else:
        spec = ExecutionCostSpecification("costs", "BTC", "v1", 1, Decimal("0.5"), Decimal("1"), CommissionModel.PERCENT_NOTIONAL, Decimal("0.1"), CommissionModel.FIXED_ORDER, Decimal("1"), SlippageModel.FIXED_PRICE, Decimal("0.1"), SlippageModel.FIXED_TICKS, Decimal("0.8"))
    return dict(entry_fill=source["fill"], sizing=sizing, exit_execution=execution, specification=spec, calculated_time=27)


@pytest.mark.parametrize("direction,economic_entry,economic_exit", [
    (StructuralRegime.BULLISH, Decimal("100.5"), Decimal("103.5")),
    (StructuralRegime.BEARISH, Decimal("99.5"), Decimal("96.5")),
])
def test_long_short_price_friction_is_adverse(direction, economic_entry, economic_exit):
    record = ExecutionCostEngine().calculate(**inputs(direction)).record
    assert record.economic_entry_price == economic_entry
    assert record.economic_exit_price == economic_exit
    assert record.price_friction_cash_cost == 0


def test_entry_exit_cash_components_and_exact_aggregation():
    record = ExecutionCostEngine().calculate(**inputs()).record
    assert (record.entry_notional, record.exit_notional) == (Decimal("2500"), Decimal("2600"))
    assert (record.entry_commission, record.exit_commission) == (Decimal("2.500"), Decimal("2.600"))
    assert (record.entry_transaction_fee, record.exit_transaction_fee) == (Decimal("1"), Decimal("1"))
    assert record.commission == Decimal("5.100")
    assert record.transaction_fees == Decimal("2")
    assert record.explicit_cash_costs == Decimal("7.100")
    assert record.rounding_mode == "NONE_CANONICAL_EXACT"


def test_zero_cost_configuration_preserves_mechanical_prices():
    record = ExecutionCostEngine().calculate(**inputs(zero=True)).record
    assert record.explicit_cash_costs == 0
    assert record.economic_entry_price == record.mechanical_entry_price
    assert record.economic_exit_price == record.mechanical_exit_price


@pytest.mark.parametrize("model,rate,expected", [
    (CommissionModel.PER_UNIT, "0.2", Decimal("10")),
    (CommissionModel.PER_CONTRACT, "0.2", Decimal("10")),
    (CommissionModel.FIXED_ORDER, "3", Decimal("6")),
    (CommissionModel.FIXED_TRADE, "3", Decimal("3")),
])
def test_canonical_cash_model_bases(model, rate, expected):
    values=inputs(zero=True); values["specification"]=replace(values["specification"], commission_model=model, commission_rate=Decimal(rate))
    assert ExecutionCostEngine().calculate(**values).record.commission == expected


@pytest.mark.parametrize("field", ["entry_fill", "sizing", "exit_execution", "specification"])
def test_missing_inputs_fail_closed(field):
    values=inputs(); values[field]=None
    assert ExecutionCostEngine().calculate(**values).error.reason == "REQUIRED_COST_INPUT_MISSING"


def test_negative_nonfinite_and_invalid_percentage_rejected():
    engine=ExecutionCostEngine(); values=inputs(); values["specification"]=replace(values["specification"], commission_rate=Decimal("-1"))
    assert engine.calculate(**values).error.reason == "NEGATIVE_COST_CONFIGURATION"
    values=inputs(); values["specification"]=replace(values["specification"], transaction_fee_rate=Decimal("NaN"))
    assert engine.calculate(**values).error.reason == "NON_FINITE_COST_INPUT"
    values=inputs(); values["specification"]=replace(values["specification"], slippage_model=SlippageModel.PERCENTAGE, slippage_value=Decimal("101"))
    assert engine.calculate(**values).error.reason == "PERCENTAGE_RATE_OUT_OF_RANGE"


def test_undefined_dynamic_models_fail_closed():
    values=inputs(); values["specification"]=replace(values["specification"], slippage_model=SlippageModel.VOLATILITY_DEPENDENT)
    assert ExecutionCostEngine().calculate(**values).error.reason == "UNDEFINED_DYNAMIC_PRICE_FRICTION_MODEL"


def test_identity_version_tick_and_chronology_validation():
    engine=ExecutionCostEngine(); values=inputs(); values["specification"]=replace(values["specification"], symbol="ETH")
    assert engine.calculate(**values).error.reason == "SYMBOL_IDENTITY_MISMATCH"
    values=inputs(); values["specification"]=replace(values["specification"], input_version="v2")
    assert engine.calculate(**values).error.reason == "INPUT_VERSION_MISMATCH"
    values=inputs(); values["specification"]=replace(values["specification"], minimum_tick=Decimal("0.3"))
    assert engine.calculate(**values).error.reason == "PRICE_TICK_GRID_MISMATCH"
    values=inputs(); values["calculated_time"]=25
    assert engine.calculate(**values).error.reason == "COST_INPUT_CHRONOLOGY_INVALID"


def test_duplicate_conflict_and_idempotent_replay():
    engine=ExecutionCostEngine(); values=inputs(); first=engine.calculate(**values)
    replay=engine.calculate(**values, history=first.history)
    assert replay.record == first.record and replay.history == first.history
    conflict=dict(values); conflict["calculated_time"]=28
    assert engine.calculate(**conflict, history=first.history).error.reason == "CONFLICTING_EXECUTION_COST_RECORD"


def test_record_is_immutable_and_sources_unchanged():
    values=inputs(); fill=values["entry_fill"]; sizing=values["sizing"]; execution=values["exit_execution"]
    result=ExecutionCostEngine().calculate(**values)
    assert (values["entry_fill"], values["sizing"], values["exit_execution"]) == (fill, sizing, execution)
    with pytest.raises(FrozenInstanceError):
        result.record.explicit_cash_costs = Decimal("0")
