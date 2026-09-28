from decimal import Decimal

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakQualifier, StructuralClassification, StructuralEventType,
    StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)


def structural(id_, type_, price, timeframe="15m"):
    return StructuralSwing(
        id=id_, mechanical_swing_id=f"m-{id_}", timeframe=timeframe,
        type=type_, classification=StructuralClassification.UNCLASSIFIED,
        price=Decimal(str(price)), pivot_time=1, protected=False, regime_ref=None,
    )


def state(regime, *, high=110, low=100, protected_high=108, protected_low=102):
    return StructuralStateSnapshot(
        id=f"state-{regime.value}", timeframe="15m", regime=regime,
        governing_high=structural("gh", MechanicalSwingType.H, high),
        governing_low=structural("gl", MechanicalSwingType.L, low),
        protected_high=structural("ph", MechanicalSwingType.H, protected_high),
        protected_low=structural("pl", MechanicalSwingType.L, protected_low),
    )


def candle(close, *, high=None, low=None, closed=True):
    return {
        "t": 10_000, "h": high if high is not None else close + 1,
        "l": low if low is not None else close - 1, "c": close,
        "is_closed": closed,
    }


def qualify(snapshot, close, *, displacement=True, **geometry):
    return StructuralBreakQualifier().qualify(
        state_before=snapshot, candle=candle(close, **geometry),
        qualifying_displacement=displacement,
    )


def test_initializing_bullish_body_close_qualifies_bos():
    events = qualify(state(StructuralRegime.INITIALIZING), 111)
    assert len(events) == 1
    assert events[0].event_type == StructuralEventType.BOS
    assert events[0].direction == StructuralRegime.BULLISH
    assert events[0].state_before_id == "state-INITIALIZING"


def test_initializing_bearish_body_close_qualifies_bos():
    event = qualify(state(StructuralRegime.INITIALIZING), 99)[0]
    assert event.event_type == StructuralEventType.BOS
    assert event.direction == StructuralRegime.BEARISH


def test_equality_and_wick_only_never_qualify():
    snapshot = state(StructuralRegime.INITIALIZING)
    assert qualify(snapshot, 110, high=115, low=109) == ()
    assert qualify(snapshot, 100, high=101, low=95) == ()


def test_displacement_is_required_for_structural_candidate():
    assert qualify(state(StructuralRegime.BULLISH), 111, displacement=False) == ()


def test_bullish_continuation_bos_uses_governing_high():
    event = qualify(state(StructuralRegime.BULLISH), 111)[0]
    assert event.event_type == StructuralEventType.BOS
    assert event.direction == StructuralRegime.BULLISH
    assert event.reference_swing_id == "gh"


def test_bullish_protected_low_break_is_bearish_mss():
    event = qualify(state(StructuralRegime.BULLISH), 101)[0]
    assert event.event_type == StructuralEventType.MSS
    assert event.direction == StructuralRegime.BEARISH
    assert event.reference_swing_id == "pl"


def test_bearish_continuation_and_mss_are_symmetric():
    snapshot = state(StructuralRegime.BEARISH)
    bearish = qualify(snapshot, 99)[0]
    bullish = qualify(snapshot, 109)[0]
    assert (bearish.event_type, bearish.direction) == (
        StructuralEventType.BOS, StructuralRegime.BEARISH,
    )
    assert (bullish.event_type, bullish.direction) == (
        StructuralEventType.MSS, StructuralRegime.BULLISH,
    )


def test_transition_does_not_invent_a_directional_candidate():
    assert qualify(state(StructuralRegime.TRANSITION), 111) == ()


def test_open_candle_and_invalid_geometry_fail_closed():
    snapshot = state(StructuralRegime.BULLISH)
    try:
        qualify(snapshot, 111, closed=False)
    except ValueError as error:
        assert "closed candle" in str(error)
    else:
        raise AssertionError("Expected open candle to fail")
    try:
        qualify(snapshot, 111, high=110, low=109)
    except ValueError as error:
        assert "geometry" in str(error)
        return
    raise AssertionError("Expected invalid geometry to fail")


def test_state_references_are_timeframe_isolated():
    snapshot = state(StructuralRegime.BULLISH)
    invalid = StructuralStateSnapshot(
        id=snapshot.id, timeframe=snapshot.timeframe, regime=snapshot.regime,
        governing_high=structural("gh", MechanicalSwingType.H, 110, "1h"),
        governing_low=snapshot.governing_low, protected_high=snapshot.protected_high,
        protected_low=snapshot.protected_low,
    )
    try:
        qualify(invalid, 111)
    except ValueError as error:
        assert "one timeframe" in str(error)
        return
    raise AssertionError("Expected mixed-timeframe state to fail")


def test_qualification_is_stable_and_does_not_mutate_frozen_state():
    snapshot = state(StructuralRegime.BULLISH)
    before = repr(snapshot)
    first = qualify(snapshot, 111)
    second = qualify(snapshot, 111)
    assert first == second and repr(snapshot) == before


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #20 PHASE B TESTS PASSED ({len(tests)} cases)")
