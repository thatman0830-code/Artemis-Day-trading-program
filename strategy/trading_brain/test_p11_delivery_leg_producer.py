from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from strategy.trading_brain.p11_cisd_confirmation import CISDEngine, CISDState
from strategy.trading_brain.p11_delivery_leg_producer import (
    DeliveryFormationOutcome, ReversalDeliveryLegProducer,
)
from strategy.trading_brain.p16_conflict_resolution import ConflictResolver
from strategy.trading_brain.p20_displacement import (
    DisplacementOutcome, DisplacementQualification,
)
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakCandidate, StructuralEventType, StructuralRegime,
    StructuralStateSnapshot,
)
from strategy.trading_brain.p20_displacement import DisplacementCandle
from strategy.trading_brain.p23_liquidity import (
    LiquidityInteractionResult, LiquidityPool, LiquiditySide, LiquidityState,
    LiquiditySweep,
)
from strategy.trading_brain.p24_lrl_selection import LRL, LRLRole


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)


def ms(value):
    return int(value.timestamp() * 1000)


def candle(name, minute, open_, close_, *, gap=0):
    opened = BASE + timedelta(minutes=minute + gap)
    open_d, close_d = Decimal(open_), Decimal(close_)
    return DisplacementCandle(
        name, "BTC", "1m", opened, opened + timedelta(minutes=1),
        open_d, max(open_d, close_d) + 1, min(open_d, close_d) - 1,
        close_d, "dataset", "run", "source-v1", "calc-v1", True,
    )


def inputs(direction=StructuralRegime.BULLISH, *, same_candle=False):
    bullish = direction == StructuralRegime.BULLISH
    prior = StructuralRegime.BEARISH if bullish else StructuralRegime.BULLISH
    side = LiquiditySide.LSL if bullish else LiquiditySide.BSL
    state = StructuralStateSnapshot("state", "1m", prior, None, None)
    mss_open = BASE + timedelta(minutes=4)
    candidate = StructuralBreakCandidate(
        "mss", "1m", ms(mss_open), StructuralEventType.MSS, direction,
        "protected", Decimal("100"), Decimal("101" if bullish else "99"),
        True, True, state.id,
    )
    decision = ConflictResolver().resolve(state_before=state, candidates=(candidate,))
    displacement = DisplacementQualification(
        "disp", "disp-key", DisplacementOutcome.QUALIFIED, "QUALIFIED", True,
        "mss-candle", (), "context", candidate.id, state.id, "protected",
        "BTC", "1m", direction, StructuralEventType.MSS, Decimal("100"),
        Decimal("1"), Decimal("2"), Decimal("4"), Decimal("1"), Decimal("2"),
        Decimal("0.5"), mss_open + timedelta(minutes=1),
        mss_open + timedelta(minutes=1), "dataset", "run", "OWNER_MECHANICAL_V1",
        "source-v1", "calc-v1", True, None,
    )
    pool = LiquidityPool(
        "pool", "1m", side, ("a", "b"), (Decimal("90"), Decimal("90")),
        ("STRUCTURAL_SWING", "STRUCTURAL_SWING"), Decimal("90"), 1, 2,
        ms(BASE), ms(BASE), LiquidityState.CONSUMED, True,
    )
    sweep_minute = 4 if same_candle else 2
    sweep_event = LiquiditySweep(
        "sweep", pool.id, "1m", "1m", side, pool.consolidated_level,
        ms(BASE + timedelta(minutes=sweep_minute)), Decimal("89"), Decimal("91"),
        Decimal("1"), LiquidityState.SWEPT, LiquidityState.CONSUMED,
    )
    interaction = LiquidityInteractionResult(pool, sweep_event)
    lrl = LRL(
        "lrl", LRLRole.REVERSAL_SWEEP_REFERENCE, pool.id, "1m", side,
        pool.consolidated_level, True, "range", prior, ms(BASE), True, False,
    )
    if bullish:
        candles = (
            candle("boundary", 0, "100", "101"),
            candle("opp-1", 1, "101", "100"),
            candle("opp-2", 2, "100", "99"),
            candle("opp-3", 3, "99", "98"),
            candle("mss-candle", 4, "98", "102"),
        )
    else:
        candles = (
            candle("boundary", 0, "100", "99"),
            candle("opp-1", 1, "99", "100"),
            candle("opp-2", 2, "100", "101"),
            candle("opp-3", 3, "101", "102"),
            candle("mss-candle", 4, "102", "98"),
        )
    return dict(
        setup_candidate_id="setup", structural_state=state, reversal_lrl=lrl,
        sweep=interaction, mss_decision=decision, displacement=displacement,
        candles=candles, evaluation_time=BASE + timedelta(minutes=5), symbol="BTC",
        dataset_id="dataset", run_id="run", source_version="source-v1",
        calculation_version="calc-v1", configuration_version="config-v1",
    )


def form(**changes):
    values = inputs()
    values.update(changes)
    return ReversalDeliveryLegProducer().form(**values)


@pytest.mark.parametrize("direction", [StructuralRegime.BULLISH, StructuralRegime.BEARISH])
def test_bullish_and_bearish_contiguous_delivery_formation(direction):
    record, ledger = ReversalDeliveryLegProducer().form(**inputs(direction))
    assert record.outcome == DeliveryFormationOutcome.READY
    assert tuple(item.id for item in record.delivery_leg.candles) == ("opp-1", "opp-2", "opp-3")
    assert record.sequence.mss_id == "mss"
    assert record.available_at == BASE + timedelta(minutes=5)
    assert ledger.records == (record,)


def test_same_candle_sweep_and_mss_uses_only_frozen_prior_reference():
    record, _ = ReversalDeliveryLegProducer().form(**inputs(same_candle=True))
    assert record.outcome == DeliveryFormationOutcome.READY
    assert record.sequence.sweep_time == record.sequence.mss_confirmation_time
    assert record.delivery_leg.end_time < record.sequence.mss_confirmation_time


def test_gap_and_dataset_boundary_fail_closed_without_shortening_or_fallback():
    values = inputs()
    values["candles"] = values["candles"][1:]
    record, _ = ReversalDeliveryLegProducer().form(**values)
    assert record.outcome == DeliveryFormationOutcome.INSUFFICIENT_HISTORY
    values = inputs()
    values["candles"] = tuple(
        replace(item, open_time=item.open_time + timedelta(minutes=1),
                close_time=item.close_time + timedelta(minutes=1))
        if item.id == "opp-2" else item for item in values["candles"]
    )
    record, _ = ReversalDeliveryLegProducer().form(**values)
    assert record.outcome in {DeliveryFormationOutcome.INVALID_INPUT,
                              DeliveryFormationOutcome.INSUFFICIENT_HISTORY}


def test_genuine_upstream_identity_direction_and_versions_fail_closed():
    values = inputs()
    values["reversal_lrl"] = replace(values["reversal_lrl"], pool_id="other")
    record, _ = ReversalDeliveryLegProducer().form(**values)
    assert record.outcome == DeliveryFormationOutcome.UPSTREAM_INVALID
    record, _ = form(source_version="source-v2")
    assert record.outcome in {DeliveryFormationOutcome.UPSTREAM_INVALID,
                              DeliveryFormationOutcome.INVALID_INPUT}


def test_idempotency_conflict_invalidation_and_no_reactivation():
    producer = ReversalDeliveryLegProducer()
    values = inputs()
    first, ledger = producer.form(**values)
    replay, same = producer.form(**values, ledger=ledger)
    assert replay is first and same is ledger
    later = candle("future-after-mss", 5, "102", "103")
    replay, same = producer.form(
        **{**values, "candles": values["candles"] + (later,),
           "evaluation_time": BASE + timedelta(minutes=6), "ledger": ledger}
    )
    assert replay is first and same is ledger
    with pytest.raises(ValueError, match="Conflicting"):
        producer.form(**{**values, "candles": values["candles"][:-1] +
                         (replace(values["candles"][-1], close=Decimal("103")),),
                         "ledger": ledger})
    historical, history = producer.invalidate(
        record=first, invalidation_time=BASE + timedelta(minutes=6),
        reason="UPSTREAM_INVALIDATED", ledger=ledger,
    )
    assert historical.historical and not historical.active
    assert first.active and len(history.transitions) == 1
    replay, unchanged = producer.form(**values, ledger=history)
    assert replay is historical and unchanged is history


def test_handoff_preserves_strict_body_close_equality_and_wick_rules():
    record, _ = form()
    engine = CISDEngine()
    process = engine.start(sequence=record.sequence)
    process = engine.identify_reference(
        process=process, delivery_legs=(record.delivery_leg,),
        as_of_time=record.sequence.mss_confirmation_time,
    )
    process = engine.wait_for_body_close(process=process)
    reference = process.reference.reference_price
    equal = replace(record.delivery_leg.candles[-1], id="equal",
                    close_time=record.sequence.mss_confirmation_time,
                    high=reference + 2, close=reference)
    result = engine.evaluate(process=process, candle=equal)
    assert not result.confirmed and result.process.state == CISDState.WAITING_FOR_BODY_CLOSE
    wick = replace(equal, id="wick", close_time=equal.close_time + 60_000,
                   close=reference - Decimal("0.5"))
    result = engine.evaluate(process=result.process, candle=wick)
    assert not result.confirmed
    confirmed = replace(wick, id="confirm", close_time=wick.close_time + 60_000,
                        close=reference + Decimal("1"))
    assert engine.evaluate(process=result.process, candle=confirmed).confirmed


def test_records_are_immutable_and_contain_no_later_ownership():
    record, _ = form()
    with pytest.raises(FrozenInstanceError):
        record.active = False
    text = open(__import__(
        "strategy.trading_brain.p11_delivery_leg_producer", fromlist=["x"]
    ).__file__, encoding="utf-8").read()
    for forbidden in ("p25_fvg", "p27_setup", "p28_entry", "p13_stop", "p29_"):
        assert forbidden not in text
