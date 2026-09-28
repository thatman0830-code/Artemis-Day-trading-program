from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p25_fvg_ifvg import (
    FVG, IFVG, FVGDirection, FVGState,
)
from strategy.trading_brain.p27_setup_qualification import (
    ContinuationSetupState, ReversalSetupState,
)
from strategy.trading_brain.p28_entry_zone_selection import (
    EntryZoneSelectionEngine, EntryZoneSelectionState, EntryZoneType,
)
from strategy.trading_brain.test_p27_setup_qualification import (
    confirmed_cisd, continuation, reversal,
)


def zone(id_, low, high, *, direction=StructuralRegime.BULLISH,
         time=3, timeframe="5m", state=FVGState.ACTIVE):
    low, high = Decimal(str(low)), Decimal(str(high))
    return FVG(
        id=id_, timeframe=timeframe,
        direction=FVGDirection(direction.value),
        candle1_id=f"{id_}-1", candle2_id=f"{id_}-2", candle3_id=f"{id_}-3",
        lower_boundary=low, upper_boundary=high, gap_size=high-low,
        creation_time=time, confirmation_time=time,
        displacement_qualified=True, state=state,
        fully_mitigated=state == FVGState.MITIGATED,
    )


def inverse(id_, low, high, *, direction=StructuralRegime.BULLISH,
            time=3, timeframe="5m"):
    return IFVG(
        id=id_, source_fvg_id=f"source-{id_}", timeframe=timeframe,
        direction=FVGDirection(direction.value),
        lower_boundary=Decimal(str(low)), upper_boundary=Decimal(str(high)),
        creation_time=time, confirmation_time=time,
    )


def continuation_setup(*zones):
    setup = continuation().setup
    return replace(setup, eligible_zone_ids=tuple(item.id for item in zones))


def select_continuation(*zones, tick="0.25", setup=None, selection_time=3):
    setup = setup or continuation_setup(*zones)
    return EntryZoneSelectionEngine(minimum_tick=Decimal(tick)).select(
        setup=setup, candidates=tuple(zones), selection_time=selection_time,
    )


def test_continuation_consumes_candidate_not_armed_and_selects_exactly_one():
    candidate = zone("fvg", "100", "101")
    setup = continuation_setup(candidate)
    result = select_continuation(candidate, setup=setup)
    assert setup.state == ContinuationSetupState.CANDIDATE
    assert result.state == EntryZoneSelectionState.SELECTED
    assert result.selected_zone_id == "fvg"
    assert result.selected_zone_type == EntryZoneType.FVG


def test_ifvg_has_absolute_priority_over_newer_fvg():
    ifvg = inverse("ifvg", "100", "101", time=2)
    fvg = zone("fvg", "99", "100", time=3)
    result = select_continuation(ifvg, fvg)
    assert result.selected_zone_id == "ifvg"


def test_newest_wins_within_same_zone_type():
    old = zone("old", "99", "100", time=2)
    new = zone("new", "101", "102", time=3)
    assert select_continuation(old, new).selected_zone_id == "new"


def test_deepest_is_directional_raw_midpoint_tie_break():
    bullish_low = zone("low", "95", "96", time=3)
    bullish_high = zone("high", "100", "101", time=3)
    assert select_continuation(bullish_high, bullish_low).selected_zone_id == "low"

    bearish_low = zone("low-b", "95", "96", direction=StructuralRegime.BEARISH, time=3)
    bearish_high = zone("high-b", "100", "101", direction=StructuralRegime.BEARISH, time=3)
    setup = replace(
        continuation(direction=StructuralRegime.BEARISH).setup,
        eligible_zone_ids=("low-b", "high-b"),
    )
    result = select_continuation(bearish_low, bearish_high, setup=setup)
    assert result.selected_zone_id == "high-b"


def test_immutable_id_is_final_tie_break_and_inventory_order_independent():
    b = zone("b", "100", "101")
    a = zone("a", "100", "101")
    first = select_continuation(b, a)
    second = select_continuation(a, b)
    assert first.selected_zone_id == second.selected_zone_id == "a"


def test_eq_raw_and_round_half_up_are_frozen_exact_decimals():
    candidate = zone("half-tick", "100", "100.25")
    result = select_continuation(candidate)
    assert result.eq_raw == Decimal("100.125")
    assert result.eq_normalized == Decimal("100.25")
    assert result.zone_low == Decimal("100")
    assert result.zone_high == Decimal("100.25")


def test_eq_uses_zone_geometry_not_ote_midpoint():
    candidate = zone("zone", "96", "98")
    result = select_continuation(candidate)
    assert result.eq_raw == Decimal("97")
    assert result.eq_normalized == Decimal("97.00")
    assert result.eq_raw != Decimal("100")  # #22 OTE EQ for the fixture range.


def test_only_candidates_confirmed_at_eligibility_timestamp_are_frozen():
    eligible = zone("eligible", "100", "101", time=3)
    future = inverse("future", "99", "100", time=4)
    setup = continuation_setup(eligible, future)
    result = select_continuation(
        eligible, future, setup=setup, selection_time=10,
    )
    assert result.selected_zone_id == "eligible"
    assert tuple(item.zone_id for item in result.frozen_candidates) == ("eligible",)
    assert result.candidate_set_frozen_time == 3


def test_wrong_direction_timeframe_or_inactive_zone_is_ineligible():
    wrong_direction = zone("wrong-dir", "100", "101", direction=StructuralRegime.BEARISH)
    wrong_timeframe = zone("wrong-tf", "100", "101", timeframe="1m")
    mitigated = zone("mitigated", "100", "101", state=FVGState.MITIGATED)
    setup = continuation_setup(wrong_direction, wrong_timeframe, mitigated)
    result = select_continuation(
        wrong_direction, wrong_timeframe, mitigated, setup=setup,
    )
    assert result.state == EntryZoneSelectionState.NO_ELIGIBLE_ZONE
    assert result.selected_zone_id is None


def test_continuation_candidate_must_come_from_phase_a_confluence_universe():
    allowed = zone("allowed", "100", "101")
    unqualified = inverse("unqualified", "99", "100")
    setup = replace(continuation().setup, eligible_zone_ids=("allowed",))
    result = select_continuation(allowed, unqualified, setup=setup)
    assert result.selected_zone_id == "allowed"


def test_reversal_consumes_mss_confirmed_and_post_cisd_1m_zone():
    process = confirmed_cisd()
    setup = reversal(cisd_process=process).setup
    candidate = zone("reversal-zone", "100", "101", time=11, timeframe="1m")
    result = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, candidates=(candidate,), selection_time=12,
        cisd_process=process,
    )
    assert setup.state == ReversalSetupState.MSS_CONFIRMED
    assert result.selected_zone_id == "reversal-zone"


def test_reversal_rejects_pre_cisd_wrong_direction_and_non_1m_zones():
    process = confirmed_cisd()
    setup = reversal(cisd_process=process).setup
    old = zone("old", "100", "101", time=10, timeframe="1m")
    wrong = zone("wrong", "100", "101", direction=StructuralRegime.BEARISH, time=11, timeframe="1m")
    five = zone("five", "100", "101", time=11, timeframe="5m")
    result = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, candidates=(old, wrong, five), selection_time=12,
        cisd_process=process,
    )
    assert result.state == EntryZoneSelectionState.NO_ELIGIBLE_ZONE


def test_selected_zone_invalidation_falls_back_only_to_original_candidates():
    preferred = inverse("preferred", "100", "101")
    fallback = zone("fallback", "99", "100")
    setup = continuation_setup(preferred, fallback)
    engine = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25"))
    initial = engine.select(
        setup=setup, candidates=(preferred, fallback), selection_time=3,
    )
    updated = engine.invalidate_and_fallback(
        setup=setup, selection=initial,
        invalidated_zone_id="preferred", invalidation_time=4,
    )
    assert updated.selected_zone_id == "fallback"
    assert updated.previous_selection_id == initial.id
    assert updated.invalidated_zone_ids == ("preferred",)
    assert initial.selected_zone_id == "preferred"


def test_no_future_zone_rescue_after_frozen_candidates_are_exhausted():
    original = zone("original", "100", "101")
    future = inverse("future", "99", "100", time=4)
    setup = continuation_setup(original, future)
    engine = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25"))
    initial = engine.select(
        setup=setup, candidates=(original, future), selection_time=4,
    )
    assert tuple(item.zone_id for item in initial.frozen_candidates) == ("original",)
    exhausted = engine.invalidate_and_fallback(
        setup=setup, selection=initial,
        invalidated_zone_id="original", invalidation_time=5,
    )
    assert exhausted.state == EntryZoneSelectionState.INVALIDATED
    assert exhausted.selected_zone_id is None
    assert all(item.zone_id != "future" for item in exhausted.frozen_candidates)


def test_fallback_respects_full_canonical_ranking_inside_frozen_set():
    first = inverse("first", "100", "101")
    second = inverse("second", "99", "100")
    fvg = zone("fvg", "98", "99")
    setup = continuation_setup(first, second, fvg)
    engine = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25"))
    initial = engine.select(setup=setup, candidates=(fvg, second, first), selection_time=3)
    fallback = engine.invalidate_and_fallback(
        setup=setup, selection=initial,
        invalidated_zone_id=initial.selected_zone_id, invalidation_time=4,
    )
    assert initial.selected_zone_id == "second"  # deeper bullish IFVG tie-break
    assert fallback.selected_zone_id == "first"  # remaining IFVG before FVG


def test_selection_and_fallback_snapshots_are_immutable():
    first = inverse("first", "100", "101")
    second = zone("second", "99", "100")
    setup = continuation_setup(first, second)
    engine = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25"))
    initial = engine.select(setup=setup, candidates=(first, second), selection_time=3)
    fallback = engine.invalidate_and_fallback(
        setup=setup, selection=initial,
        invalidated_zone_id="first", invalidation_time=4,
    )
    with pytest.raises(FrozenInstanceError):
        initial.selected_zone_id = "second"
    assert fallback.previous_selection_id == initial.id


def test_requires_phase_a_eligibility_not_armed_state():
    candidate = zone("candidate", "100", "101")
    setup = continuation_setup(candidate)
    assert select_continuation(candidate, setup=setup).state == EntryZoneSelectionState.SELECTED
    with pytest.raises(ValueError, match="eligibility"):
        select_continuation(
            candidate,
            setup=replace(setup, entry_zone_selection_eligible=False),
        )
    with pytest.raises(ValueError, match="not ARMED"):
        select_continuation(
            candidate,
            setup=replace(setup, state=ContinuationSetupState.ARMED),
        )


def test_invalid_tick_duplicate_identity_and_early_selection_fail_closed():
    with pytest.raises(ValueError, match="positive"):
        EntryZoneSelectionEngine(minimum_tick=Decimal("0"))
    candidate = zone("same", "100", "101")
    setup = continuation_setup(candidate)
    engine = EntryZoneSelectionEngine(minimum_tick=Decimal("0.25"))
    with pytest.raises(ValueError, match="Duplicate"):
        engine.select(
            setup=setup, candidates=(candidate, candidate), selection_time=3,
        )
    with pytest.raises(ValueError, match="precede"):
        engine.select(setup=setup, candidates=(candidate,), selection_time=2)


def test_schema_has_no_stop_r_multiple_arming_risk_order_or_execution_fields():
    result = select_continuation(zone("candidate", "100", "101"))
    forbidden = {
        "stop", "risk", "reward", "r_multiple", "armed", "rejected",
        "quantity", "order", "execution",
    }
    assert forbidden.isdisjoint(result.__dataclass_fields__)
