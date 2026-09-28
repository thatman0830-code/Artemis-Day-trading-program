from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionEngine, LiquidityPoolEngine, LiquidityReference,
    LiquiditySide, LiquidityState,
)
from strategy.trading_brain.p23_prior_period_references import (
    POLICY_ID, PriorPeriodCandle, PriorPeriodLiquidityReferenceProducer,
    PriorPeriodOutcome, PriorPeriodReferenceType,
)


UTC = timezone.utc


def minute_candles(start, count, *, high="101", low="99", tied=()):
    rows = []
    for index in range(count):
        opened = start + timedelta(minutes=index)
        row_high = Decimal("105") if index in tied else Decimal(high)
        rows.append(PriorPeriodCandle(
            f"c-{opened.isoformat()}", "BTC", "1m", opened,
            opened + timedelta(minutes=1), Decimal("100"), row_high,
            Decimal(low), Decimal("100"), "dataset", "run", "source-v1",
            "calc-v1", True,
        ))
    return tuple(rows)


def evaluate(candles, at, *, zone="UTC", ledger=None, **changes):
    values = dict(
        candles=candles, evaluation_time=at, account_timezone=zone,
        symbol="BTC", dataset_id="dataset", run_id="run",
        policy_id=POLICY_ID, source_version="source-v1",
        calculation_version="calc-v1", ledger=ledger,
    )
    values.update(changes)
    return PriorPeriodLiquidityReferenceProducer().evaluate(**values)


def test_complete_prior_day_registers_exact_pdh_pdl_and_ties_at_period_end():
    start = datetime(2026, 1, 2, tzinfo=UTC)
    result, ledger = evaluate(
        minute_candles(start, 1440, tied=(4, 900)),
        datetime(2026, 1, 3, tzinfo=UTC),
    )
    assert all(status.outcome == PriorPeriodOutcome.REGISTERED for status in result.statuses[:2])
    facts = {fact.reference_type: fact for fact in ledger.facts}
    assert facts[PriorPeriodReferenceType.PDH].reference.price == Decimal("105")
    assert len(facts[PriorPeriodReferenceType.PDH].tied_extreme_candle_ids) == 2
    assert facts[PriorPeriodReferenceType.PDL].reference.price == Decimal("99")
    assert all(fact.reference.confirmation_time == int(datetime(2026, 1, 3, tzinfo=UTC).timestamp() * 1000)
               for fact in facts.values())


def test_complete_prior_iso_week_registers_week_types_and_day_week_stay_distinct():
    start = datetime(2026, 1, 5, tzinfo=UTC)  # Monday
    result, ledger = evaluate(
        minute_candles(start, 7 * 1440), datetime(2026, 1, 12, tzinfo=UTC),
    )
    types = {fact.reference_type for fact in ledger.facts}
    assert {PriorPeriodReferenceType.PWH, PriorPeriodReferenceType.PWL} <= types
    high_facts = [fact for fact in ledger.facts
                  if fact.reference_type in {PriorPeriodReferenceType.PDH,
                                             PriorPeriodReferenceType.PWH}]
    assert len(high_facts) == 2 and high_facts[0].reference.price == high_facts[1].reference.price
    assert high_facts[0].reference.id != high_facts[1].reference.id


def test_developing_period_is_never_exposed_and_partial_boundary_is_insufficient():
    current = datetime(2026, 1, 3, tzinfo=UTC)
    candles = minute_candles(current, 60)
    result, ledger = evaluate(candles, current + timedelta(hours=1))
    assert not ledger.facts
    assert all(item.outcome == PriorPeriodOutcome.INSUFFICIENT_PERIOD for item in result.statuses)


def test_missing_duplicate_forming_future_and_unknown_policy_fail_closed():
    start = datetime(2026, 1, 2, tzinfo=UTC)
    complete = minute_candles(start, 1440)
    result, _ = evaluate(complete[:50] + complete[51:], datetime(2026, 1, 3, tzinfo=UTC))
    assert result.statuses[0].outcome == PriorPeriodOutcome.INSUFFICIENT_PERIOD
    result, _ = evaluate(complete + (complete[0],), datetime(2026, 1, 3, tzinfo=UTC))
    assert result.statuses[0].outcome == PriorPeriodOutcome.INVALID_INPUT
    result, _ = evaluate(tuple(replace(item, is_closed=False) if item is complete[0] else item
                               for item in complete), datetime(2026, 1, 3, tzinfo=UTC))
    assert result.statuses[0].outcome == PriorPeriodOutcome.INVALID_INPUT
    future = replace(
        complete[0], id="future", open_time=datetime(2026, 1, 3, tzinfo=UTC),
        close_time=datetime(2026, 1, 3, 0, 1, tzinfo=UTC),
    )
    result, _ = evaluate(complete + (future,), datetime(2026, 1, 3, tzinfo=UTC))
    assert result.statuses[0].outcome == PriorPeriodOutcome.INVALID_INPUT
    with pytest.raises(ValueError, match="Unknown"):
        evaluate(complete, datetime(2026, 1, 3, tzinfo=UTC), policy_id="OTHER")


def test_non_utc_and_dst_calendar_boundaries_use_timezone_aware_duration():
    # New York 2025-03-09 is the 23-hour spring-forward local day.
    start = datetime(2025, 3, 9, 5, tzinfo=UTC)
    end = datetime(2025, 3, 10, 4, tzinfo=UTC)
    result, ledger = evaluate(minute_candles(start, 23 * 60), end, zone="America/New_York")
    daily = [item for item in result.statuses
             if item.reference_type in {PriorPeriodReferenceType.PDH,
                                        PriorPeriodReferenceType.PDL}]
    assert all(item.outcome == PriorPeriodOutcome.REGISTERED for item in daily)
    fact = next(item for item in ledger.facts if item.reference_type == PriorPeriodReferenceType.PDH)
    assert fact.utc_period_end - fact.utc_period_start == timedelta(hours=23)
    assert fact.local_period_start.utcoffset() != fact.local_period_end.utcoffset()


def test_replay_is_idempotent_identity_is_versioned_and_records_are_immutable():
    start = datetime(2026, 1, 2, tzinfo=UTC)
    candles = minute_candles(start, 1440)
    at = datetime(2026, 1, 3, tzinfo=UTC)
    first, ledger = evaluate(candles, at)
    replay, same = evaluate(candles, at, ledger=ledger)
    assert replay is first and same is ledger
    with pytest.raises(FrozenInstanceError):
        ledger.facts[0].active = False
    other, _ = evaluate(candles, at, calculation_version="calc-v2")
    assert other.id != first.id


def test_existing_23_forms_pool_with_structural_reference_and_owns_consumption():
    start = datetime(2026, 1, 2, tzinfo=UTC)
    _, ledger = evaluate(minute_candles(start, 1440), datetime(2026, 1, 3, tzinfo=UTC))
    pdh = next(item.reference for item in ledger.facts
               if item.reference_type == PriorPeriodReferenceType.PDH)
    structural = LiquidityReference(
        "structural", "1m", LiquiditySide.BSL, pdh.price, pdh.confirmation_time,
        "STRUCTURAL_SWING", True,
    )
    pool = LiquidityPoolEngine(minimum_tick=Decimal("1")).build_inventory(
        references=(pdh, structural), active_range=None,
    ).pools[0]
    touch = LiquidityInteractionEngine.evaluate(
        pool=pool, candle={"t": 1, "h": pdh.price, "l": Decimal("99"),
                           "c": Decimal("100"), "is_closed": True},
        event_timeframe="1m",
    )
    fact, same = PriorPeriodLiquidityReferenceProducer.consume(
        reference_id=pdh.id, interaction=touch,
        consumption_time=datetime(2026, 1, 3, 1, tzinfo=UTC), ledger=ledger,
    )
    assert fact.active and same is ledger
    swept = LiquidityInteractionEngine.evaluate(
        pool=pool, candle={"t": 2, "h": pdh.price + 1, "l": Decimal("99"),
                           "c": pdh.price - 1, "is_closed": True},
        event_timeframe="1m",
    )
    historical, consumed = PriorPeriodLiquidityReferenceProducer.consume(
        reference_id=pdh.id, interaction=swept,
        consumption_time=datetime(2026, 1, 3, 2, tzinfo=UTC), ledger=ledger,
    )
    assert historical.consumed and historical.historical and not historical.active
    replay, unchanged = PriorPeriodLiquidityReferenceProducer.consume(
        reference_id=pdh.id, interaction=swept,
        consumption_time=datetime(2026, 1, 3, 3, tzinfo=UTC), ledger=consumed,
    )
    assert replay is historical and unchanged is consumed


def test_explicit_invalidation_is_chronological_append_only_and_idempotent():
    start = datetime(2026, 1, 2, tzinfo=UTC)
    _, ledger = evaluate(minute_candles(start, 1440), datetime(2026, 1, 3, tzinfo=UTC))
    pdh = next(item for item in ledger.facts
               if item.reference_type == PriorPeriodReferenceType.PDH)
    with pytest.raises(ValueError, match="precedes"):
        PriorPeriodLiquidityReferenceProducer.invalidate(
            reference_id=pdh.reference.id,
            invalidation_time=datetime(2026, 1, 2, 23, 59, tzinfo=UTC),
            reason="source correction", ledger=ledger,
        )
    retired, updated = PriorPeriodLiquidityReferenceProducer.invalidate(
        reference_id=pdh.reference.id,
        invalidation_time=datetime(2026, 1, 3, 1, tzinfo=UTC),
        reason="source correction", ledger=ledger,
    )
    assert not retired.active and retired.historical and not retired.consumed
    assert pdh in updated.facts and retired in updated.facts
    assert pdh.reference not in updated.active_references
    replay, same = PriorPeriodLiquidityReferenceProducer.invalidate(
        reference_id=pdh.reference.id,
        invalidation_time=datetime(2026, 1, 3, 2, tzinfo=UTC),
        reason="ignored replay", ledger=updated,
    )
    assert replay is retired and same is updated


def test_producer_does_not_fabricate_pools_lrl_setups_or_trades():
    module = __import__("strategy.trading_brain.p23_prior_period_references", fromlist=["x"])
    text = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("LiquidityPoolEngine", "LRLSelectionEngine", "SetupQualification", "p29_"):
        assert forbidden not in text
