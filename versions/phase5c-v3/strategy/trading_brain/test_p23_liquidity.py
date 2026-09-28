from dataclasses import replace
from decimal import Decimal

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionEngine, LiquidityPoolEngine, LiquidityReference,
    LiquiditySide, LiquidityState,
)


def active_range():
    return StructuralRange(
        id="range", timeframe="15m", upper_boundary=Decimal("110"),
        lower_boundary=Decimal("100"), defining_high_swing_id="h",
        defining_low_swing_id="l", defining_high_price=Decimal("110"),
        defining_low_price=Decimal("100"), regime=StructuralRegime.BULLISH,
        creation_time=1, confirmation_time=1, active=True, historical=False,
        created_by_event_id="bos",
    )


def ref(id_, price, side=LiquiditySide.BSL, *, time=1, major=False, timeframe="15m"):
    return LiquidityReference(
        id=id_, timeframe=timeframe, side=side, price=Decimal(str(price)),
        confirmation_time=time, source_type="MECHANICAL_SWING", major_reference=major,
    )


def pool(side=LiquiditySide.BSL, prices=("105.00", "105.25")):
    references = tuple(ref(f"r{i}", price, side, time=i) for i, price in enumerate(prices, 1))
    return LiquidityPoolEngine(minimum_tick=Decimal("0.25")).build_inventory(
        references=references, active_range=active_range(),
    ).pools[0]


def candle(high, low, close):
    return {"t": 10, "h": high, "l": low, "c": close, "is_closed": True}


def test_pool_requires_two_qualifying_references():
    inventory = LiquidityPoolEngine(minimum_tick=Decimal("0.25")).build_inventory(
        references=(ref("one", "105"),), active_range=active_range(),
    )
    assert inventory.pools == () and len(inventory.single_references) == 1


def test_one_tick_equality_creates_pool_but_wider_does_not():
    engine = LiquidityPoolEngine(minimum_tick=Decimal("0.25"))
    inventory = engine.build_inventory(
        references=(ref("a", "105"), ref("b", "105.25"), ref("c", "106")),
        active_range=active_range(),
    )
    assert len(inventory.pools) == 1
    assert [r.id for r in inventory.single_references] == ["c"]


def test_consolidated_mean_is_tick_normalized_half_up_and_components_retained():
    engine = LiquidityPoolEngine(minimum_tick=Decimal("0.25"))
    inventory = engine.build_inventory(
        references=(ref("a", "5000"), ref("b", "5000.25"), ref("c", "5000")),
        active_range=None,
    )
    result = inventory.pools[0]
    assert result.consolidated_level == Decimal("5000.00")
    assert result.component_prices == (Decimal("5000"), Decimal("5000"), Decimal("5000.25"))
    assert result.component_source_types == (
        "MECHANICAL_SWING", "MECHANICAL_SWING", "MECHANICAL_SWING",
    )
    assert result.touch_count == 3


def test_internal_external_and_boundary_classification():
    engine = LiquidityPoolEngine(minimum_tick=Decimal("0.25"))
    internal = engine.build_inventory(
        references=(ref("a", "105"), ref("b", "105")), active_range=active_range(),
    ).pools[0]
    boundary = engine.build_inventory(
        references=(ref("c", "110"), ref("d", "110")), active_range=active_range(),
    ).pools[0]
    major = engine.build_inventory(
        references=(ref("e", "105", major=True), ref("f", "105")), active_range=active_range(),
    ).pools[0]
    assert internal.external is False
    assert boundary.external is True and major.external is True


def test_touch_or_approach_is_not_sweep_and_stays_active():
    source = pool()
    result = LiquidityInteractionEngine.evaluate(
        pool=source, candle=candle("105.00", "104", "104.5"), event_timeframe="1m",
    )
    assert result.pool.state == LiquidityState.ACTIVE and result.event is None


def test_bsl_sweep_requires_strict_penetration_and_close_back():
    result = LiquidityInteractionEngine.evaluate(
        pool=pool(), candle=candle("106", "104", "104.5"), event_timeframe="1m",
    )
    assert result.event.outcome == LiquidityState.SWEPT
    assert result.pool.state == LiquidityState.CONSUMED
    assert result.event.penetration == Decimal("0.75")


def test_lsl_sweep_is_symmetric():
    result = LiquidityInteractionEngine.evaluate(
        pool=pool(LiquiditySide.LSL),
        candle=candle("106", "104", "106"), event_timeframe="1m",
    )
    assert result.event.outcome == LiquidityState.SWEPT
    assert result.event.side == LiquiditySide.LSL


def test_penetration_and_close_beyond_is_broken_consumed():
    result = LiquidityInteractionEngine.evaluate(
        pool=pool(), candle=candle("106", "104", "105.5"), event_timeframe="15m",
    )
    assert result.event.outcome == LiquidityState.BROKEN
    assert result.event.final_state == LiquidityState.CONSUMED


def test_close_exactly_at_level_records_violation_not_sweep_or_break():
    source = pool()
    result = LiquidityInteractionEngine.evaluate(
        pool=source,
        candle=candle("106", "104", source.consolidated_level),
        event_timeframe="15m",
    )
    assert result.pool.state == LiquidityState.VIOLATED and result.event is None


def test_no_maximum_penetration_and_deepest_is_recorded():
    result = LiquidityInteractionEngine.evaluate(
        pool=pool(), candle=candle("1000", "1", "100"), event_timeframe="1m",
    )
    assert result.event.outcome == LiquidityState.SWEPT
    assert result.pool.deepest_penetration == Decimal("894.75")


def test_consumed_pool_cannot_generate_second_event():
    first = LiquidityInteractionEngine.evaluate(
        pool=pool(), candle=candle("106", "104", "104"), event_timeframe="1m",
    )
    second = LiquidityInteractionEngine.evaluate(
        pool=first.pool, candle=candle("107", "103", "104"), event_timeframe="1m",
    )
    assert second.event is None and second.pool is first.pool


def test_lower_timeframe_event_preserves_pool_timeframe_identity():
    result = LiquidityInteractionEngine.evaluate(
        pool=pool(), candle=candle("106", "104", "104"), event_timeframe="1m",
    )
    assert result.event.pool_timeframe == "15m"
    assert result.event.event_timeframe == "1m"


def test_liquidity_event_does_not_mutate_range_or_structure():
    range_before = active_range()
    representation = repr(range_before)
    LiquidityInteractionEngine.evaluate(
        pool=pool(), candle=candle("106", "104", "104"), event_timeframe="1m",
    )
    assert repr(range_before) == representation and range_before.active is True


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #23 TESTS PASSED ({len(tests)} cases)")
