from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p13_stop_loss_selection import StopSelection
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_1_entry_execution import EntryExecutionEngine
from strategy.trading_brain.p29_2_position_sizing import *
from strategy.trading_brain.test_p29_1_entry_execution import bar, inputs


def facts(direction=StructuralRegime.BULLISH, model=SetupModel.CONTINUATION, tick_value="1", minimum="0.1", increment="0.1", maximum=None):
    q, selection, context, availability = inputs(model, direction)
    stop_price = Decimal("98") if direction == StructuralRegime.BULLISH else Decimal("102")
    q = replace(q, stop=stop_price)
    stop = StopSelection("stop", q.setup_id, selection.id, model, direction, "REFERENCE", "ref", Decimal("98.5"), Decimal("0.5"), Decimal("100"), stop_price, 15)
    entry = EntryExecutionEngine()
    pending = entry.create_order(qualification=q, selection=selection, context=context, position_availability=availability, created_time=20)
    active = entry.activate_order(order=pending.order, activation_time=21, history=pending.history)
    filled = entry.evaluate_candle(order=active.order, candle=bar(), history=active.history)
    account = PreFillAccountFact("account-fact", "paper-account", Decimal("10000"), 20, "v1")
    risk = SizingRiskConfiguration("risk-config", Decimal("1"), 1, "v1")
    constraints = InstrumentSizingConstraints("instrument", "BTC", Decimal("0.5"), Decimal(tick_value), Decimal("1"), Decimal(minimum), Decimal(increment), 1, "v1", Decimal(maximum) if maximum else None)
    return dict(qualification=q, selection=selection, stop=stop, order=filled.order, fill=filled.fill, account=account, risk_configuration=risk, constraints=constraints, calculated_time=23)


@pytest.mark.parametrize("direction,model", [
    (StructuralRegime.BULLISH, SetupModel.CONTINUATION),
    (StructuralRegime.BEARISH, SetupModel.CONTINUATION),
    (StructuralRegime.BULLISH, SetupModel.REVERSAL_1),
])
def test_long_short_and_model_semantics(direction, model):
    result = PositionSizingEngine().calculate(**facts(direction, model))
    assert result.valid
    assert result.proposal.proposed_quantity == Decimal("25")
    assert result.proposal.maximum_risk == result.proposal.actual_risk_dollars == Decimal("100")
    assert result.proposal.authorized is False


def test_quantity_is_floored_and_never_exceeds_risk():
    result = PositionSizingEngine().calculate(**facts(tick_value="1.5"))
    assert result.proposal.raw_quantity == Decimal("16.66666666666666666666666667")
    assert result.proposal.proposed_quantity == Decimal("16.6")
    assert result.proposal.actual_risk_dollars == Decimal("99.60")
    assert result.proposal.actual_risk_dollars < result.proposal.maximum_risk


def test_minimum_boundary_and_below_minimum():
    exact = PositionSizingEngine().calculate(**facts(minimum="25", increment="1"))
    assert exact.proposal.proposed_quantity == Decimal("25")
    below = PositionSizingEngine().calculate(**facts(minimum="26", increment="1"))
    assert below.error.reason == "POSITION_QUANTITY_OUTSIDE_PERMITTED_RISK_OR_SIZE"


def test_exchange_maximum_is_floored_to_increment():
    result = PositionSizingEngine().calculate(**facts(maximum="10.07"))
    assert result.proposal.proposed_quantity == Decimal("10.0")
    assert result.proposal.actual_risk_dollars == Decimal("40.0")


@pytest.mark.parametrize("field", ["account", "risk_configuration", "constraints", "stop", "fill"])
def test_missing_inputs_fail_closed(field):
    values = facts(); values[field] = None
    assert PositionSizingEngine().calculate(**values).error.reason == "REQUIRED_SIZING_INPUT_MISSING"


def test_stale_mismatched_and_versioned_inputs_fail_closed():
    engine = PositionSizingEngine(); values = facts()
    values["account"] = replace(values["account"], as_of_time=19)
    assert engine.calculate(**values).error.reason == "SIZING_INPUT_CHRONOLOGY_INVALID"
    values = facts(); values["constraints"] = replace(values["constraints"], symbol="ETH")
    assert engine.calculate(**values).error.reason == "SYMBOL_IDENTITY_MISMATCH"
    values = facts(); values["account"] = replace(values["account"], input_version="v2")
    assert engine.calculate(**values).error.reason == "INPUT_VERSION_MISMATCH"


@pytest.mark.parametrize("direction,bad_stop,reason", [
    (StructuralRegime.BULLISH, Decimal("101"), "LONG_STOP_GEOMETRY_INVALID"),
    (StructuralRegime.BEARISH, Decimal("99"), "SHORT_STOP_GEOMETRY_INVALID"),
])
def test_invalid_directional_geometry(direction, bad_stop, reason):
    values = facts(direction); values["stop"] = replace(values["stop"], stop_price=bad_stop)
    values["qualification"] = replace(values["qualification"], stop=bad_stop)
    assert PositionSizingEngine().calculate(**values).error.reason == reason


@pytest.mark.parametrize("field,value", [("risk_percent", "NaN"), ("risk_percent", "0"), ("risk_percent", "101")])
def test_invalid_risk_configuration(field, value):
    values = facts(); values["risk_configuration"] = replace(values["risk_configuration"], **{field: Decimal(value)})
    assert PositionSizingEngine().calculate(**values).error.code == PositionSizingErrorCode.POSITION_SIZE_INVALID


def test_deterministic_replay_and_immutability():
    engine = PositionSizingEngine(); values = facts()
    first = engine.calculate(**values); second = engine.calculate(**values)
    assert first == second and first.proposal.id == second.proposal.id
    with pytest.raises(FrozenInstanceError):
        first.proposal.proposed_quantity = Decimal("999")


def test_source_identity_mismatch_and_unconfirmed_fill_fail_closed():
    values = facts(); values["stop"] = replace(values["stop"], setup_id="other")
    assert PositionSizingEngine().calculate(**values).error.reason == "SIZING_INPUT_IDENTITY_MISMATCH"
    values = facts(); values["fill"] = replace(values["fill"], event="OTHER")
    assert PositionSizingEngine().calculate(**values).error.reason == "ENTRY_FILL_NOT_CONFIRMED"
