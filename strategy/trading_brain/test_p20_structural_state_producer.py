from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from strategy.trading_brain.p19_mechanical_swings import (
    MechanicalSwing, MechanicalSwingResult, MechanicalSwingType,
)
from strategy.trading_brain.p20_structural_classification import (
    StructuralClassification, StructuralRegime, StructuralSwingSelector,
)
from strategy.trading_brain.p20_structural_state_producer import StructuralStateProducer


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)


def ms(value: datetime) -> int:
    return int(value.timestamp() * 1_000)


def swing(name: str, type_: MechanicalSwingType, price: str, minute: int,
          timeframe: str = "5m") -> MechanicalSwing:
    return MechanicalSwing(name, timeframe, type_, Decimal(price),
                           ms(BASE + timedelta(minutes=minute)), True)


def result(*items: MechanicalSwing, timeframe: str = "5m") -> MechanicalSwingResult:
    return MechanicalSwingResult(timeframe, tuple(items))


def ingest(items, minute, ledger=None, **changes):
    values = {
        "swing_result": result(*items), "symbol": "BTC",
        "available_at": BASE + timedelta(minutes=minute),
        "source_version": "candles-v1", "calculation_version": "structure-v1",
        "ledger": ledger,
    }
    values.update(changes)
    return StructuralStateProducer().ingest(**values)


def test_one_sided_initialization_is_pending_and_ineligible():
    high = swing("h1", MechanicalSwingType.H, "110", 1)
    ledger = ingest((high,), 3)
    assert ledger.current_snapshot is None
    assert ledger.classification_ready is False
    assert ledger.pending_source_swing_ids == ("h1",)
    assert ledger.availability_facts[0].source_swing is high
    assert ledger.structural_swings == ()


def test_first_opposite_pair_completes_unclassified_initializing_baseline():
    high = swing("h1", MechanicalSwingType.H, "110", 1)
    low = swing("l1", MechanicalSwingType.L, "90", 4)
    one = ingest((high,), 3)
    two = ingest((high, low), 6, one)
    state = two.current_snapshot
    assert two.classification_ready and state.regime is StructuralRegime.INITIALIZING
    assert state.governing_high.mechanical_swing_id == "h1"
    assert state.governing_low.mechanical_swing_id == "l1"
    assert {item.classification for item in two.structural_swings} == {
        StructuralClassification.UNCLASSIFIED,
    }
    assert one.current_snapshot is None and len(two.snapshots) == 1


def test_pivot_occurrence_is_distinct_from_later_availability_and_no_future_visibility():
    high = swing("h1", MechanicalSwingType.H, "110", 1)
    with pytest.raises(ValueError, match="at or before its pivot"):
        ingest((high,), 1)
    ledger = ingest((high,), 3)
    fact = ledger.availability_facts[0]
    assert fact.source_swing.pivot_time == ms(BASE + timedelta(minutes=1))
    assert fact.available_at == BASE + timedelta(minutes=3)
    assert fact.available_at > BASE + timedelta(milliseconds=fact.source_swing.pivot_time - ms(BASE))


def test_symbol_timeframe_and_version_lineage_is_explicit_and_isolated():
    high = swing("h1", MechanicalSwingType.H, "110", 1)
    ledger = ingest((high,), 3)
    fact = ledger.availability_facts[0]
    assert (fact.symbol, fact.timeframe, fact.source_version, fact.calculation_version) == (
        "BTC", "5m", "candles-v1", "structure-v1",
    )
    for replacement in (
        {"symbol": "ETH"}, {"source_version": "candles-v2"},
        {"calculation_version": "structure-v2"},
    ):
        with pytest.raises(ValueError, match="lineage mismatch"):
            ingest((high,), 4, ledger, **replacement)
    with pytest.raises(ValueError, match="timeframe lineage mismatch"):
        ingest((high,), 3, swing_result=result(high, timeframe="1m"))


def test_same_type_extreme_replacement_preserves_pending_and_superseded_sources():
    h1 = swing("h1", MechanicalSwingType.H, "110", 1)
    h2 = swing("h2", MechanicalSwingType.H, "112", 2)
    low = swing("l1", MechanicalSwingType.L, "90", 4)
    first = ingest((h1,), 3)
    second = ingest((h1, h2), 4, first)
    assert second.pending_source_swing_ids == ("h2",)
    assert second.superseded_source_swing_ids == ("h1",)
    final = ingest((h1, h2, low), 6, second)
    assert final.current_snapshot.governing_high.mechanical_swing_id == "h2"
    assert tuple(f.source_swing.id for f in final.availability_facts) == ("h1", "h2", "l1")
    assert second.pending_source_swing_ids == ("h2",)


def test_alternating_new_leg_remains_pending_until_opposite_leg_closes_it():
    h1 = swing("h1", MechanicalSwingType.H, "110", 1)
    l1 = swing("l1", MechanicalSwingType.L, "90", 4)
    h2 = swing("h2", MechanicalSwingType.H, "115", 7)
    l2 = swing("l2", MechanicalSwingType.L, "95", 10)
    ledger = ingest((h1,), 3)
    ledger = ingest((h1, l1), 6, ledger)
    baseline = ledger.current_snapshot
    ledger = ingest((h1, l1, h2), 9, ledger)
    assert ledger.current_snapshot == baseline and ledger.pending_source_swing_ids == ("h2",)
    ledger = ingest((h1, l1, h2, l2), 12, ledger)
    assert ledger.current_snapshot.governing_high.mechanical_swing_id == "h2"
    assert ledger.current_snapshot.governing_low.mechanical_swing_id == "l1"
    assert ledger.pending_source_swing_ids == ("l2",)
    assert next(item for item in ledger.structural_swings
                if item.mechanical_swing_id == "h2").classification is StructuralClassification.HH


def test_duplicate_replay_is_idempotent_and_conflicting_identity_fails_closed():
    high = swing("h1", MechanicalSwingType.H, "110", 1)
    ledger = ingest((high,), 3)
    assert ingest((high,), 4, ledger) is ledger
    conflict = replace(high, price=Decimal("111"))
    with pytest.raises(ValueError, match="Conflicting reuse"):
        ingest((conflict,), 4, ledger)


def test_chronology_rejects_stale_and_unproven_multi_pivot_availability():
    h1 = swing("h1", MechanicalSwingType.H, "110", 2)
    ledger = ingest((h1,), 4)
    stale = swing("l-stale", MechanicalSwingType.L, "90", 1)
    with pytest.raises(ValueError, match="Stale/out-of-order"):
        ingest((stale,), 5, ledger)
    h2 = swing("h2", MechanicalSwingType.H, "112", 5)
    l2 = swing("l2", MechanicalSwingType.L, "90", 6)
    with pytest.raises(ValueError, match="availability is unproven"):
        ingest((h1, h2, l2), 8, ledger)
    with pytest.raises(ValueError, match="monotonically"):
        ingest((h1, h2), 3, ledger)
    with pytest.raises(ValueError, match="canonical increasing chronology"):
        ingest((h2, h1), 8)


def test_records_are_immutable_and_selector_handoff_is_compatible():
    high = swing("h1", MechanicalSwingType.H, "110", 1)
    low = swing("l1", MechanicalSwingType.L, "90", 4)
    ledger = ingest((high,), 3)
    ledger = ingest((high, low), 6, ledger)
    selected = StructuralSwingSelector().select(swings=(high, low))
    assert selected.swings == ledger.structural_swings
    with pytest.raises(FrozenInstanceError):
        ledger.symbol = "ETH"
    with pytest.raises(FrozenInstanceError):
        ledger.current_snapshot.regime = StructuralRegime.BULLISH


def test_producer_does_not_fabricate_later_primitive_facts():
    annotations = set(StructuralStateProducer.ingest.__annotations__)
    assert annotations == {
        "swing_result", "symbol", "available_at", "source_version",
        "calculation_version", "ledger", "state_before", "return",
    }
    source = __import__(
        "strategy.trading_brain.p20_structural_state_producer",
        fromlist=["placeholder"],
    ).__file__
    text = open(source, encoding="utf-8").read()
    for forbidden in ("p23_liquidity", "p11_cisd", "p26_confluence", "p27_setup", "p29_"):
        assert forbidden not in text
