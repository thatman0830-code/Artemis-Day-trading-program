from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_1_entry_execution import EntryExecutionEngine
from strategy.trading_brain.p29_3_protective_orders import ProtectiveOrderEngine
from strategy.trading_brain.p29_4_exit_resolution import ExitReason, ExitResolutionEngine
from strategy.trading_brain.p29_6_position_lifecycle import *
from strategy.trading_brain.test_p29_3_protective_orders import protective_inputs
from strategy.trading_brain.test_p29_4_exit_resolution import candle


def open_inputs(direction=StructuralRegime.BULLISH, model=SetupModel.CONTINUATION):
    values = protective_inputs(direction, model)
    engine = ProtectiveOrderEngine(); created = engine.create(**values)
    active = engine.activate(protective_set=created.protective_set, activation_time=25, history=created.history)
    return dict(entry_order=values["entry_order"], fill=values["fill"], sizing=values["sizing"], protective_set=active.protective_set, protective_history=active.history)


def opened(direction=StructuralRegime.BULLISH, model=SetupModel.CONTINUATION):
    engine=PositionLifecycleEngine(); result=engine.open(**open_inputs(direction, model))
    return engine, result


def resolved(engine, opened_result, target=True):
    position=opened_result.position; values=open_inputs(position.direction, position.model)
    market = candle(high="104") if position.direction == StructuralRegime.BULLISH and target else candle(low="98")
    if position.direction == StructuralRegime.BEARISH:
        market = candle(low="96") if target else candle(high="102")
    exit_result=ExitResolutionEngine().evaluate(protective_set=values["protective_set"], protective_history=values["protective_history"], position=engine.open_boundary(position), market=market)
    return exit_result


def test_availability_bootstrap_before_entry_and_after_open():
    engine=PositionLifecycleEngine(); empty=PositionLifecycleHistory()
    before=engine.availability(symbol="BTC", checked_time=20, history=empty)
    assert before.confirmed and before.open_position_count == 0
    result=engine.open(**open_inputs(), history=empty)
    after=engine.availability(symbol="ETH", checked_time=25, history=result.history)
    assert after.confirmed and after.open_position_count == 1


@pytest.mark.parametrize("direction,model,stop,target", [
    (StructuralRegime.BULLISH, SetupModel.CONTINUATION, Decimal("98"), Decimal("104")),
    (StructuralRegime.BEARISH, SetupModel.CONTINUATION, Decimal("102"), Decimal("96")),
    (StructuralRegime.BULLISH, SetupModel.REVERSAL_1, Decimal("98"), Decimal("104")),
])
def test_position_opens_once_with_exact_frozen_facts(direction, model, stop, target):
    _, result=opened(direction, model); position=result.position
    assert position.state == PositionState.OPEN
    assert position.entry_price == Decimal("100") and position.quantity == Decimal("25")
    assert position.stop_price == stop and position.target_price == target
    assert position.opened_time == 22


@pytest.mark.parametrize("direction,target,reason", [
    (StructuralRegime.BULLISH, False, ExitReason.STOP_LOSS),
    (StructuralRegime.BULLISH, True, ExitReason.TARGET),
    (StructuralRegime.BEARISH, False, ExitReason.STOP_LOSS),
    (StructuralRegime.BEARISH, True, ExitReason.TARGET),
])
def test_stop_and_target_closure_preserves_exit(direction, target, reason):
    engine, result=opened(direction); exit_result=resolved(engine, result, target)
    closed=engine.close(position=result.position, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=result.history)
    assert closed.position.state == PositionState.CLOSED
    assert closed.position.exit_reason == reason
    assert closed.position.exit_price == exit_result.resolution.exit_price
    assert closed.position.winning_protective_order_id == exit_result.resolution.winning_order_id


def test_open_and_close_replays_are_idempotent():
    engine=PositionLifecycleEngine(); values=open_inputs(); first=engine.open(**values)
    replay=engine.open(**values, history=first.history)
    assert replay.position == first.position and replay.history == first.history
    exit_result=resolved(engine, first); closed=engine.close(position=first.position, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=first.history)
    replay_close=engine.close(position=closed.position, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=closed.history)
    assert replay_close.position == closed.position and replay_close.history == closed.history


def test_overlapping_position_and_conflicting_fill_rejected():
    engine, first=opened(); second=open_inputs(StructuralRegime.BEARISH)
    second["fill"] = replace(second["fill"], id="second-fill")
    assert engine.open(**second, history=first.history).error.reason == "OVERLAPPING_POSITION_PROHIBITED"
    conflict=open_inputs(); conflict["sizing"]=replace(conflict["sizing"], id="other")
    assert engine.open(**conflict, history=first.history).error.reason == "CONFLICTING_POSITION_CREATION"


def test_closed_position_finality_and_no_reopen():
    engine, first=opened(); exit_result=resolved(engine, first)
    closed=engine.close(position=first.position, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=first.history)
    assert engine.close(position=closed.position, exit_execution=replace(exit_result.resolution, id="other"), exit_history=exit_result.history, history=closed.history).error.reason == "CLOSED_POSITION_FINAL"
    assert engine.open(**open_inputs(), history=closed.history).position.state == PositionState.CLOSED


@pytest.mark.parametrize("field", ["entry_order", "fill", "sizing", "protective_set", "protective_history"])
def test_missing_open_inputs_fail_closed(field):
    values=open_inputs(); values[field]=None
    assert PositionLifecycleEngine().open(**values).error.reason == "REQUIRED_POSITION_OPEN_INPUT_MISSING"


def test_invalid_fill_identity_quantity_and_protection_fail_closed():
    engine=PositionLifecycleEngine(); values=open_inputs(); values["fill"]=replace(values["fill"], event="OTHER")
    assert engine.open(**values).error.reason == "ENTRY_FILL_NOT_CONFIRMED"
    values=open_inputs(); values["sizing"]=replace(values["sizing"], proposed_quantity=Decimal("24"))
    assert engine.open(**values).error.reason == "POSITION_PRICE_OR_QUANTITY_MISMATCH"
    values=open_inputs(); values["protective_set"]=replace(values["protective_set"], setup_id="other")
    assert engine.open(**values).error.reason == "POSITION_OPEN_IDENTITY_MISMATCH"


def test_close_unopened_missing_exit_and_identity_mismatch():
    engine, first=opened(); exit_result=resolved(engine, first)
    not_open=replace(first.position, state=PositionState.NOT_OPEN)
    assert engine.close(position=not_open, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=first.history).error.reason == "POSITION_NOT_LATEST_SNAPSHOT"
    assert engine.close(position=first.position, exit_execution=None, exit_history=None, history=first.history).error.reason == "RESOLVED_EXIT_REQUIRED"
    bad=replace(exit_result.resolution, setup_id="other")
    bad_history=replace(exit_result.history, resolutions=(bad,))
    assert engine.close(position=first.position, exit_execution=bad, exit_history=bad_history, history=first.history).error.reason == "POSITION_EXIT_IDENTITY_MISMATCH"


def test_stale_availability_fails_closed_and_boundary_is_29_1_compatible():
    engine, result=opened()
    stale=engine.availability(symbol="BTC", checked_time=21, history=result.history)
    assert not stale.confirmed
    values=protective_inputs(); q=values["qualification"]; selection_inputs=__import__('strategy.trading_brain.test_p29_1_entry_execution', fromlist=['inputs']).inputs()
    q2, selection, context, _ = selection_inputs
    attempted=EntryExecutionEngine().create_order(qualification=q2, selection=selection, context=context, position_availability=engine.availability(symbol="BTC", checked_time=25, history=result.history), created_time=25)
    assert attempted.error.reason == "LIVE_POSITION_ALREADY_EXISTS"


def test_snapshots_are_immutable_and_history_append_only():
    engine, first=opened(); exit_result=resolved(engine, first)
    closed=engine.close(position=first.position, exit_execution=exit_result.resolution, exit_history=exit_result.history, history=first.history)
    assert [x.state for x in closed.history.snapshots] == [PositionState.OPEN, PositionState.CLOSED]
    with pytest.raises(FrozenInstanceError):
        closed.position.exit_price = Decimal("0")
