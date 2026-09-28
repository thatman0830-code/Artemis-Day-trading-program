from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p11_cisd_confirmation import (
    CISDDirection, CISDEngine, DeliveryCandle, DeliveryLeg,
    ReversalConfirmationSequence,
)
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralRegime, StructuralSwing,
)
from strategy.trading_brain.p21_active_dealing_range import StructuralRange
from strategy.trading_brain.p22_ote import OTEEngine
from strategy.trading_brain.p23_liquidity import LiquiditySide
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole
from strategy.trading_brain.p25_fvg_ifvg import FVGDirection
from strategy.trading_brain.p26_confluence import (
    Confluence, ConfluenceCategory, ConfluenceType,
)
from strategy.trading_brain.p27_setup_qualification import (
    ContinuationSetupState, ReversalSetupState, SetupModel,
    SetupQualificationEngine,
)


def structural_range(direction=StructuralRegime.BULLISH):
    return StructuralRange(
        id="range", timeframe="5m", upper_boundary=Decimal("110"),
        lower_boundary=Decimal("90"), defining_high_swing_id="high",
        defining_low_swing_id="low", defining_high_price=Decimal("110"),
        defining_low_price=Decimal("90"), regime=direction,
        creation_time=1, confirmation_time=1, active=True, historical=False,
        created_by_event_id="bos",
    )


def protected(direction=StructuralRegime.BULLISH):
    type_ = MechanicalSwingType.L if direction == StructuralRegime.BULLISH else MechanicalSwingType.H
    return StructuralSwing(
        id="protected", mechanical_swing_id="mechanical", timeframe="5m",
        type=type_, classification=(
            StructuralClassification.HL if type_ == MechanicalSwingType.L
            else StructuralClassification.LH
        ), price=Decimal("90" if type_ == MechanicalSwingType.L else "110"),
        pivot_time=1, protected=True, regime_ref="regime",
    )


def target(direction=StructuralRegime.BULLISH, *, role=LRLRole.CONTINUATION_TARGET):
    bullish = direction == StructuralRegime.BULLISH
    return LRL(
        id="target", role=role, pool_id="pool", pool_timeframe="5m",
        side=LiquiditySide.BSL if bullish else LiquiditySide.LSL,
        level=Decimal("120" if bullish else "80"), external=True,
        active_range_id="range", regime=direction, selected_time=2,
    )


def confluence(ote_id, *, direction_ok=True, active=True, historical=False,
               type_=ConfluenceType.OTE_FVG):
    return Confluence(
        id="confluence", type=type_, category=ConfluenceCategory.OVERLAP,
        primary_object_id=ote_id, secondary_object_id="fvg",
        primary_type="OTE", secondary_type="FVG",
        primary_timeframe="5m", secondary_timeframe="5m",
        overlap_low=Decimal("94.2"), overlap_high=Decimal("98"),
        overlap_width=Decimal("3.8"),
        directional_compatibility=direction_ok,
        temporal_relationship=True, positional_relationship=True,
        causal_relationship=False, created_time=2, terminated_time=None,
        active=active, historical=historical,
    )


def continuation(**overrides):
    direction = overrides.pop("direction", StructuralRegime.BULLISH)
    range_ = overrides.pop("active_range", structural_range(direction))
    if "ote" in overrides:
        ote = overrides.pop("ote")
    else:
        ote = OTEEngine().create(active_range=range_) if range_ is not None else None
    default_confluences = (confluence(ote.id),) if ote is not None else ()
    values = dict(
        setup_candidate_id="continuation-a",
        state=ContinuationSetupState.CANDIDATE, direction=direction,
        protected_swing=protected(direction), active_range=range_, ote=ote,
        target_lrl=target(direction), confluences=default_confluences,
        evaluation_time=3,
    )
    values.update(overrides)
    return SetupQualificationEngine().qualify_continuation(**values)


def confirmed_cisd(direction=CISDDirection.BULLISH):
    bullish = direction == CISDDirection.BULLISH
    sequence = ReversalConfirmationSequence(
        setup_candidate_id="reversal-a", intended_direction=direction,
        prior_regime=StructuralRegime.BEARISH if bullish else StructuralRegime.BULLISH,
        sweep_id="sweep", sweep_side=LiquiditySide.LSL if bullish else LiquiditySide.BSL,
        sweep_time=5, mss_id="mss", mss_confirmation_time=10,
        mss_accepted=True,
    )
    if bullish:
        delivery = DeliveryCandle("delivery", "1m", Decimal("100"), Decimal("101"), Decimal("98"), Decimal("99"), 9)
        confirm = DeliveryCandle("confirm", "1m", Decimal("99"), Decimal("102"), Decimal("98"), Decimal("101"), 11)
        leg_direction = CISDDirection.BEARISH
    else:
        delivery = DeliveryCandle("delivery", "1m", Decimal("100"), Decimal("102"), Decimal("99"), Decimal("101"), 9)
        confirm = DeliveryCandle("confirm", "1m", Decimal("101"), Decimal("102"), Decimal("98"), Decimal("99"), 11)
        leg_direction = CISDDirection.BULLISH
    leg = DeliveryLeg(
        id="leg", setup_candidate_id="reversal-a", timeframe="1m",
        direction=leg_direction, candles=(delivery,),
        directly_precedes_reversal_delivery=True,
    )
    engine = CISDEngine()
    process = engine.start(sequence=sequence)
    process = engine.identify_reference(process=process, delivery_legs=(leg,), as_of_time=10)
    process = engine.wait_for_body_close(process=process)
    return engine.evaluate(process=process, candle=confirm).process


def reversal(**overrides):
    direction = overrides.pop("direction", StructuralRegime.BULLISH)
    values = dict(
        setup_candidate_id="reversal-a", state=ReversalSetupState.MSS_CONFIRMED,
        direction=direction,
        cisd_process=confirmed_cisd(
            CISDDirection.BULLISH if direction == StructuralRegime.BULLISH
            else CISDDirection.BEARISH
        ),
        target_lrl=target(direction), evaluation_time=12,
    )
    values.update(overrides)
    return SetupQualificationEngine().qualify_reversal_1(**values)


def test_continuation_phase_a_becomes_zone_selection_eligible_but_stays_candidate():
    result = continuation()
    assert result.eligible_for_entry_zone_selection
    assert result.setup.model == SetupModel.CONTINUATION
    assert result.setup.state == ContinuationSetupState.CANDIDATE
    assert result.setup.missing_prerequisites == ()


def test_bearish_continuation_is_symmetric():
    result = continuation(direction=StructuralRegime.BEARISH)
    assert result.eligible_for_entry_zone_selection
    assert result.setup.direction == StructuralRegime.BEARISH


@pytest.mark.parametrize(
    ("override", "missing"),
    [
        ({"protected_swing": None}, "DIRECTIONAL_PROTECTED_STRUCTURE_AND_ACTIVE_RANGE"),
        ({"active_range": None}, "DIRECTIONAL_PROTECTED_STRUCTURE_AND_ACTIVE_RANGE"),
        ({"ote": None, "confluences": ()}, "ACTIVE_5M_OTE"),
        ({"confluences": ()}, "ACTIVE_DIRECTIONAL_OTE_IMBALANCE_CONFLUENCE"),
        ({"target_lrl": None}, "ACTIVE_CONTINUATION_TARGET_LRL"),
    ],
)
def test_missing_continuation_prerequisite_remains_candidate(override, missing):
    result = continuation(**override)
    assert not result.eligible_for_entry_zone_selection
    assert result.setup.state == ContinuationSetupState.CANDIDATE
    assert missing in result.setup.missing_prerequisites


def test_continuation_requires_active_directionally_compatible_5m_ote_confluence():
    baseline = continuation()
    ote_id = baseline.setup.ote_id
    incompatible = continuation(confluences=(confluence(ote_id, direction_ok=False),))
    historical = continuation(confluences=(confluence(ote_id, active=False, historical=True),))
    wrong_type = continuation(confluences=(confluence(ote_id, type_=ConfluenceType.LRL_FVG),))
    assert not incompatible.eligible_for_entry_zone_selection
    assert not historical.eligible_for_entry_zone_selection
    assert not wrong_type.eligible_for_entry_zone_selection


def test_continuation_target_must_be_active_continuation_role_and_directional():
    wrong_role = continuation(target_lrl=target(role=LRLRole.REVERSAL_SWEEP_REFERENCE))
    inactive = continuation(target_lrl=replace(target(), active=False, historical=True))
    wrong_side = continuation(target_lrl=replace(target(), side=LiquiditySide.LSL))
    assert not wrong_role.eligible_for_entry_zone_selection
    assert not inactive.eligible_for_entry_zone_selection
    assert not wrong_side.eligible_for_entry_zone_selection


def test_reversal_phase_a_consumes_cisd_and_stays_mss_confirmed():
    result = reversal()
    assert result.eligible_for_entry_zone_selection
    assert result.setup.model == SetupModel.REVERSAL_1
    assert result.setup.state == ReversalSetupState.MSS_CONFIRMED
    assert result.setup.cisd_confirmation_id is not None


def test_bearish_reversal_is_symmetric():
    result = reversal(direction=StructuralRegime.BEARISH)
    assert result.eligible_for_entry_zone_selection
    assert result.setup.direction == StructuralRegime.BEARISH


def test_reversal_requires_active_setup_specific_cisd():
    process = confirmed_cisd()
    wrong_setup = reversal(cisd_process=replace(
        process,
        confirmation=replace(process.confirmation, setup_candidate_id="other"),
    ))
    terminated = reversal(cisd_process=CISDEngine.terminate(
        process=process, invalidation_time=12, invalidation_reason="UPSTREAM_INVALIDATED",
    ))
    assert not wrong_setup.eligible_for_entry_zone_selection
    assert not terminated.eligible_for_entry_zone_selection
    assert wrong_setup.setup.state == ReversalSetupState.MSS_CONFIRMED


def test_reversal_requires_post_mss_continuation_target_not_sweep_reference():
    sweep_reference = target(role=LRLRole.REVERSAL_SWEEP_REFERENCE)
    result = reversal(target_lrl=sweep_reference)
    assert not result.eligible_for_entry_zone_selection
    assert "POST_MSS_ACTIVE_CONTINUATION_TARGET_LRL" in result.setup.missing_prerequisites


def test_no_look_ahead_rejects_future_confluence_target_and_cisd_facts():
    baseline = continuation()
    ote_id = baseline.setup.ote_id
    future_fact = replace(confluence(ote_id), created_time=10)
    future_target = replace(target(), selected_time=10)
    assert not continuation(confluences=(future_fact,), evaluation_time=3).eligible_for_entry_zone_selection
    assert not continuation(target_lrl=future_target, evaluation_time=3).eligible_for_entry_zone_selection
    process = confirmed_cisd()
    assert not reversal(cisd_process=process, evaluation_time=10).eligible_for_entry_zone_selection


def test_phase_a_never_requires_armed_and_refuses_post_zone_states():
    assert continuation().setup.state == ContinuationSetupState.CANDIDATE
    assert reversal().setup.state == ReversalSetupState.MSS_CONFIRMED
    with pytest.raises(ValueError, match="never ARMED"):
        continuation(state=ContinuationSetupState.ARMED)
    with pytest.raises(ValueError, match="never ENTRY_ZONE_ARMED"):
        reversal(state=ReversalSetupState.ENTRY_ZONE_ARMED)


def test_setup_decision_and_upstream_facts_are_immutable():
    range_ = structural_range()
    before = repr(range_)
    result = continuation(active_range=range_)
    assert repr(range_) == before
    with pytest.raises(FrozenInstanceError):
        result.setup.entry_zone_selection_eligible = False


def test_phase_a_schema_has_no_zone_eq_stop_risk_reward_arming_or_execution_fields():
    setup = continuation().setup
    forbidden = {
        "selected_zone", "entry_price", "eq", "stop", "risk", "reward",
        "r_multiple", "armed", "rejected", "quantity", "order", "execution",
    }
    assert forbidden.isdisjoint(setup.__dataclass_fields__)


def test_duplicate_confluence_identity_fails_closed():
    baseline = continuation()
    fact = confluence(baseline.setup.ote_id)
    with pytest.raises(ValueError, match="Duplicate"):
        continuation(confluences=(fact, fact))


def test_setup_identity_is_deterministic():
    assert continuation().setup.id == continuation().setup.id
    assert reversal().setup.id == reversal().setup.id
