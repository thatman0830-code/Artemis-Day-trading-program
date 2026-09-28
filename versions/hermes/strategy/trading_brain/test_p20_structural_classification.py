from decimal import Decimal

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwing, MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralRegime, StructuralSwingSelector,
)


def swing(id_, type_, price, time, timeframe="15m", confirmed=True):
    return MechanicalSwing(
        id=id_, timeframe=timeframe, type=type_, price=Decimal(str(price)),
        pivot_time=time, confirmed=confirmed,
    )


def select(*items):
    return StructuralSwingSelector().select(swings=tuple(items))


def test_initial_opposite_pair_is_unclassified_baseline_and_initializing():
    result = select(swing("h1", MechanicalSwingType.H, 110, 1), swing("l1", MechanicalSwingType.L, 100, 2))
    assert [s.classification for s in result.swings] == [
        StructuralClassification.UNCLASSIFIED, StructuralClassification.UNCLASSIFIED,
    ]
    assert result.regime == StructuralRegime.INITIALIZING


def test_dominant_high_survives_same_leg():
    result = select(
        swing("h1", MechanicalSwingType.H, 110, 1),
        swing("h2", MechanicalSwingType.H, 112, 2),
        swing("h3", MechanicalSwingType.H, 111, 3),
        swing("l1", MechanicalSwingType.L, 100, 4),
    )
    assert [s.mechanical_swing_id for s in result.swings] == ["h2", "l1"]


def test_dominant_low_survives_same_leg():
    result = select(
        swing("l1", MechanicalSwingType.L, 100, 1),
        swing("l2", MechanicalSwingType.L, 98, 2),
        swing("l3", MechanicalSwingType.L, 99, 3),
        swing("h1", MechanicalSwingType.H, 110, 4),
    )
    assert [s.mechanical_swing_id for s in result.swings] == ["l2", "h1"]


def test_exact_same_type_classification_family():
    result = select(
        swing("h1", MechanicalSwingType.H, 110, 1), swing("l1", MechanicalSwingType.L, 100, 2),
        swing("h2", MechanicalSwingType.H, 112, 3), swing("l2", MechanicalSwingType.L, 102, 4),
        swing("h3", MechanicalSwingType.H, 109, 5), swing("l3", MechanicalSwingType.L, 99, 6),
        swing("h4", MechanicalSwingType.H, 109, 7), swing("l4", MechanicalSwingType.L, 99, 8),
    )
    assert [s.classification for s in result.highs] == [
        StructuralClassification.UNCLASSIFIED, StructuralClassification.HH,
        StructuralClassification.LH, StructuralClassification.EQUAL_HIGH,
    ]
    assert [s.classification for s in result.lows] == [
        StructuralClassification.UNCLASSIFIED, StructuralClassification.HL,
        StructuralClassification.LL, StructuralClassification.EQUAL_LOW,
    ]


def test_equal_competing_unfinalized_extreme_keeps_first_identity():
    result = select(
        swing("h-first", MechanicalSwingType.H, 110, 1),
        swing("h-later", MechanicalSwingType.H, 110, 2),
        swing("l1", MechanicalSwingType.L, 100, 3),
    )
    assert result.highs[0].mechanical_swing_id == "h-first"


def test_dual_pivot_records_are_both_consumed_without_exclusion():
    result = select(
        swing("h1", MechanicalSwingType.H, 110, 1),
        swing("l1", MechanicalSwingType.L, 90, 1),
    )
    assert {s.mechanical_swing_id for s in result.swings} == {"h1", "l1"}


def test_unconfirmed_input_fails_closed():
    try:
        select(swing("h1", MechanicalSwingType.H, 110, 1, confirmed=False))
    except ValueError as error:
        assert "confirmed" in str(error)
        return
    raise AssertionError("Expected unconfirmed input to fail")


def test_mixed_timeframes_fail_closed():
    try:
        select(
            swing("h1", MechanicalSwingType.H, 110, 1, timeframe="15m"),
            swing("l1", MechanicalSwingType.L, 100, 2, timeframe="1h"),
        )
    except ValueError as error:
        assert "timeframe-isolated" in str(error)
        return
    raise AssertionError("Expected mixed timeframes to fail")


def test_output_is_stable_and_immutable():
    items = (swing("h1", MechanicalSwingType.H, 110, 1), swing("l1", MechanicalSwingType.L, 100, 2))
    assert StructuralSwingSelector().select(swings=items) == StructuralSwingSelector().select(swings=items)


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #20 PHASE A TESTS PASSED ({len(tests)} cases)")
