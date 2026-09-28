from decimal import Decimal

import pandas as pd

from strategy.trading_brain.p19_mechanical_swings import (
    MechanicalSwingEngine, MechanicalSwingType,
)


def candles(highs, lows, *, closed=True):
    return pd.DataFrame({
        "t": [1_000 * (i + 1) for i in range(len(highs))],
        "h": highs, "l": lows, "is_closed": [closed] * len(highs),
    })


def detect(frame, timeframe="15m"):
    return MechanicalSwingEngine().detect(timeframe=timeframe, candles=frame)


def test_strict_high_has_canonical_shape_and_opaque_identity():
    swing = detect(candles([10, 11, 15, 12, 11], [7, 8, 9, 8, 7])).highs[0]
    assert swing.type == MechanicalSwingType.H
    assert swing.price == Decimal("15") and swing.pivot_time == 3_000
    assert swing.confirmed is True and len(swing.id) == 36
    assert "15m" not in swing.id


def test_strict_low():
    result = detect(candles([14, 13, 12, 13, 14], [10, 9, 5, 8, 9]))
    assert len(result.lows) == 1 and result.lows[0].price == Decimal("5")


def test_equal_high_and_equal_low_do_not_qualify():
    assert detect(candles([10, 11, 15, 15, 11], [8, 7, 5, 5, 8])).swings == ()


def test_two_right_closed_candles_are_required_without_lookahead():
    assert detect(candles([10, 11, 15, 12], [7, 8, 9, 8])).swings == ()


def test_open_candle_input_fails_closed():
    frame = candles([10, 11, 15, 12, 11], [7, 8, 9, 8, 7])
    frame.loc[4, "is_closed"] = False
    try:
        detect(frame)
    except ValueError as error:
        assert "closed candles only" in str(error)
        return
    raise AssertionError("Expected open-candle input to fail")


def test_results_are_immutable_and_stable_across_repeated_evaluation():
    frame = candles([10, 11, 15, 12, 11], [7, 8, 9, 8, 7])
    assert detect(frame) == detect(frame.copy())


def test_timeframes_are_isolated_and_change_identity():
    frame = candles([10, 11, 15, 12, 11], [7, 8, 9, 8, 7])
    fifteen, hourly = detect(frame, "15m"), detect(frame, "1h")
    assert fifteen.highs[0].id != hourly.highs[0].id


def test_invalid_timestamp_order_is_rejected():
    frame = candles([10, 11, 15, 12, 11], [7, 8, 9, 8, 7])
    frame.loc[3, "t"] = frame.loc[1, "t"]
    try:
        detect(frame)
    except ValueError as error:
        assert "unique and increasing" in str(error)
        return
    raise AssertionError("Expected invalid timestamp order to fail")


def test_tb_19_dual_001_creates_two_independent_records():
    result = detect(candles([10, 11, 20, 12, 11], [8, 7, 1, 6, 7]))
    assert len(result.swings) == 2
    assert {s.type for s in result.swings} == {MechanicalSwingType.H, MechanicalSwingType.L}
    assert result.swings[0].pivot_time == result.swings[1].pivot_time == 3_000
    assert result.swings[0].id != result.swings[1].id


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #19 TESTS PASSED ({len(tests)} cases)")
