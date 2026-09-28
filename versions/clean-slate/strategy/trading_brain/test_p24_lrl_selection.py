from dataclasses import replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p23_liquidity import LiquidityPool, LiquiditySide, LiquidityState
from strategy.trading_brain.p24_lrl_selection import (
    LRLRole, LRLSelectionEngine, LRLTerminationReason,
)


def active_range(id_="range", regime=StructuralRegime.BULLISH):
    return StructuralRange(
        id=id_, timeframe="15m", upper_boundary=Decimal("110"),
        lower_boundary=Decimal("90"), defining_high_swing_id="h",
        defining_low_swing_id="l", defining_high_price=Decimal("110"),
        defining_low_price=Decimal("90"), regime=regime,
        creation_time=1, confirmation_time=1, active=True, historical=False,
        created_by_event_id="event",
    )


def pool(id_, level, side=LiquiditySide.BSL, *, external=False,
         state=LiquidityState.ACTIVE, confirmed=1, source="EQUAL_HIGH"):
    price = Decimal(str(level))
    return LiquidityPool(
        id=id_, timeframe="15m", side=side,
        component_reference_ids=(f"{id_}-ref",), component_prices=(price,),
        component_source_types=(source,), consolidated_level=price,
        tolerance_ticks=1, touch_count=2, created_time=confirmed,
        confirmation_time=confirmed, state=state, external=external,
    )


def select(pools, **overrides):
    values = dict(
        pools=tuple(pools), current_price=Decimal("100"),
        active_range=active_range(), regime=StructuralRegime.BULLISH,
        role=LRLRole.CONTINUATION_TARGET, selection_time=10,
    )
    values.update(overrides)
    return LRLSelectionEngine().select(**values)


def test_continuation_directional_mapping_is_symmetric():
    bullish = select((pool("bsl", 101), pool("lsl", 99, LiquiditySide.LSL))).active_lrl
    bearish = select(
        (pool("bsl", 101), pool("lsl", 99, LiquiditySide.LSL)),
        regime=StructuralRegime.BEARISH,
        active_range=active_range(regime=StructuralRegime.BEARISH),
    ).active_lrl
    assert bullish.side == LiquiditySide.BSL
    assert bearish.side == LiquiditySide.LSL


def test_amendment_005a_reversal_sweep_reference_mapping():
    pools = (pool("bsl", 101), pool("lsl", 99, LiquiditySide.LSL))
    bullish = select(pools, role=LRLRole.REVERSAL_SWEEP_REFERENCE).active_lrl
    bearish = select(
        pools, role=LRLRole.REVERSAL_SWEEP_REFERENCE,
        regime=StructuralRegime.BEARISH,
        active_range=active_range(regime=StructuralRegime.BEARISH),
    ).active_lrl
    assert bullish.side == LiquiditySide.BSL
    assert bearish.side == LiquiditySide.LSL


def test_consumed_wrong_side_and_behind_price_are_ineligible():
    result = select((
        pool("consumed", 101, state=LiquidityState.CONSUMED),
        pool("wrong-side", 99, LiquiditySide.LSL),
        pool("behind", 99),
    ))
    assert result.active_lrl is None


def test_external_priority_is_absolute_over_nearer_internal():
    result = select((pool("internal", 101), pool("external", 109, external=True)))
    assert result.active_lrl.pool_id == "external"


def test_no_external_falls_back_to_nearest_internal():
    result = select((pool("far", 108), pool("near", 102)))
    assert result.active_lrl.pool_id == "near"


def test_nearest_target_cannot_be_skipped_to_manufacture_two_r():
    result = select((pool("nearest", 102, external=True), pool("farther", 110, external=True)))
    # #27 may reject the 102 target for R < 2; #24 must never substitute 110.
    assert result.active_lrl.pool_id == "nearest"


def test_equal_distance_uses_reference_priority_then_confirmation_then_id():
    priority = select((
        pool("equal", 105, source="EQUAL_HIGH"),
        pool("weekly", 105, source="PREVIOUS_WEEK_HIGH", confirmed=9),
    )).active_lrl
    time = select((pool("late", 105, confirmed=2), pool("early", 105, confirmed=1))).active_lrl
    identity = select((pool("b", 105), pool("a", 105))).active_lrl
    assert priority.pool_id == "weekly"
    assert time.pool_id == "early"
    assert identity.pool_id == "a"


def test_selection_is_deterministic_across_inventory_order():
    pools = (pool("b", 105), pool("a", 105))
    first = select(pools).active_lrl
    second = select(tuple(reversed(pools))).active_lrl
    assert first == second


def test_selection_persists_when_a_closer_pool_appears():
    previous = select((pool("fixed", 105),), selection_time=10).active_lrl
    result = select(
        (pool("fixed", 105), pool("closer", 101)),
        previous_active_lrl=previous, selection_time=11,
    )
    assert result.active_lrl is previous and result.terminated_lrl is None


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"setup_invalidated": True}, LRLTerminationReason.SETUP_INVALIDATED),
        ({"mss_confirmed": True}, LRLTerminationReason.MSS),
        ({"regime": StructuralRegime.TRANSITION, "active_range": None},
         LRLTerminationReason.TRANSITION),
    ],
)
def test_terminal_events_end_lrl_without_same_setup_reselection(kwargs, reason):
    previous = select((pool("fixed", 105),)).active_lrl
    result = select((pool("fixed", 105),), previous_active_lrl=previous, **kwargs)
    assert result.active_lrl is None
    assert result.terminated_lrl.termination_reason == reason


def test_consumed_selected_pool_terminates_lrl_but_selection_is_not_a_sweep():
    previous = select((pool("fixed", 105),)).active_lrl
    consumed = pool("fixed", 105, state=LiquidityState.CONSUMED)
    result = select((consumed, pool("other", 106)), previous_active_lrl=previous)
    assert result.active_lrl is None
    assert result.terminated_lrl.termination_reason == LRLTerminationReason.CONSUMED
    assert consumed.state == LiquidityState.CONSUMED


def test_range_replacement_terminates_old_and_selects_against_new_range():
    previous = select((pool("old", 105),)).active_lrl
    result = select(
        (pool("new", 106),), previous_active_lrl=previous,
        active_range=active_range("replacement"), selection_time=20,
    )
    assert result.active_lrl.pool_id == "new"
    assert result.terminated_lrl.termination_reason == LRLTerminationReason.RANGE_REPLACED


def test_initializing_or_no_candidates_is_valid_lrl_none_outcome():
    assert select((), regime=StructuralRegime.INITIALIZING).active_lrl is None
    assert select((pool("behind", 99),)).active_lrl is None


def test_invalid_inputs_fail_closed():
    with pytest.raises(ValueError, match="positive"):
        select((), current_price=Decimal("0"))
    duplicate = pool("same", 105)
    with pytest.raises(ValueError, match="Duplicate"):
        select((duplicate, duplicate))
    with pytest.raises(ValueError, match="active #21"):
        select((), active_range=replace(active_range(), active=False, historical=True))
