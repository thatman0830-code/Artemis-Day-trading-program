from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import pytest

from strategy.trading_brain.p13_stop_loss_selection import StopLossSelectionEngine
from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import (
    ContinuationSetupState, ReversalSetupState,
    SetupQualificationEngine, SetupQualificationErrorCode, SetupModel,
)
from strategy.trading_brain.p28_entry_zone_selection import EntryZoneSelectionState
from strategy.trading_brain.test_p13_stop_loss_selection import (
    continuation_inputs, reversal_inputs,
)
from strategy.trading_brain.test_p27_setup_qualification import target
from strategy.trading_brain.owner_policies import (
    OWNER_MIN_RR_V1, MinimumRiskRewardPolicy,
)


def continuation_pipeline(direction=StructuralRegime.BULLISH, *, target_level=None):
    setup, entry_zone, reference = continuation_inputs(direction)
    stop = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone,
        protected_swing=reference, selection_time=4,
    ).stop
    selected_target = target(direction)
    if target_level is not None:
        selected_target = replace(selected_target, level=Decimal(str(target_level)))
    return setup, entry_zone, stop, selected_target


def reversal_pipeline(direction=StructuralRegime.BULLISH, *, target_level=None):
    setup, entry_zone, event = reversal_inputs(direction)
    stop = StopLossSelectionEngine(minimum_tick=Decimal("0.25")).select(
        setup=setup, entry_zone=entry_zone,
        qualifying_sweep=event, selection_time=13,
    ).stop
    selected_target = target(direction)
    if target_level is not None:
        selected_target = replace(selected_target, level=Decimal(str(target_level)))
    return setup, entry_zone, stop, selected_target


def finalize(inputs, *, time=14, **overrides):
    setup, entry_zone, stop, selected_target = inputs
    values = dict(
        phase_a_setup=setup, entry_zone_selection=entry_zone,
        stop_selection=stop, target_lrl=selected_target,
        finalized_time=time,
    )
    values.update(overrides)
    return SetupQualificationEngine().finalize(**values)


def test_continuation_long_exact_two_r_transitions_to_armed():
    # Entry 100.50, stop 89.75 => risk 10.75; target 122 => reward 21.50.
    result = finalize(continuation_pipeline(target_level="122"))
    assert result.valid and result.qualification.executable
    assert result.qualification.final_state == ContinuationSetupState.ARMED
    assert result.qualification.risk == Decimal("10.75")
    assert result.qualification.reward == Decimal("21.50")
    assert result.qualification.r_multiple == Decimal("2")


def test_continuation_short_exact_two_r_is_symmetric():
    # Entry 100.50, stop 110.25 => risk 9.75; target 81 => reward 19.50.
    result = finalize(continuation_pipeline(
        StructuralRegime.BEARISH, target_level="81",
    ))
    assert result.valid and result.qualification.executable
    assert result.qualification.final_state == ContinuationSetupState.ARMED
    assert result.qualification.r_multiple == Decimal("2")


def test_reversal_long_at_least_two_r_transitions_to_entry_zone_armed():
    # Entry 100.50, stop 88.75 => risk 11.75; target 124 => reward 23.50.
    result = finalize(reversal_pipeline(target_level="124"))
    assert result.valid and result.qualification.executable
    assert result.qualification.final_state == ReversalSetupState.ENTRY_ZONE_ARMED
    assert result.qualification.r_multiple == Decimal("2")


def test_reversal_short_above_two_r_is_symmetric():
    result = finalize(reversal_pipeline(StructuralRegime.BEARISH, target_level="78"))
    assert result.valid and result.qualification.executable
    assert result.qualification.final_state == ReversalSetupState.ENTRY_ZONE_ARMED
    assert result.qualification.r_multiple > Decimal("2")


def test_r_below_two_is_canonical_non_error_rejection():
    continuation_result = finalize(continuation_pipeline(target_level="120"))
    reversal_result = finalize(reversal_pipeline(target_level="120"))
    assert continuation_result.error is None
    assert continuation_result.qualification.final_state == ContinuationSetupState.REJECTED
    assert not continuation_result.qualification.executable
    assert reversal_result.error is None
    assert reversal_result.qualification.final_state == ReversalSetupState.REJECTED


def test_owner_minimum_one_r_equality_qualifies_both_models_and_directions():
    cases = (
        continuation_pipeline(target_level="111.25"),
        continuation_pipeline(StructuralRegime.BEARISH, target_level="90.75"),
        reversal_pipeline(target_level="112.25"),
        reversal_pipeline(StructuralRegime.BEARISH, target_level="89.75"),
    )
    for inputs in cases:
        record = finalize(inputs, risk_reward_policy=OWNER_MIN_RR_V1).qualification
        assert record.r_multiple == Decimal("1")
        assert record.executable
        assert record.minimum_required_r == Decimal("1.0")
        assert record.policy_id == "OWNER_MIN_RR_V1"
        assert record.entry == inputs[1].eq_normalized
        assert record.stop == inputs[2].stop_price
        assert record.target == inputs[3].level


def test_owner_minimum_below_one_r_rejects_and_policy_isolates_identity():
    inputs = continuation_pipeline(target_level="110")
    legacy = finalize(inputs).qualification
    owner = finalize(inputs, risk_reward_policy=OWNER_MIN_RR_V1,
                     source_version="source-v1", calculation_version="calc-v1").qualification
    assert not owner.executable and owner.qualification_reason == "BELOW_MINIMUM_R_REJECTED"
    assert legacy.id != owner.id
    assert (owner.source_version, owner.calculation_version) == ("source-v1", "calc-v1")


def test_policy_rejects_model_minimum_below_global_hard_floor():
    with pytest.raises(ValueError, match="global hard minimum"):
        MinimumRiskRewardPolicy("bad", "1", Decimal("1.0"),
            ((SetupModel.CONTINUATION, Decimal("0.99")),
             (SetupModel.REVERSAL_1, Decimal("1.0"))))


def test_exact_decimal_r_formula_uses_frozen_values():
    result = finalize(continuation_pipeline(target_level="121"))
    record = result.qualification
    with localcontext() as context:
        context.prec = 28
        expected = abs(record.target - record.entry) / abs(record.entry - record.stop)
    assert record.risk == abs(record.entry - record.stop)
    assert record.reward == abs(record.target - record.entry)
    assert record.r_multiple == expected


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("entry_zone_selection", "FROZEN_ENTRY_MISSING"),
        ("stop_selection", "IMMUTABLE_STOP_MISSING"),
        ("target_lrl", "FROZEN_TARGET_MISSING"),
    ],
)
def test_missing_frozen_input_fails_closed(field, reason):
    result = finalize(continuation_pipeline(target_level="122"), **{field: None})
    assert not result.valid and result.qualification is None
    assert result.error.code == SetupQualificationErrorCode.SETUP_INVALID
    assert result.error.reason == reason


def test_long_and_short_directional_geometry_is_strict():
    long_inputs = continuation_pipeline(target_level="100.50")
    short_inputs = continuation_pipeline(StructuralRegime.BEARISH, target_level="100.50")
    long_result = finalize(long_inputs)
    short_result = finalize(short_inputs)
    assert long_result.error.reason == "DIRECTIONAL_ENTRY_STOP_TARGET_GEOMETRY_INVALID"
    assert short_result.error.reason == "DIRECTIONAL_ENTRY_STOP_TARGET_GEOMETRY_INVALID"


def test_mismatched_frozen_entry_and_stop_fail_closed_without_replacement():
    setup, entry_zone, stop, selected_target = continuation_pipeline(target_level="122")
    entry_mismatch = finalize(
        (setup, replace(entry_zone, setup_id="other"), stop, selected_target),
    )
    stop_mismatch = finalize(
        (setup, entry_zone, replace(stop, entry_zone_selection_id="other"), selected_target),
    )
    assert entry_mismatch.error.reason == "FROZEN_ENTRY_INVALID"
    assert stop_mismatch.error.reason == "IMMUTABLE_STOP_INVALID"


def test_inactive_or_wrong_frozen_target_fails_closed():
    setup, entry_zone, stop, selected_target = continuation_pipeline(target_level="122")
    inactive = finalize((setup, entry_zone, stop, replace(
        selected_target, active=False, historical=True,
    )))
    wrong_id = finalize((setup, entry_zone, stop, replace(
        selected_target, id="farther-target",
    )))
    assert inactive.error.reason == "FROZEN_TARGET_INVALID"
    assert wrong_id.error.reason == "FROZEN_TARGET_INVALID"


def test_nearest_frozen_target_rejection_cannot_be_rescued_by_farther_target():
    setup, entry_zone, stop, nearest = continuation_pipeline(target_level="120")
    rejected = finalize((setup, entry_zone, stop, nearest))
    farther = replace(nearest, id="farther", level=Decimal("130"))
    attempted_rescue = finalize((setup, entry_zone, stop, farther))
    assert rejected.qualification.final_state == ContinuationSetupState.REJECTED
    assert attempted_rescue.error.reason == "FROZEN_TARGET_INVALID"


def test_invalidated_entry_zone_cannot_be_replaced_during_finalization():
    setup, entry_zone, stop, selected_target = continuation_pipeline(target_level="122")
    invalidated = replace(
        entry_zone, state=EntryZoneSelectionState.INVALIDATED,
        selected_zone_id=None, eq_normalized=None,
    )
    result = finalize((setup, invalidated, stop, selected_target))
    assert result.error.reason == "FROZEN_ENTRY_INVALID"


def test_final_validation_cannot_precede_any_frozen_input():
    result = finalize(continuation_pipeline(target_level="122"), time=3)
    assert result.error.reason == "FINAL_VALIDATION_PRECEDES_FROZEN_INPUT"


def test_phase_a_state_semantics_are_enforced_not_rewritten():
    setup, entry_zone, stop, selected_target = continuation_pipeline(target_level="122")
    result = finalize((replace(
        setup, state=ContinuationSetupState.ARMED,
    ), entry_zone, stop, selected_target))
    assert result.error.reason == "CONTINUATION_PHASE_A_STATE_INVALID"
    assert setup.state == ContinuationSetupState.CANDIDATE


def test_final_record_and_error_are_deterministic_immutable_and_preserve_history():
    inputs = continuation_pipeline(target_level="122")
    before = tuple(repr(item) for item in inputs)
    first = finalize(inputs)
    second = finalize(inputs)
    assert first == second
    assert tuple(repr(item) for item in inputs) == before
    with pytest.raises(FrozenInstanceError):
        first.qualification.r_multiple = Decimal("3")
    error = finalize(inputs, target_lrl=None).error
    with pytest.raises(FrozenInstanceError):
        error.reason = "changed"


def test_final_record_has_no_risk_authorization_sizing_order_or_execution_fields():
    record = finalize(continuation_pipeline(target_level="122")).qualification
    forbidden = {
        "risk_authorized", "risk_percent", "account_equity", "quantity",
        "order", "fill", "position", "protective_order", "execution",
    }
    assert forbidden.isdisjoint(record.__dataclass_fields__)
