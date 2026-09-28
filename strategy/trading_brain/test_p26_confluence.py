from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p22_ote import OTEEngine
from strategy.trading_brain.p23_liquidity import LiquiditySide
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole
from strategy.trading_brain.p25_fvg_ifvg import (
    FVG, IFVG, FVGDirection, FVGState,
)
from strategy.trading_brain.p26_confluence import (
    ConfirmedEventFact, ConfluenceCategory, ConfluenceEngine,
    ConfluenceResult, ConfluenceType,
)


def ote():
    range_ = StructuralRange(
        id="range", timeframe="15m", upper_boundary=Decimal("110"),
        lower_boundary=Decimal("90"), defining_high_swing_id="h",
        defining_low_swing_id="l", defining_high_price=Decimal("110"),
        defining_low_price=Decimal("90"), regime=StructuralRegime.BULLISH,
        creation_time=1, confirmation_time=1, active=True, historical=False,
        created_by_event_id="bos",
    )
    return OTEEngine().create(active_range=range_)


def fvg(low="94", high="98", *, state=FVGState.ACTIVE, full=False):
    low, high = Decimal(low), Decimal(high)
    return FVG(
        id=f"fvg-{low}-{high}", timeframe="15m",
        direction=FVGDirection.BULLISH, candle1_id="c1", candle2_id="c2",
        candle3_id="c3", lower_boundary=low, upper_boundary=high,
        gap_size=high-low, creation_time=2, confirmation_time=2,
        displacement_qualified=True, state=state, fully_mitigated=full,
    )


def ifvg(low="94", high="98"):
    return IFVG(
        id="ifvg", source_fvg_id="source", timeframe="15m",
        direction=FVGDirection.BEARISH,
        lower_boundary=Decimal(low), upper_boundary=Decimal(high),
        creation_time=2, confirmation_time=2,
    )


def lrl(level="105"):
    return LRL(
        id="lrl", role=LRLRole.CONTINUATION_TARGET, pool_id="pool",
        pool_timeframe="15m", side=LiquiditySide.BSL, level=Decimal(level),
        external=True, active_range_id="range", regime=StructuralRegime.BULLISH,
        selected_time=2,
    )


def event(kind="SWEEP", low="94", high="98", *, time=2, eligible=True):
    return ConfirmedEventFact(
        id=f"{kind.lower()}-event", event_type=kind, timeframe="15m",
        event_time=time, lower_boundary=Decimal(low), upper_boundary=Decimal(high),
        direction=FVGDirection.BULLISH, setup_eligible=eligible,
    )


def test_closed_confluence_types_are_the_exact_ten_canonical_relationships():
    assert {item.value for item in ConfluenceType} == {
        "OTE_FVG", "OTE_IFVG", "LRL_FVG", "LRL_IFVG",
        "SWEEP_FVG", "SWEEP_IFVG", "DISPLACEMENT_FVG",
        "DISPLACEMENT_IFVG", "MSS_FVG", "MSS_IFVG",
    }


def test_ote_fvg_requires_positive_overlap_and_records_exact_geometry():
    result = ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=2,
    )
    assert result.result == ConfluenceResult.TRUE
    assert result.type == ConfluenceType.OTE_FVG
    assert result.category == ConfluenceCategory.OVERLAP
    assert (result.confluence.overlap_low, result.confluence.overlap_high) == (
        Decimal("94.20"), Decimal("98"),
    )
    assert result.confluence.overlap_width == Decimal("3.80")


def test_boundary_touching_is_not_confluence_golden_scenario():
    # Bullish OTE is [94.2, 100]; the FVG only touches its upper boundary.
    result = ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=fvg("90", "94.2"), evaluation_time=2,
    )
    assert result.result == ConfluenceResult.FALSE
    assert result.confluence is None


def test_ote_ifvg_uses_canonical_ifvg_type_without_mutation():
    source = ifvg()
    before = repr(source)
    result = ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=source, evaluation_time=2,
    )
    assert result.type == ConfluenceType.OTE_IFVG
    assert result.is_confluent and repr(source) == before


def test_fully_mitigated_or_violated_fvg_is_not_active_confluence():
    engine = ConfluenceEngine()
    mitigated = engine.evaluate_ote(
        ote=ote(), imbalance=fvg(state=FVGState.MITIGATED, full=True),
        evaluation_time=3,
    )
    violated = engine.evaluate_ote(
        ote=ote(), imbalance=fvg(state=FVGState.VIOLATED, full=True),
        evaluation_time=3,
    )
    assert mitigated.result == violated.result == ConfluenceResult.FALSE


def test_inactive_ote_and_ineligible_objects_cannot_create_active_confluence():
    source = replace(ote(), active=False, historical=True)
    assert not ConfluenceEngine().evaluate_ote(
        ote=source, imbalance=fvg(), evaluation_time=3,
    ).is_confluent
    assert not ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=3, setup_eligible=False,
    ).is_confluent


def test_lrl_fvg_requires_positive_position_between_price_and_lrl():
    result = ConfluenceEngine().evaluate_lrl(
        lrl=lrl(), imbalance=fvg("101", "103"),
        current_price=Decimal("100"), evaluation_time=2,
    )
    assert result.type == ConfluenceType.LRL_FVG
    assert result.category == ConfluenceCategory.POSITIONAL
    assert result.confluence.positional_relationship is True


def test_lrl_boundary_contact_or_zone_behind_price_is_false():
    engine = ConfluenceEngine()
    touching = engine.evaluate_lrl(
        lrl=lrl(), imbalance=fvg("99", "100"),
        current_price=Decimal("100"), evaluation_time=2,
    )
    behind = engine.evaluate_lrl(
        lrl=lrl(), imbalance=fvg("95", "99"),
        current_price=Decimal("100"), evaluation_time=2,
    )
    assert not touching.is_confluent and not behind.is_confluent


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("SWEEP", ConfluenceType.SWEEP_FVG),
        ("DISPLACEMENT", ConfluenceType.DISPLACEMENT_FVG),
        ("MSS", ConfluenceType.MSS_FVG),
    ],
)
def test_confirmed_event_facts_coincide_with_fvg(kind, expected):
    result = ConfluenceEngine().evaluate_event(
        event=event(kind), imbalance=fvg(), evaluation_time=2,
    )
    assert result.type == expected and result.is_confluent
    assert result.confluence.temporal_relationship
    assert result.confluence.causal_relationship


def test_event_ifvg_emits_ifvg_variant():
    result = ConfluenceEngine().evaluate_event(
        event=event("MSS"), imbalance=ifvg(), evaluation_time=2,
    )
    assert result.type == ConfluenceType.MSS_IFVG and result.is_confluent


def test_event_requires_confirmation_eligibility_coincidence_and_positive_overlap():
    engine = ConfluenceEngine()
    not_eligible = engine.evaluate_event(
        event=event(eligible=False), imbalance=fvg(), evaluation_time=2,
    )
    later = engine.evaluate_event(
        event=event(time=3), imbalance=fvg(), evaluation_time=3,
    )
    touching = engine.evaluate_event(
        event=event(low="90", high="94"), imbalance=fvg(), evaluation_time=2,
    )
    assert not not_eligible.is_confluent
    assert not later.is_confluent
    assert not touching.is_confluent


def test_no_look_ahead_before_both_facts_are_confirmed():
    result = ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=1,
    )
    assert result.result == ConfluenceResult.FALSE


def test_true_relationship_is_deterministic_and_immutable():
    engine = ConfluenceEngine()
    first = engine.evaluate_ote(ote=ote(), imbalance=fvg(), evaluation_time=2)
    second = engine.evaluate_ote(ote=ote(), imbalance=fvg(), evaluation_time=2)
    assert first == second
    with pytest.raises(FrozenInstanceError):
        first.confluence.active = False


def test_dynamic_relationship_terminates_into_history_without_deletion():
    engine = ConfluenceEngine()
    active = engine.evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=2,
    ).confluence
    false_now = engine.evaluate_ote(
        ote=ote(), imbalance=fvg(state=FVGState.MITIGATED, full=True),
        evaluation_time=3,
    )
    update = engine.reconcile(
        previous=active, evaluation=false_now, evaluation_time=3,
    )
    assert update.active_confluence is None
    assert update.terminated_confluence.active is False
    assert update.terminated_confluence.historical is True
    assert update.terminated_confluence.terminated_time == 3
    assert active.active is True and active.historical is False


def test_still_true_relationship_preserves_original_record_identity():
    engine = ConfluenceEngine()
    active = engine.evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=2,
    ).confluence
    still_true = engine.evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=3,
    )
    update = engine.reconcile(
        previous=active, evaluation=still_true, evaluation_time=3,
    )
    assert update.active_confluence is active
    assert update.terminated_confluence is None


def test_directional_compatibility_is_a_fact_not_a_setup_decision():
    result = ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=ifvg(), evaluation_time=2,
    )
    assert result.is_confluent
    assert result.confluence.directional_compatibility is False


def test_facts_only_schema_has_no_trade_decision_or_execution_fields():
    record = ConfluenceEngine().evaluate_ote(
        ote=ote(), imbalance=fvg(), evaluation_time=2,
    ).confluence
    forbidden = {
        "armed", "rejected", "triggered", "authorized", "quantity",
        "order", "position", "executed",
    }
    assert forbidden.isdisjoint(record.__dataclass_fields__)


def test_invalid_inputs_fail_closed():
    engine = ConfluenceEngine()
    with pytest.raises(ValueError, match="positive"):
        engine.evaluate_lrl(
            lrl=lrl(), imbalance=fvg(), current_price=Decimal("0"),
            evaluation_time=2,
        )
    with pytest.raises(ValueError, match="event_type"):
        engine.evaluate_event(
            event=event("ENTRY"), imbalance=fvg(), evaluation_time=2,
        )
    with pytest.raises(ValueError, match="active"):
        active = engine.evaluate_ote(
            ote=ote(), imbalance=fvg(), evaluation_time=2,
        ).confluence
        engine.reconcile(
            previous=replace(active, active=False, historical=True),
            evaluation=engine.evaluate_ote(
                ote=ote(), imbalance=fvg(), evaluation_time=3,
            ), evaluation_time=3,
        )
