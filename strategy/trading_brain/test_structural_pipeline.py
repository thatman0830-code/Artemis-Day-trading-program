from decimal import Decimal

from strategy.trading_brain.p16_conflict_resolution import ConflictResolver
from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_state_commit import StructuralStateCommitter
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakQualifier, StructuralClassification, StructuralRegime,
    StructuralStateSnapshot, StructuralSwing,
)
from strategy.trading_brain.p21_active_dealing_range import ActiveDealingRangeEngine
from strategy.trading_brain.p22_ote import OTEEngine


def structural(id_, type_, price):
    return StructuralSwing(
        id=id_, mechanical_swing_id=f"m-{id_}", timeframe="15m", type=type_,
        classification=StructuralClassification.UNCLASSIFIED,
        price=Decimal(str(price)), pivot_time=1, protected=False, regime_ref=None,
    )


def test_initialization_through_final_conflict_record():
    before = StructuralStateSnapshot(
        id="initial", timeframe="15m", regime=StructuralRegime.INITIALIZING,
        governing_high=structural("high", MechanicalSwingType.H, 110),
        governing_low=structural("low", MechanicalSwingType.L, 100),
    )
    candidates = StructuralBreakQualifier().qualify(
        state_before=before,
        candle={"t": 10_000, "h": 112, "l": 109, "c": 111, "is_closed": True},
        qualifying_displacement=True,
    )
    decision = ConflictResolver().resolve(state_before=before, candidates=candidates)
    after = StructuralStateCommitter().commit(state_before=before, decision=decision)
    record = ConflictResolver.finalize(
        decision=decision, post_state_id=after.id,
        chronology_source="15M_CLOSED_OHLC",
        chronology_resolution="KNOWN_CLOSE",
        created_time=10_001,
    )
    assert before.regime == StructuralRegime.INITIALIZING
    assert after.regime == StructuralRegime.BULLISH
    assert after.protected_low.mechanical_swing_id == "m-low"
    assert record.pre_state_id == before.id and record.post_state_id == after.id
    assert record.accepted_event_ids == (candidates[0].id,)

    range_result = ActiveDealingRangeEngine().update(
        state_after=after,
        accepted_structural_event_id=decision.primary_structural_event_id,
        processing_timestamp=10_001,
    )
    assert range_result.active_range.lower_boundary == Decimal("100")
    assert range_result.active_range.upper_boundary == Decimal("110")
    assert range_result.active_range.created_by_event_id == candidates[0].id

    ote = OTEEngine().create(active_range=range_result.active_range)
    assert ote.range_id == range_result.active_range.id
    assert ote.eq_50_price == Decimal("105.00")
    assert ote.ote_79_price == Decimal("102.10")


if __name__ == "__main__":
    test_initialization_through_final_conflict_record()
    print("CANONICAL STRUCTURAL PIPELINE THROUGH OTE PASSED (1 case)")
