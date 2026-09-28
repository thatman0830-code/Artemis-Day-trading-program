from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from strategy.trading_brain.p16_conflict_resolution import ConflictResolver
from strategy.trading_brain.p19_mechanical_swings import (
    MechanicalSwing, MechanicalSwingResult, MechanicalSwingType,
)
from strategy.trading_brain.p20_state_commit import StructuralStateCommitter
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakQualifier, StructuralRegime,
)
from strategy.trading_brain.p20_structural_state_producer import StructuralStateProducer
from strategy.trading_brain.p21_active_dealing_range import ActiveDealingRangeEngine
from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionEngine, LiquidityPoolEngine, LiquiditySide,
)
from strategy.trading_brain.p23_liquidity_reference_producer import (
    ReferenceTransitionKind, StructuralLiquidityReferenceProducer,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)


def ms(value):
    return int(value.timestamp() * 1000)


def mechanical(name, type_, price, minute):
    return MechanicalSwing(name, "5m", type_, Decimal(price),
                           ms(BASE + timedelta(minutes=minute)), True)


def upstream(high_name="mh", low_name="ml", high="110", low="90", event="bos",
             direction=StructuralRegime.BULLISH):
    h = mechanical(high_name, MechanicalSwingType.H, high, 1)
    l = mechanical(low_name, MechanicalSwingType.L, low, 4)
    engine = StructuralStateProducer()
    ledger = engine.ingest(
        swing_result=MechanicalSwingResult("5m", (h,)), symbol="BTC",
        available_at=BASE + timedelta(minutes=3), source_version="source-v1",
        calculation_version="calc-v1",
    )
    ledger = engine.ingest(
        swing_result=MechanicalSwingResult("5m", (h, l)), symbol="BTC",
        available_at=BASE + timedelta(minutes=6), source_version="source-v1",
        calculation_version="calc-v1", ledger=ledger,
    )
    initial = ledger.current_snapshot
    break_close = (Decimal(high) + Decimal("2") if direction == StructuralRegime.BULLISH
                   else Decimal(low) - Decimal("2"))
    candidates = StructuralBreakQualifier().qualify(
        state_before=initial,
        candle={"t": ms(BASE + timedelta(minutes=10)),
                "h": (break_close + 1 if direction == StructuralRegime.BULLISH else Decimal(low)),
                "l": (Decimal(high) if direction == StructuralRegime.BULLISH else break_close - 1),
                "c": break_close, "is_closed": True},
        qualifying_displacement=True,
    )
    decision = ConflictResolver().resolve(state_before=initial, candidates=candidates)
    state = StructuralStateCommitter().commit(state_before=initial, decision=decision)
    active_range = ActiveDealingRangeEngine().update(
        state_after=state, accepted_structural_event_id=decision.primary_structural_event_id,
        processing_timestamp=ms(BASE + timedelta(minutes=10)),
    ).active_range
    return ledger, state, active_range, decision.primary_structural_event_id


def derive(source=None, history=None, **changes):
    structural, state, active_range, event = source or upstream()
    values = dict(
        structural_ledger=structural, state_after=state,
        accepted_structural_event_id=event, active_range=active_range,
        symbol="BTC", dataset_id="dataset", run_id="run",
        source_version="source-v1", calculation_version="calc-v1",
        evaluation_time=BASE + timedelta(minutes=11), ledger=history,
    )
    values.update(changes)
    return StructuralLiquidityReferenceProducer().derive(**values)


def test_governing_bsl_and_protected_lsl_are_exact_major_range_boundaries():
    structural, state, active_range, _ = upstream()
    ledger = derive((structural, state, active_range, active_range.created_by_event_id))
    refs = ledger.active_references
    assert {(r.side, r.price) for r in refs} == {
        (LiquiditySide.BSL, Decimal("110")),
        (LiquiditySide.LSL, Decimal("90")),
    }
    assert all(r.major_reference and r.source_type == "STRUCTURAL_SWING" for r in refs)
    facts = [fact for fact in ledger.facts if fact.active]
    assert {fact.source_mechanical_swing_id for fact in facts} == {"mh", "ml"}
    assert all(fact.available_at > BASE + timedelta(minutes=4) for fact in facts)


def test_bearish_protected_high_and_governing_low_map_to_bsl_and_lsl():
    source = upstream(direction=StructuralRegime.BEARISH)
    refs = derive(source).active_references
    assert {(item.side, item.price) for item in refs} == {
        (LiquiditySide.BSL, Decimal("110")),
        (LiquiditySide.LSL, Decimal("90")),
    }
    assert all(item.major_reference for item in refs)


def test_one_sided_pending_candidate_and_mismatched_range_cannot_activate():
    h = mechanical("h", MechanicalSwingType.H, "110", 1)
    pending = StructuralStateProducer().ingest(
        swing_result=MechanicalSwingResult("5m", (h,)), symbol="BTC",
        available_at=BASE + timedelta(minutes=3), source_version="source-v1",
        calculation_version="calc-v1",
    )
    assert pending.current_snapshot is None
    source = upstream()
    with pytest.raises(ValueError, match="exactly define"):
        derive(source, active_range=replace(source[2], defining_high_swing_id="candidate"))


def test_same_source_is_not_duplicated_and_equal_price_distinct_sources_get_distinct_ids():
    first = derive()
    assert derive(history=first) is first
    second_source = upstream("mh-new", "ml-new", "110", "90", "bos-new")
    second = derive(second_source, history=first)
    latest = {fact.reference.id: fact for fact in second.facts}
    active = [fact for fact in latest.values() if fact.active]
    historical = [fact for fact in latest.values() if fact.historical]
    assert len(active) == 2 and len(historical) == 2
    assert {fact.reference.price for fact in active} == {Decimal("110"), Decimal("90")}
    assert {fact.reference.id for fact in active}.isdisjoint(
        {fact.reference.id for fact in historical}
    )
    assert len({fact.source_mechanical_swing_id for fact in second.facts}) == 4


def test_replacement_is_append_only_and_old_reference_never_reactivates():
    first = derive()
    replacement = derive(upstream("mh2", "ml2", "112", "92", "bos2"), history=first)
    assert len(replacement.transitions) == 6
    assert sum(t.kind is ReferenceTransitionKind.HISTORICAL for t in replacement.transitions) == 2
    old_ids = {r.id for r in first.active_references}
    assert old_ids.isdisjoint({r.id for r in replacement.active_references})
    with pytest.raises(ValueError, match="cannot reactivate"):
        derive(history=replacement)
    latest = {fact.reference.id: fact for fact in replacement.facts}
    assert all(not latest[item].active for item in old_ids)


def test_confirmed_existing_pool_sweep_consumes_but_wick_touch_does_not():
    ledger = derive()
    target = next(r for r in ledger.active_references if r.side is LiquiditySide.BSL)
    other = replace(target, id="different-source", confirmation_time=target.confirmation_time + 1)
    inventory = LiquidityPoolEngine(minimum_tick=Decimal("1")).build_inventory(
        references=(target, other), active_range=None,
    )
    pool = inventory.pools[0]
    touch = LiquidityInteractionEngine.evaluate(
        pool=pool, candle={"t": 1, "h": target.price, "l": Decimal("100"),
                           "c": Decimal("109"), "is_closed": True},
        event_timeframe="5m",
    )
    producer = StructuralLiquidityReferenceProducer()
    assert producer.consume(
        reference_id=target.id, interaction=touch,
        consumption_time=BASE + timedelta(minutes=12), ledger=ledger,
    ) is ledger
    swept = LiquidityInteractionEngine.evaluate(
        pool=pool, candle={"t": 2, "h": Decimal("111"), "l": Decimal("100"),
                           "c": Decimal("109"), "is_closed": True},
        event_timeframe="5m",
    )
    consumed = producer.consume(
        reference_id=target.id, interaction=swept,
        consumption_time=BASE + timedelta(minutes=13), ledger=ledger,
    )
    assert target not in consumed.active_references
    assert consumed.facts[-1].consumed and consumed.facts[-1].historical
    assert consumed.transitions[-1].kind is ReferenceTransitionKind.CONSUMED
    assert producer.consume(
        reference_id=target.id, interaction=swept,
        consumption_time=BASE + timedelta(minutes=14), ledger=consumed,
    ) is consumed


def test_lineage_timeframe_range_and_version_mismatches_fail_closed():
    source = upstream()
    with pytest.raises(ValueError, match="lineage mismatch"):
        derive(source, symbol="ETH")
    with pytest.raises(ValueError, match="lineage mismatch"):
        derive(source, source_version="source-v2")
    with pytest.raises(ValueError, match="identities mismatch"):
        derive(source, accepted_structural_event_id="other")
    with pytest.raises(ValueError, match="not yet available"):
        derive(source, evaluation_time=BASE + timedelta(minutes=5))


def test_records_are_immutable_and_no_external_or_later_facts_are_fabricated():
    ledger = derive()
    with pytest.raises(FrozenInstanceError):
        ledger.facts[0].active = False
    module = __import__(
        "strategy.trading_brain.p23_liquidity_reference_producer", fromlist=["x"]
    )
    text = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("SESSION_HIGH", "PREVIOUS_DAY", "p24_lrl", "p11_cisd", "p27_setup", "p29_"):
        assert forbidden not in text
