from dataclasses import FrozenInstanceError
from decimal import Decimal

import pytest

from strategy.trading_brain.p25_fvg_ifvg import (
    FVGDirection, FVGEngine, FVGState,
)


def candle(id_, t, high, low, close, *, displacement=False, closed=True):
    return {
        "id": id_, "t": t, "h": high, "l": low, "c": close,
        "is_closed": closed, "qualifying_displacement": displacement,
    }


def bullish_fvg():
    candles = (
        candle("c1", 1, "100", "99", "99.5"),
        candle("c2", 2, "102", "100", "101", displacement=True),
        candle("c3", 3, "103", "101", "102"),
    )
    return FVGEngine(minimum_tick=Decimal("0.25")).detect(
        timeframe="5m", candles=candles,
    )[0]


def bearish_fvg():
    candles = (
        candle("c1", 1, "101", "100", "100.5"),
        candle("c2", 2, "100", "98", "99", displacement=True),
        candle("c3", 3, "99", "97", "98"),
    )
    return FVGEngine(minimum_tick=Decimal("0.25")).detect(
        timeframe="5m", candles=candles,
    )[0]


def test_exact_bullish_three_candle_geometry_and_confirmation_time():
    result = bullish_fvg()
    assert result.direction == FVGDirection.BULLISH
    assert (result.lower_boundary, result.upper_boundary) == (
        Decimal("100"), Decimal("101"),
    )
    assert result.gap_size == Decimal("1")
    assert result.confirmation_time == 3 and result.displacement_qualified is True


def test_exact_bearish_three_candle_geometry():
    result = bearish_fvg()
    assert result.direction == FVGDirection.BEARISH
    assert (result.lower_boundary, result.upper_boundary) == (
        Decimal("99"), Decimal("100"),
    )


def test_equality_and_sub_tick_gap_do_not_create_fvg():
    engine = FVGEngine(minimum_tick=Decimal("0.25"))
    equality = (
        candle("a", 1, "100", "99", "99.5"),
        candle("b", 2, "101", "100", "100.5"),
        candle("c", 3, "102", "100", "101"),
    )
    sub_tick = (
        candle("d", 4, "100", "99", "99.5"),
        candle("e", 5, "101", "100", "100.5"),
        candle("f", 6, "102", "100.10", "101"),
    )
    assert engine.detect(timeframe="5m", candles=equality) == ()
    assert engine.detect(timeframe="5m", candles=sub_tick) == ()


def test_displacement_is_not_required_for_fvg_existence():
    candles = (
        candle("a", 1, "100", "99", "99.5"),
        candle("b", 2, "101", "100", "100.5"),
        candle("c", 3, "102", "101", "101.5"),
    )
    result = FVGEngine(minimum_tick=Decimal("0.25")).detect(
        timeframe="5m", candles=candles,
    )[0]
    assert result.displacement_qualified is False


def test_partial_mitigation_records_actual_deepest_penetration():
    engine = FVGEngine(minimum_tick=Decimal("0.25"))
    result = engine.interact(
        fvg=bullish_fvg(),
        candle=candle("i", 4, "102", "100.70", "101.5"),
        event_timeframe="1m",
    ).fvg
    assert result.state == FVGState.ACTIVE
    assert result.deepest_penetration == Decimal("0.30")
    assert result.fully_mitigated is False


def test_deepest_penetration_never_regresses():
    engine = FVGEngine(minimum_tick=Decimal("0.25"))
    first = engine.interact(
        fvg=bullish_fvg(), candle=candle("i1", 4, "102", "100.40", "101"),
        event_timeframe="1m",
    ).fvg
    second = engine.interact(
        fvg=first, candle=candle("i2", 5, "102", "100.80", "101"),
        event_timeframe="1m",
    ).fvg
    assert second.deepest_penetration == Decimal("0.60")


def test_wick_to_far_boundary_fully_mitigates_without_ifvg():
    result = FVGEngine(minimum_tick=Decimal("0.25")).interact(
        fvg=bullish_fvg(), candle=candle("i", 4, "102", "99.5", "101"),
        event_timeframe="1m", qualifying_opposing_displacement=True,
    )
    assert result.fvg.state == FVGState.MITIGATED
    assert result.fvg.fully_mitigated is True
    assert result.ifvg is None


def test_close_through_without_displacement_is_violated_not_inverted():
    result = FVGEngine(minimum_tick=Decimal("0.25")).interact(
        fvg=bullish_fvg(), candle=candle("i", 4, "101", "98", "99"),
        event_timeframe="1m",
    )
    assert result.fvg.state == FVGState.VIOLATED
    assert result.ifvg is None


def test_bullish_fvg_converts_once_to_bearish_ifvg():
    engine = FVGEngine(minimum_tick=Decimal("0.25"))
    first = engine.interact(
        fvg=bullish_fvg(), candle=candle("i", 4, "101", "98", "99"),
        event_timeframe="1m", qualifying_opposing_displacement=True,
    )
    second = engine.interact(
        fvg=first.fvg, candle=candle("j", 5, "102", "99", "101.5"),
        event_timeframe="1m", qualifying_opposing_displacement=True,
    )
    assert first.ifvg.direction == FVGDirection.BEARISH
    assert first.ifvg.source_fvg_id == first.fvg.id
    assert first.ifvg.lower_boundary == Decimal("100")
    assert first.fvg.state == FVGState.INVERTED and first.fvg.converted_once
    assert second.fvg is first.fvg and second.ifvg is None


def test_bearish_fvg_converts_symmetrically_to_bullish_ifvg():
    result = FVGEngine(minimum_tick=Decimal("0.25")).interact(
        fvg=bearish_fvg(), candle=candle("i", 4, "102", "99", "101"),
        event_timeframe="1m", qualifying_opposing_displacement=True,
    )
    assert result.ifvg.direction == FVGDirection.BULLISH
    assert (result.ifvg.lower_boundary, result.ifvg.upper_boundary) == (
        Decimal("99"), Decimal("100"),
    )


def test_equal_close_and_wick_only_never_convert():
    engine = FVGEngine(minimum_tick=Decimal("0.25"))
    equality = engine.interact(
        fvg=bullish_fvg(), candle=candle("i", 4, "101", "99", "100"),
        event_timeframe="1m", qualifying_opposing_displacement=True,
    )
    assert equality.ifvg is None and equality.fvg.state == FVGState.MITIGATED


def test_creation_candle_cannot_retroactively_convert_same_fvg():
    source = bullish_fvg()
    result = FVGEngine(minimum_tick=Decimal("0.25")).interact(
        fvg=source, candle=candle("c3", 3, "103", "98", "99"),
        event_timeframe="5m", qualifying_opposing_displacement=True,
    )
    assert result.fvg is source and result.ifvg is None


def test_lower_timeframe_interaction_preserves_originating_timeframe():
    result = FVGEngine(minimum_tick=Decimal("0.25")).interact(
        fvg=bullish_fvg(), candle=candle("i", 4, "102", "100.5", "101"),
        event_timeframe="1m",
    ).fvg
    assert result.timeframe == "5m"


def test_overlapping_fvgs_remain_distinct_objects():
    candles = (
        candle("c1", 1, "100", "99", "99.5"),
        candle("c2", 2, "101", "100", "100.5"),
        candle("c3", 3, "102", "101", "101.5"),
        candle("c4", 4, "103", "102", "102.5"),
    )
    results = FVGEngine(minimum_tick=Decimal("0.25")).detect(
        timeframe="5m", candles=candles,
    )
    assert len(results) == 2 and results[0].id != results[1].id


def test_detection_is_deterministic_and_historical_snapshots_are_immutable():
    first = bullish_fvg()
    second = bullish_fvg()
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.state = FVGState.MITIGATED


def test_invalid_inputs_fail_closed():
    with pytest.raises(ValueError, match="positive"):
        FVGEngine(minimum_tick=Decimal("0"))
    engine = FVGEngine(minimum_tick=Decimal("0.25"))
    with pytest.raises(ValueError, match="closed"):
        engine.detect(timeframe="5m", candles=(
            candle("a", 1, 2, 1, 1, closed=False),
            candle("b", 2, 3, 2, 2), candle("c", 3, 4, 3, 3),
        ))
    with pytest.raises(ValueError, match="unique and increasing"):
        engine.detect(timeframe="5m", candles=(
            candle("a", 2, 2, 1, 1), candle("b", 1, 3, 2, 2),
            candle("c", 3, 4, 3, 3),
        ))
