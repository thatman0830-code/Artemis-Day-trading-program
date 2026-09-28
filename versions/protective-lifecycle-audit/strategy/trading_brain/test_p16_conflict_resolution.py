from dataclasses import replace
from decimal import Decimal

from strategy.trading_brain.p16_conflict_resolution import (
    ConflictResolver, ConflictType, ResolutionRule, SuppressionReason,
)
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakCandidate, StructuralClassification, StructuralEventType,
    StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)


def structural(id_, type_, price):
    return StructuralSwing(
        id=id_, mechanical_swing_id=f"m-{id_}", timeframe="15m", type=type_,
        classification=StructuralClassification.UNCLASSIFIED,
        price=Decimal(str(price)), pivot_time=1, protected=False, regime_ref=None,
    )


def state(regime=StructuralRegime.BULLISH):
    return StructuralStateSnapshot(
        id="state-1", timeframe="15m", regime=regime,
        governing_high=structural("gh", MechanicalSwingType.H, 110),
        governing_low=structural("gl", MechanicalSwingType.L, 100),
        protected_high=structural("ph", MechanicalSwingType.H, 108),
        protected_low=structural("pl", MechanicalSwingType.L, 102),
    )


def candidate(id_, event_type, direction, reference="gh"):
    return StructuralBreakCandidate(
        id=id_, timeframe="15m", processing_timestamp=10_000,
        event_type=event_type, direction=direction,
        reference_swing_id=reference, reference_price=Decimal("110"),
        close_price=Decimal("111"), qualifying_displacement=True,
        qualified=True, state_before_id="state-1",
    )


def test_no_candidate_is_valid_no_action():
    result = ConflictResolver().resolve(
        state_before=state(), candidates=(), processing_timestamp=10_000,
    )
    assert result.conflict_type == ConflictType.NO_STRUCTURAL_CANDIDATE
    assert result.accepted_events == ()


def test_single_candidate_passes_through():
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH)
    result = ConflictResolver().resolve(state_before=state(), candidates=(bos,))
    assert result.accepted_events[0].id == "bos"
    assert result.resolution_rule == ResolutionRule.PASS_THROUGH_SINGLE_CANDIDATE


def test_opposing_mss_suppresses_same_direction_bos():
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH)
    mss = candidate("mss", StructuralEventType.MSS, StructuralRegime.BEARISH, "pl")
    result = ConflictResolver().resolve(state_before=state(), candidates=(bos, mss))
    assert [event.id for event in result.accepted_events] == ["mss"]
    assert [event.id for event in result.suppressed_events] == ["bos"]
    suppressed = result.suppressed_events[0]
    assert suppressed.suppression_reason == SuppressionReason.OPPOSING_MSS_STATE_PRIORITY
    assert suppressed.suppressing_event_id == "mss"
    assert result.primary_structural_event_id == "mss"


def test_bearish_symmetry():
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BEARISH, "gl")
    mss = candidate("mss", StructuralEventType.MSS, StructuralRegime.BULLISH, "ph")
    result = ConflictResolver().resolve(
        state_before=state(StructuralRegime.BEARISH), candidates=(bos, mss),
    )
    assert result.accepted_events[0].id == "mss"


def test_input_order_does_not_change_resolution():
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH)
    mss = candidate("mss", StructuralEventType.MSS, StructuralRegime.BEARISH, "pl")
    resolver = ConflictResolver()
    first = resolver.resolve(state_before=state(), candidates=(bos, mss))
    second = resolver.resolve(state_before=state(), candidates=(mss, bos))
    assert first == second


def test_suppressed_event_remains_qualified_and_immutable_evidence():
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH)
    mss = candidate("mss", StructuralEventType.MSS, StructuralRegime.BEARISH, "pl")
    event = ConflictResolver().resolve(state_before=state(), candidates=(bos, mss)).suppressed_events[0]
    assert event.source_candidate.qualified is True
    assert event.qualified_conditions


def test_mixed_timeframe_candidate_fails_closed():
    bos = replace(candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH), timeframe="1h")
    try:
        ConflictResolver().resolve(state_before=state(), candidates=(bos,))
    except ValueError as error:
        assert "timeframe-isolated" in str(error)
        return
    raise AssertionError("Expected timeframe mismatch")


def test_wrong_frozen_pre_state_fails_closed():
    bos = replace(candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH), state_before_id="other")
    try:
        ConflictResolver().resolve(state_before=state(), candidates=(bos,))
    except ValueError as error:
        assert "frozen pre-state" in str(error)
        return
    raise AssertionError("Expected pre-state mismatch")


def test_uncovered_collision_fails_instead_of_inventing_priority():
    one = candidate("bos-1", StructuralEventType.BOS, StructuralRegime.BULLISH)
    two = candidate("bos-2", StructuralEventType.BOS, StructuralRegime.BULLISH)
    try:
        ConflictResolver().resolve(state_before=state(), candidates=(one, two))
    except ValueError as error:
        assert "not covered" in str(error)
        return
    raise AssertionError("Expected uncovered collision to fail")


def test_finalize_records_post_state_and_chronology():
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH)
    decision = ConflictResolver().resolve(state_before=state(), candidates=(bos,))
    record = ConflictResolver.finalize(
        decision=decision, post_state_id="state-2", chronology_source="15M_CLOSED_OHLC",
        chronology_resolution="KNOWN_CLOSE", created_time=10_001,
    )
    assert record.pre_state_id == "state-1" and record.post_state_id == "state-2"
    assert record.accepted_event_ids == ("bos",) and record.immutable is True


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #16 TESTS PASSED ({len(tests)} cases)")
