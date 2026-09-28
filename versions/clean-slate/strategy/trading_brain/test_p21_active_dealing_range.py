from dataclasses import replace
from decimal import Decimal

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)
from strategy.trading_brain.p21_active_dealing_range import ActiveDealingRangeEngine


def structural(id_, type_, price, protected=False):
    return StructuralSwing(
        id=id_, mechanical_swing_id=f"m-{id_}", timeframe="15m", type=type_,
        classification=StructuralClassification.UNCLASSIFIED,
        price=Decimal(str(price)), pivot_time=1, protected=protected, regime_ref="state",
    )


def state(regime, *, high=110, low=100, protected_high=108, protected_low=102):
    return StructuralStateSnapshot(
        id=f"state-{regime.value}", timeframe="15m", regime=regime,
        governing_high=structural("gh", MechanicalSwingType.H, high),
        governing_low=structural("gl", MechanicalSwingType.L, low),
        protected_high=structural("ph", MechanicalSwingType.H, protected_high, True),
        protected_low=structural("pl", MechanicalSwingType.L, protected_low, True),
        as_of_timestamp=10_000,
    )


def update(snapshot, previous=None, event="event-1"):
    return ActiveDealingRangeEngine().update(
        state_after=snapshot, accepted_structural_event_id=event,
        processing_timestamp=10_001, previous_active_range=previous,
    )


def test_bullish_range_uses_protected_low_to_governing_high_wicks():
    result = update(state(StructuralRegime.BULLISH))
    assert result.active_range.lower_boundary == Decimal("102")
    assert result.active_range.upper_boundary == Decimal("110")
    assert result.active_range.defining_low_swing_id == "pl"
    assert result.active_range.defining_high_swing_id == "gh"


def test_bearish_range_uses_governing_low_to_protected_high_wicks():
    result = update(state(StructuralRegime.BEARISH))
    assert result.active_range.lower_boundary == Decimal("100")
    assert result.active_range.upper_boundary == Decimal("108")
    assert result.active_range.defining_low_swing_id == "gl"
    assert result.active_range.defining_high_swing_id == "ph"


def test_initializing_has_no_range():
    assert update(state(StructuralRegime.INITIALIZING)).active_range is None


def test_missing_boundary_is_not_an_error():
    snapshot = replace(state(StructuralRegime.BULLISH), protected_low=None)
    result = update(snapshot)
    assert result.active_range is None and result.error is None


def test_invalid_equal_or_inverted_geometry_is_blocking_and_not_repaired():
    for protected_low in (110, 111):
        result = update(state(StructuralRegime.BULLISH, protected_low=protected_low))
        assert result.active_range is None
        assert result.error.error_code == "ACTIVE_RANGE_INVALID"
        assert result.error.severity == "BLOCKING"


def test_unaccepted_event_or_ordinary_candle_cannot_update_range():
    first = update(state(StructuralRegime.BULLISH)).active_range
    changed = state(StructuralRegime.BULLISH, high=115)
    result = update(changed, previous=first, event=None)
    assert result.active_range is first and result.terminated_range is None


def test_same_pair_does_not_create_replacement():
    snapshot = state(StructuralRegime.BULLISH)
    first = update(snapshot).active_range
    result = update(snapshot, previous=first, event="event-2")
    assert result.active_range.id == first.id and result.terminated_range is None


def test_new_finalized_pair_creates_new_id_and_historical_predecessor():
    first = update(state(StructuralRegime.BULLISH)).active_range
    replacement_state = state(StructuralRegime.BULLISH, high=115, protected_low=104)
    replacement_state = replace(
        replacement_state,
        governing_high=replace(replacement_state.governing_high, id="gh-2"),
        protected_low=replace(replacement_state.protected_low, id="pl-2"),
    )
    result = update(replacement_state, previous=first, event="event-2")
    assert result.active_range.id != first.id
    assert result.active_range.predecessor_range_id == first.id
    assert result.terminated_range.historical is True
    assert result.terminated_range.successor_range_id == result.active_range.id


def test_transition_terminates_active_range_without_opposing_replacement():
    first = update(state(StructuralRegime.BULLISH)).active_range
    result = update(state(StructuralRegime.TRANSITION), previous=first, event="mss")
    assert result.active_range is None
    assert result.terminated_range.terminated_by_event_id == "mss"
    assert result.terminated_range.successor_range_id is None


def test_timeframe_mismatch_fails_closed():
    snapshot = state(StructuralRegime.BULLISH)
    invalid_high = replace(snapshot.governing_high, timeframe="1h")
    try:
        update(replace(snapshot, governing_high=invalid_high))
    except ValueError as error:
        assert "timeframe-isolated" in str(error)
        return
    raise AssertionError("Expected timeframe mismatch")


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #21 TESTS PASSED ({len(tests)} cases)")
