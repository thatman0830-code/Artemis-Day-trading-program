from dataclasses import replace
from decimal import Decimal

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p22_ote import OTEEngine


def range_(id_="range-1", regime=StructuralRegime.BULLISH, low="100", high="110"):
    return StructuralRange(
        id=id_, timeframe="15m", upper_boundary=Decimal(high), lower_boundary=Decimal(low),
        defining_high_swing_id="high", defining_low_swing_id="low",
        defining_high_price=Decimal(high), defining_low_price=Decimal(low),
        regime=regime, creation_time=10_000, confirmation_time=9_999,
        active=True, historical=False, created_by_event_id=f"event-{id_}",
    )


def test_bullish_ote_is_discount_side_deep_retracement():
    ote = OTEEngine().create(active_range=range_())
    assert ote.eq_50_price == Decimal("105.00")
    assert ote.ote_79_price == Decimal("102.10")
    assert (ote.zone_low, ote.zone_high) == (Decimal("102.10"), Decimal("105.00"))


def test_bearish_ote_is_premium_side_deep_retracement():
    ote = OTEEngine().create(active_range=range_(regime=StructuralRegime.BEARISH))
    assert ote.eq_50_price == Decimal("105.00")
    assert ote.ote_79_price == Decimal("107.90")
    assert (ote.zone_low, ote.zone_high) == (Decimal("105.00"), Decimal("107.90"))


def test_zone_boundaries_are_inclusive():
    ote = OTEEngine().create(active_range=range_())
    assert ote.contains(ote.zone_low) and ote.contains(ote.zone_high)
    assert not ote.contains(ote.zone_low - Decimal("0.01"))


def test_ote_consumes_exact_range_anchors_and_identity():
    source = range_()
    first = OTEEngine().create(active_range=source)
    second = OTEEngine().create(active_range=source)
    assert first == second
    assert first.range_id == source.id
    assert first.anchor_high == source.upper_boundary
    assert first.anchor_low == source.lower_boundary


def test_same_active_range_does_not_recalculate_or_replace_ote():
    source = range_()
    first = OTEEngine().create(active_range=source)
    result = OTEEngine().update(active_range=source, previous_active_ote=first)
    assert result.active_ote is first and result.terminated_ote is None


def test_range_replacement_creates_new_ote_and_terminates_old():
    engine = OTEEngine()
    first_range = range_()
    first = engine.create(active_range=first_range)
    second_range = range_(id_="range-2", low="104", high="115")
    result = engine.update(active_range=second_range, previous_active_ote=first)
    assert result.active_ote.id != first.id
    assert result.active_ote.range_id == "range-2"
    assert result.terminated_ote.historical is True
    assert result.terminated_ote.terminated_by_event_id == "event-range-2"


def test_mss_or_transition_terminates_active_ote():
    first = OTEEngine().create(active_range=range_())
    result = OTEEngine().update(
        active_range=None, previous_active_ote=first, termination_event_id="mss",
    )
    assert result.active_ote is None
    assert result.terminated_ote.terminated_by_event_id == "mss"


def test_no_active_range_means_no_ote_without_error():
    result = OTEEngine().update(active_range=None)
    assert result.active_ote is None and result.terminated_ote is None


def test_inactive_or_invalid_range_fails_closed():
    engine = OTEEngine()
    for invalid in (
        replace(range_(), active=False, historical=True),
        replace(range_(), upper_boundary=Decimal("100")),
    ):
        try:
            engine.create(active_range=invalid)
        except ValueError:
            continue
        raise AssertionError("Expected invalid range to fail")


def test_price_traversal_does_not_mutate_geometry():
    ote = OTEEngine().create(active_range=range_())
    before = repr(ote)
    assert ote.contains(Decimal("103"))
    assert repr(ote) == before and ote.active is True


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #22 TESTS PASSED ({len(tests)} cases)")
