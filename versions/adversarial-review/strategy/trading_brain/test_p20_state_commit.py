from dataclasses import replace
from decimal import Decimal

from strategy.trading_brain.p16_conflict_resolution import ConflictResolver
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_state_commit import StructuralStateCommitter
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakCandidate, StructuralClassification, StructuralEventType,
    StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)


def structural(id_, type_, price, classification=StructuralClassification.UNCLASSIFIED):
    return StructuralSwing(
        id=id_, mechanical_swing_id=f"m-{id_}", timeframe="15m", type=type_,
        classification=classification, price=Decimal(str(price)), pivot_time=1,
        protected=False, regime_ref=None,
    )


def state(regime=StructuralRegime.INITIALIZING, **changes):
    base = StructuralStateSnapshot(
        id="state-1", timeframe="15m", regime=regime,
        governing_high=structural("gh", MechanicalSwingType.H, 110),
        governing_low=structural("gl", MechanicalSwingType.L, 100),
    )
    return replace(base, **changes)


def candidate(id_, event_type, direction, reference):
    return StructuralBreakCandidate(
        id=id_, timeframe="15m", processing_timestamp=10_000,
        event_type=event_type, direction=direction, reference_swing_id=reference.id,
        reference_price=reference.price, close_price=Decimal("111"),
        qualifying_displacement=True, qualified=True, state_before_id="state-1",
    )


def decision(snapshot, event=None):
    candidates = () if event is None else (event,)
    return ConflictResolver().resolve(
        state_before=snapshot, candidates=candidates,
        processing_timestamp=10_000 if event is None else None,
    )


def test_initial_bullish_bos_establishes_regime_and_protected_low():
    before = state()
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH, before.governing_high)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before, bos))
    assert after.regime == StructuralRegime.BULLISH
    assert after.protected_low.mechanical_swing_id == before.governing_low.mechanical_swing_id
    assert after.protected_low.protected is True and after.protected_high is None


def test_initial_bearish_bos_is_symmetric():
    before = state()
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BEARISH, before.governing_low)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before, bos))
    assert after.regime == StructuralRegime.BEARISH
    assert after.protected_high.mechanical_swing_id == before.governing_high.mechanical_swing_id


def test_bullish_continuation_promotes_only_candidate_hl():
    old = structural("old-pl", MechanicalSwingType.L, 100)
    hl = structural("hl", MechanicalSwingType.L, 103, StructuralClassification.HL)
    before = state(StructuralRegime.BULLISH, protected_low=old, candidate_protected_low=hl)
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH, before.governing_high)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before, bos))
    assert after.protected_low.mechanical_swing_id == "m-hl"
    assert after.candidate_protected_low is None
    assert before.protected_low.id == "old-pl" and before.candidate_protected_low.id == "hl"


def test_bare_hl_does_not_transfer_without_accepted_bos():
    old = structural("old-pl", MechanicalSwingType.L, 100)
    hl = structural("hl", MechanicalSwingType.L, 103, StructuralClassification.HL)
    before = state(StructuralRegime.BULLISH, protected_low=old, candidate_protected_low=hl)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before))
    assert after.protected_low == old and after.candidate_protected_low == hl


def test_bearish_continuation_promotes_candidate_lh():
    old = structural("old-ph", MechanicalSwingType.H, 110)
    lh = structural("lh", MechanicalSwingType.H, 107, StructuralClassification.LH)
    before = state(StructuralRegime.BEARISH, protected_high=old, candidate_protected_high=lh)
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BEARISH, before.governing_low)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before, bos))
    assert after.protected_high.mechanical_swing_id == "m-lh"


def test_accepted_mss_terminates_protection_and_enters_transition():
    protected = structural("pl", MechanicalSwingType.L, 102)
    before = state(StructuralRegime.BULLISH, protected_low=protected)
    mss = candidate("mss", StructuralEventType.MSS, StructuralRegime.BEARISH, protected)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before, mss))
    assert after.regime == StructuralRegime.TRANSITION
    assert after.protected_low is None and after.protected_high is None


def test_mss_is_not_reclassified_as_first_opposing_bos():
    protected = structural("pl", MechanicalSwingType.L, 102)
    before = state(StructuralRegime.BULLISH, protected_low=protected)
    mss = candidate("mss", StructuralEventType.MSS, StructuralRegime.BEARISH, protected)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision(before, mss))
    assert after.regime != StructuralRegime.BEARISH


def test_post_state_has_immutable_lineage_and_stable_identity():
    before = state()
    bos = candidate("bos", StructuralEventType.BOS, StructuralRegime.BULLISH, before.governing_high)
    resolved = decision(before, bos)
    first = StructuralStateCommitter().commit(state_before=before, decision=resolved)
    second = StructuralStateCommitter().commit(state_before=before, decision=resolved)
    assert first == second
    assert first.predecessor_state_id == before.id and first.as_of_timestamp == 10_000


def test_invalid_candidate_protection_classification_fails_closed():
    invalid = structural("low", MechanicalSwingType.L, 103, StructuralClassification.LL)
    before = state(StructuralRegime.BULLISH, candidate_protected_low=invalid)
    try:
        StructuralStateCommitter().commit(state_before=before, decision=decision(before))
    except ValueError as error:
        assert "classified HL" in str(error)
        return
    raise AssertionError("Expected invalid candidate protection to fail")


if __name__ == "__main__":
    tests = [v for n, v in sorted(globals().items()) if n.startswith("test_")]
    for test in tests:
        test()
    print(f"CANONICAL #20 PHASE C TESTS PASSED ({len(tests)} cases)")
