from dataclasses import FrozenInstanceError, replace
from decimal import Decimal
import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_1_entry_execution import OrderState
from strategy.trading_brain.p29_3_protective_orders import ProtectiveOrderEngine
from strategy.trading_brain.p29_4_exit_resolution import *
from strategy.trading_brain.test_p29_3_protective_orders import protective_inputs


def active_facts(direction=StructuralRegime.BULLISH, model=SetupModel.CONTINUATION):
    protective = ProtectiveOrderEngine(); created = protective.create(**protective_inputs(direction, model))
    active = protective.activate(protective_set=created.protective_set, activation_time=25, history=created.history)
    pset = active.protective_set
    position = OpenPositionBoundary("position", pset.setup_id, pset.oco_group.entry_fill_id, pset.id, "BTC", "1m", "v1", PositionState.OPEN, 25)
    return pset, active.history, position


def candle(id="bar", opened=25, closed=26, open="100", high="101", low="99", close="100", observations=()):
    return ExitMarketData(id, "BTC", "1m", opened, closed, Decimal(open), Decimal(high), Decimal(low), Decimal(close), "v1", observations)


@pytest.mark.parametrize("direction,market,price", [
    (StructuralRegime.BULLISH, candle(low="98", close="98.5"), Decimal("98")),
    (StructuralRegime.BEARISH, candle(high="102", close="101.5"), Decimal("102")),
])
def test_long_and_short_normal_stop(direction, market, price):
    pset, ph, position = active_facts(direction)
    result = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    assert result.resolution.exit_reason == ExitReason.STOP_LOSS
    assert result.resolution.exit_price == price
    assert result.stop_order.state == OrderState.FILLED
    assert result.target_order.state == OrderState.CANCELLED


@pytest.mark.parametrize("direction,market,price", [
    (StructuralRegime.BULLISH, candle(high="104", close="103"), Decimal("104")),
    (StructuralRegime.BEARISH, candle(low="96", close="97"), Decimal("96")),
])
def test_long_and_short_target(direction, market, price):
    pset, ph, position = active_facts(direction)
    result = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    assert result.resolution.exit_reason == ExitReason.TARGET
    assert result.resolution.exit_price == price
    assert result.target_order.state == OrderState.FILLED
    assert result.stop_order.state == OrderState.CANCELLED


def test_neither_touched_is_recorded_and_prevents_retroactive_change():
    pset, ph, position = active_facts(); engine = ExitResolutionEngine()
    none = engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=candle(id="later", opened=27, closed=28))
    assert none.resolution is None and none.error is None
    earlier = engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=candle(id="earlier", opened=26, closed=27, low="98"), history=none.history)
    assert earlier.error.reason == "MARKET_DATA_RETROACTIVE_OR_OUT_OF_ORDER"


@pytest.mark.parametrize("direction,market,stop", [
    (StructuralRegime.BULLISH, candle(open="100", high="104", low="98"), Decimal("98")),
    (StructuralRegime.BEARISH, candle(open="100", high="102", low="96"), Decimal("102")),
])
def test_same_candle_collision_uses_stop_priority(direction, market, stop):
    pset, ph, position = active_facts(direction)
    result = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    assert result.resolution.exit_reason == ExitReason.OHLC_AMBIGUOUS_STOP_PRIORITY
    assert result.resolution.exit_price == stop


@pytest.mark.parametrize("direction,market,price", [
    (StructuralRegime.BULLISH, candle(open="97", high="105", low="96", close="104"), Decimal("97")),
    (StructuralRegime.BEARISH, candle(open="103", high="104", low="95", close="96"), Decimal("103")),
])
def test_gap_stop_precedes_collision(direction, market, price):
    pset, ph, position = active_facts(direction)
    result = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    assert result.resolution.exit_reason == ExitReason.STOP_LOSS_GAP
    assert result.resolution.exit_price == price


@pytest.mark.parametrize("direction,market,target", [
    (StructuralRegime.BULLISH, candle(open="105", high="106", low="104", close="105"), Decimal("104")),
    (StructuralRegime.BEARISH, candle(open="95", high="96", low="94", close="95"), Decimal("96")),
])
def test_target_gap_never_improves_fill(direction, market, target):
    pset, ph, position = active_facts(direction)
    result = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    assert result.resolution.exit_reason == ExitReason.TARGET and result.resolution.exit_price == target


def test_finer_chronology_overrides_ohlc_stop_priority():
    pset, ph, position = active_facts()
    observations = (PriceObservation("p1", Decimal("104"), 25), PriceObservation("p2", Decimal("98"), 26))
    market = candle(high="104", low="98", observations=observations)
    result = ExitResolutionEngine().evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    assert result.resolution.exit_reason == ExitReason.TARGET
    assert result.resolution.exit_time == 25


def test_before_activation_and_non_active_sets_fail_closed():
    pset, ph, position = active_facts(); engine = ExitResolutionEngine()
    assert engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=candle(opened=24)).error.reason == "MARKET_DATA_CHRONOLOGY_INVALID"
    pending = replace(pset, stop_order=replace(pset.stop_order, state=OrderState.PENDING))
    assert engine.evaluate(protective_set=pending, protective_history=ph, position=position, market=candle()).error.reason == "PROTECTIVE_SET_NOT_ACTIVE"


@pytest.mark.parametrize("field", ["protective_set", "protective_history", "position", "market"])
def test_missing_inputs_fail_closed(field):
    pset, ph, position = active_facts(); values=dict(protective_set=pset, protective_history=ph, position=position, market=candle()); values[field]=None
    assert ExitResolutionEngine().evaluate(**values).error.reason == "REQUIRED_EXIT_INPUT_MISSING"


def test_identity_version_and_open_position_validation():
    pset, ph, position = active_facts(); engine=ExitResolutionEngine()
    assert engine.evaluate(protective_set=pset, protective_history=ph, position=replace(position, state=PositionState.CLOSED), market=candle()).error.reason == "OPEN_POSITION_NOT_CONFIRMED"
    assert engine.evaluate(protective_set=pset, protective_history=ph, position=replace(position, symbol="ETH"), market=candle()).error.reason == "SYMBOL_IDENTITY_MISMATCH"
    assert engine.evaluate(protective_set=pset, protective_history=ph, position=replace(position, input_version="v2"), market=candle()).error.reason == "INPUT_VERSION_MISMATCH"


def test_invalid_prices_and_tick_grid_fail_closed():
    pset, ph, position = active_facts(); engine=ExitResolutionEngine()
    assert engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=candle(open="NaN")).error.reason == "NON_FINITE_EXIT_INPUT"
    assert engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=candle(low="98.1")).error.reason == "EXIT_PRICE_GEOMETRY_OR_TICK_GRID_INVALID"


def test_terminal_replay_is_idempotent_and_conflicting_exit_prevented():
    pset, ph, position = active_facts(); engine=ExitResolutionEngine(); market=candle(low="98")
    first=engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=market)
    replay=engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=market, history=first.history)
    assert replay.resolution == first.resolution and replay.history == first.history
    conflict=engine.evaluate(protective_set=pset, protective_history=ph, position=position, market=candle(id="other", high="104"), history=first.history)
    assert conflict.error.reason == "PROTECTIVE_SET_ALREADY_RESOLVED"
    with pytest.raises(FrozenInstanceError):
        first.resolution.exit_price = Decimal("999")
