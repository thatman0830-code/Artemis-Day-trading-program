from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import ContinuationSetupState, FinalSetupQualification, ReversalSetupState, SetupModel
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelection, EntryZoneSelectionState, EntryZoneType, FrozenEntryZoneCandidate
from strategy.trading_brain.p29_1_entry_execution import *


def inputs(model=SetupModel.CONTINUATION, direction=StructuralRegime.BULLISH):
    final = ContinuationSetupState.ARMED if model == SetupModel.CONTINUATION else ReversalSetupState.ENTRY_ZONE_ARMED
    phase = ContinuationSetupState.CANDIDATE if model == SetupModel.CONTINUATION else ReversalSetupState.MSS_CONFIRMED
    zone = FrozenEntryZoneCandidate("zone", EntryZoneType.FVG, "1m", direction, Decimal("99"), Decimal("101"), 10, Decimal("100"))
    selection = EntryZoneSelection("selection", "setup", "candidate", model, direction, EntryZoneSelectionState.SELECTED, 10, 10, (zone,), "zone", EntryZoneType.FVG, Decimal("99"), Decimal("101"), Decimal("100"), Decimal("100"), Decimal("0.5"), (), selection_time=10)
    qualification = FinalSetupQualification("qualification", "setup", "candidate", model, direction, phase, final, "selection", "stop", "target", Decimal("100"), Decimal("98"), Decimal("104"), Decimal("2"), Decimal("4"), Decimal("2"), Decimal("2"), True, True, 20)
    return qualification, selection, EntryExecutionContext("context", "BTC", "1m", Decimal("0.5"), ExecutionMode.PAPER, 20), PositionAvailability("slot", "BTC", 0, 20)


def lifecycle(model=SetupModel.CONTINUATION, direction=StructuralRegime.BULLISH):
    engine = EntryExecutionEngine(); q, s, c, a = inputs(model, direction)
    pending = engine.create_order(qualification=q, selection=s, context=c, position_availability=a, created_time=20)
    active = engine.activate_order(order=pending.order, activation_time=21, history=pending.history)
    return engine, (q, s, c, a), active


def bar(low="99.5", high="100.5", opened=21, closed=22, symbol="BTC", timeframe="1m"):
    return EntryCandle("bar", symbol, timeframe, opened, closed, Decimal("100.5"), Decimal(high), Decimal(low), Decimal("100"))


@pytest.mark.parametrize("model", [SetupModel.CONTINUATION, SetupModel.REVERSAL_1])
@pytest.mark.parametrize("direction,side", [(StructuralRegime.BULLISH, OrderSide.BUY), (StructuralRegime.BEARISH, OrderSide.SELL)])
def test_armed_models_fill_at_exact_frozen_eq(model, direction, side):
    engine, _, active = lifecycle(model, direction)
    result = engine.evaluate_candle(order=active.order, candle=bar(), history=active.history)
    assert (result.fill.fill_price, result.fill.side, result.order.state) == (Decimal("100"), side, OrderState.FILLED)


def test_no_touch_remains_active_and_unfilled():
    engine, _, active = lifecycle()
    untouched = EntryCandle("bar", "BTC", "1m", 21, 22, Decimal("101"), Decimal("102"), Decimal("101"), Decimal("101.5"))
    result = engine.evaluate_candle(order=active.order, candle=untouched, history=active.history)
    assert result.error.code == EntryExecutionErrorCode.ENTRY_NOT_FILLED
    assert len(result.history.evaluations) == 1 and result.order.state == OrderState.ACTIVE


def test_later_no_touch_prevents_retroactive_earlier_fill():
    engine, _, active = lifecycle()
    untouched = EntryCandle("later", "BTC", "1m", 23, 24, Decimal("101"), Decimal("102"), Decimal("101"), Decimal("101.5"))
    observed = engine.evaluate_candle(order=active.order, candle=untouched, history=active.history)
    earlier = bar(opened=22, closed=23)
    result = engine.evaluate_candle(order=active.order, candle=earlier, history=observed.history)
    assert result.error.reason == "CANDLE_DUPLICATE_OR_OUT_OF_ORDER"


def test_same_candle_cannot_retroactively_fill():
    engine, _, active = lifecycle()
    assert engine.evaluate_candle(order=active.order, candle=bar(opened=20), history=active.history).error.reason == "CANDLE_CHRONOLOGY_INVALID"


@pytest.mark.parametrize("kwargs", [{"symbol": "ETH"}, {"timeframe": "5m"}])
def test_candle_identity_mismatch(kwargs):
    engine, _, active = lifecycle()
    assert engine.evaluate_candle(order=active.order, candle=bar(**kwargs), history=active.history).error.reason == "CANDLE_IDENTITY_MISMATCH"


def test_nonarmed_missing_boundary_and_live_position_fail_closed():
    engine = EntryExecutionEngine(); q, s, c, a = inputs()
    rejected = replace(q, final_state=ContinuationSetupState.REJECTED, executable=False)
    assert engine.create_order(qualification=rejected, selection=s, context=c, position_availability=a, created_time=20).error.reason == "SETUP_NOT_CANONICALLY_ARMED"
    assert engine.create_order(qualification=q, selection=s, context=c, position_availability=None, created_time=20).error.reason == "POSITION_AVAILABILITY_NOT_CONFIRMED"
    assert engine.create_order(qualification=q, selection=s, context=c, position_availability=replace(a, open_position_count=1), created_time=20).error.reason == "LIVE_POSITION_ALREADY_EXISTS"


def test_tick_grid_and_frozen_identity_fail_closed():
    engine = EntryExecutionEngine(); q, s, c, a = inputs()
    assert engine.create_order(qualification=q, selection=s, context=replace(c, minimum_tick=Decimal("0.3")), position_availability=a, created_time=20).error.reason == "FROZEN_EQ_TICK_GRID_INVALID"
    assert engine.create_order(qualification=replace(q, entry=Decimal("100.5")), selection=s, context=c, position_availability=a, created_time=20).error.reason == "FROZEN_INPUT_IDENTITY_MISMATCH"


def test_duplicate_order_and_fill_are_prevented():
    engine, values, active = lifecycle(); q, s, c, a = values
    assert engine.create_order(qualification=q, selection=s, context=c, position_availability=a, created_time=22, history=active.history).error.reason == "DUPLICATE_ENTRY_ORDER"
    filled = engine.evaluate_candle(order=active.order, candle=bar(), history=active.history)
    assert engine.evaluate_candle(order=active.order, candle=bar(), history=filled.history).error.reason == "ORDER_NOT_ACTIVE_OR_NOT_LATEST"
    assert len(filled.history.fills) == 1


def test_invalidation_cancels_and_prevents_fill():
    engine, _, active = lifecycle()
    cancelled = engine.cancel_order(order=active.order, invalidation_time=22, history=active.history)
    assert cancelled.order.state == OrderState.CANCELLED
    assert engine.evaluate_candle(order=cancelled.order, candle=bar(opened=22, closed=23), history=cancelled.history).error.code == EntryExecutionErrorCode.ENTRY_INVALID


def test_history_and_fill_are_immutable():
    engine, _, active = lifecycle()
    filled = engine.evaluate_candle(order=active.order, candle=bar(), history=active.history)
    assert [row.state for row in filled.history.orders] == [OrderState.PENDING, OrderState.ACTIVE, OrderState.FILLED]
    with pytest.raises(FrozenInstanceError):
        filled.fill.fill_price = Decimal("99")


def test_candle_prices_require_tick_grid():
    engine, _, active = lifecycle()
    assert engine.evaluate_candle(order=active.order, candle=bar(low="99.4"), history=active.history).error.reason == "CANDLE_GEOMETRY_OR_TICK_GRID_INVALID"
