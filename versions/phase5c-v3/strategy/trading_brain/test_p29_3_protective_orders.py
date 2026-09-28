from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p23_liquidity import LiquiditySide
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_1_entry_execution import OrderSide, OrderState
from strategy.trading_brain.p29_2_position_sizing import PositionSizingEngine
from strategy.trading_brain.p29_3_protective_orders import *
from strategy.trading_brain.test_p29_2_position_sizing import facts


def protective_inputs(direction=StructuralRegime.BULLISH, model=SetupModel.CONTINUATION):
    values = facts(direction, model)
    sizing = PositionSizingEngine().calculate(**values).proposal
    target_price = Decimal("104") if direction == StructuralRegime.BULLISH else Decimal("96")
    q = replace(values["qualification"], target=target_price)
    side = LiquiditySide.BSL if direction == StructuralRegime.BULLISH else LiquiditySide.LSL
    target = LRL("target", LRLRole.CONTINUATION_TARGET, "pool", "5m", side, target_price, True, "range", direction, 10)
    return dict(qualification=q, stop=values["stop"], target=target, entry_order=values["order"], fill=values["fill"], sizing=sizing, created_time=24)


@pytest.mark.parametrize("direction,exit_side,stop_price,target_price", [
    (StructuralRegime.BULLISH, OrderSide.SELL, Decimal("98"), Decimal("104")),
    (StructuralRegime.BEARISH, OrderSide.BUY, Decimal("102"), Decimal("96")),
])
@pytest.mark.parametrize("model", [SetupModel.CONTINUATION, SetupModel.REVERSAL_1])
def test_exact_long_short_protective_sets(direction, exit_side, stop_price, target_price, model):
    result = ProtectiveOrderEngine().create(**protective_inputs(direction, model))
    assert result.valid
    assert result.protective_set.stop_order.price == stop_price
    assert result.protective_set.target_order.price == target_price
    assert result.protective_set.stop_order.quantity == result.protective_set.target_order.quantity == Decimal("25")
    assert result.protective_set.stop_order.side == result.protective_set.target_order.side == exit_side
    assert result.protective_set.oco_group.resolution_pending
    assert not result.protective_set.oco_group.exchange_submission_authorized


def test_pending_to_active_history_and_idempotent_activation():
    engine = ProtectiveOrderEngine(); created = engine.create(**protective_inputs())
    active = engine.activate(protective_set=created.protective_set, activation_time=25, history=created.history)
    assert active.protective_set.stop_order.state == active.protective_set.target_order.state == OrderState.ACTIVE
    assert [row.state for row in active.history.transitions] == [OrderState.PENDING, OrderState.PENDING, OrderState.ACTIVE, OrderState.ACTIVE]
    replay = engine.activate(protective_set=created.protective_set, activation_time=25, history=active.history)
    assert replay.valid and replay.history == active.history


def test_create_replay_is_deterministic_and_idempotent():
    engine = ProtectiveOrderEngine(); values = protective_inputs()
    first = engine.create(**values)
    replay = engine.create(**values, history=first.history)
    assert replay.protective_set == first.protective_set and replay.history == first.history


def test_conflicting_set_for_same_setup_is_rejected():
    engine = ProtectiveOrderEngine(); values = protective_inputs(); first = engine.create(**values)
    conflict = dict(values); conflict["created_time"] = 25
    assert engine.create(**conflict, history=first.history).error.reason == "CONFLICTING_PROTECTIVE_ORDER_SET"


@pytest.mark.parametrize("field", ["qualification", "stop", "target", "entry_order", "fill", "sizing"])
def test_missing_inputs_fail_closed(field):
    values = protective_inputs(); values[field] = None
    assert ProtectiveOrderEngine().create(**values).error.reason == "REQUIRED_PROTECTIVE_INPUT_MISSING"


def test_identity_timeframe_and_chronology_mismatch():
    engine = ProtectiveOrderEngine(); values = protective_inputs()
    values["stop"] = replace(values["stop"], setup_id="other")
    assert engine.create(**values).error.reason == "PROTECTIVE_INPUT_IDENTITY_MISMATCH"
    values = protective_inputs(); values["sizing"] = replace(values["sizing"], timeframe="5m")
    assert engine.create(**values).error.reason == "TIMEFRAME_IDENTITY_MISMATCH"
    values = protective_inputs(); values["created_time"] = 22
    assert engine.create(**values).error.reason == "PROTECTIVE_ORDER_CHRONOLOGY_INVALID"


@pytest.mark.parametrize("direction,stop,target,reason,code", [
    (StructuralRegime.BULLISH, "101", "104", "LONG_STOP_GEOMETRY_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID),
    (StructuralRegime.BULLISH, "98", "99", "LONG_TARGET_GEOMETRY_INVALID", ProtectiveOrderErrorCode.TARGET_ORDER_INVALID),
    (StructuralRegime.BEARISH, "99", "96", "SHORT_STOP_GEOMETRY_INVALID", ProtectiveOrderErrorCode.PROTECTIVE_ORDER_INVALID),
    (StructuralRegime.BEARISH, "102", "101", "SHORT_TARGET_GEOMETRY_INVALID", ProtectiveOrderErrorCode.TARGET_ORDER_INVALID),
])
def test_directional_geometry(direction, stop, target, reason, code):
    values = protective_inputs(direction)
    values["stop"] = replace(values["stop"], stop_price=Decimal(stop))
    values["qualification"] = replace(values["qualification"], stop=Decimal(stop), target=Decimal(target))
    values["target"] = replace(values["target"], level=Decimal(target))
    values["sizing"] = replace(values["sizing"], stop_price=Decimal(stop))
    result = ProtectiveOrderEngine().create(**values)
    assert result.error.reason == reason and result.error.code == code


def test_tick_quantity_and_nonfinite_validation():
    engine = ProtectiveOrderEngine(); values = protective_inputs()
    values["target"] = replace(values["target"], level=Decimal("104.1")); values["qualification"] = replace(values["qualification"], target=Decimal("104.1"))
    assert engine.create(**values).error.reason == "PRICE_TICK_OR_QUANTITY_INVALID"
    values = protective_inputs(); values["sizing"] = replace(values["sizing"], proposed_quantity=Decimal("25.05"))
    assert engine.create(**values).error.reason == "QUANTITY_STEP_INVALID"
    values = protective_inputs(); values["target"] = replace(values["target"], level=Decimal("NaN")); values["qualification"] = replace(values["qualification"], target=Decimal("NaN"))
    assert engine.create(**values).error.reason == "NON_FINITE_PROTECTIVE_INPUT"


def test_inactive_target_and_unconfirmed_fill_fail_closed():
    engine = ProtectiveOrderEngine(); values = protective_inputs(); values["target"] = replace(values["target"], active=False, historical=True)
    assert engine.create(**values).error.code == ProtectiveOrderErrorCode.TARGET_ORDER_INVALID
    values = protective_inputs(); values["fill"] = replace(values["fill"], event="OTHER")
    assert engine.create(**values).error.reason == "ENTRY_FILL_NOT_CONFIRMED"


def test_records_are_immutable():
    result = ProtectiveOrderEngine().create(**protective_inputs())
    with pytest.raises(FrozenInstanceError):
        result.protective_set.stop_order.price = Decimal("97")
