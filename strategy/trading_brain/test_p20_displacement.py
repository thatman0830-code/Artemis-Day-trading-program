from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from strategy.trading_brain.p19_mechanical_swings import MechanicalSwingType
from strategy.trading_brain.p20_displacement import (
    DisplacementCandle, DisplacementOutcome, DisplacementQualificationProducer,
    MechanicalDisplacementPolicy,
)
from strategy.trading_brain.p20_structural_classification import (
    StructuralBreakQualifier, StructuralClassification, StructuralEventType,
    StructuralRegime, StructuralStateSnapshot, StructuralSwing,
)


UTC = timezone.utc
BASE = datetime(2026, 8, 20, tzinfo=UTC)


def structural(name, type_, price):
    return StructuralSwing(name, "m-" + name, "5m", type_,
                           StructuralClassification.UNCLASSIFIED, Decimal(price),
                           int(BASE.timestamp() * 1000), False, None)


def state():
    return StructuralStateSnapshot(
        "state", "5m", StructuralRegime.INITIALIZING,
        structural("high", MechanicalSwingType.H, "100"),
        structural("low", MechanicalSwingType.L, "90"),
    )


def candle(index, open_, high, low, close, *, closed=True, suffix=""):
    opened = BASE + timedelta(minutes=5 * index)
    return DisplacementCandle(
        f"c{index}{suffix}", "BTC", "5m", opened, opened + timedelta(minutes=5),
        Decimal(open_), Decimal(high), Decimal(low), Decimal(close),
        "dataset", "run", "source-v1", "calc-v1", closed,
    )


def references(body="2"):
    result = []
    for index in range(20):
        opened = Decimal("95")
        closed = opened + Decimal(body)
        result.append(candle(index, str(opened), str(closed + 1), str(opened - 1), str(closed)))
    return tuple(result)


def evaluate(direction=StructuralRegime.BULLISH, evaluation=None, refs=None,
             ledger=None, **changes):
    snapshot = state()
    producer = DisplacementQualificationProducer()
    context = producer.context(
        state=snapshot, symbol="BTC", direction=direction,
        event_type=StructuralEventType.BOS,
    )
    values = dict(
        policy=MechanicalDisplacementPolicy.owner_mechanical_v1(calculation_version="calc-v1"),
        context=context, state_before=snapshot,
        evaluation_candle=evaluation or (
            candle(20, "98", "102", "97", "101")
            if direction == StructuralRegime.BULLISH
            else candle(20, "92", "93", "88", "89")
        ),
        reference_candles=refs if refs is not None else references(),
        minimum_tick=Decimal("1"), dataset_id="dataset", run_id="run",
        source_version="source-v1", calculation_version="calc-v1", ledger=ledger,
    )
    values.update(changes)
    return producer.evaluate(**values)


def test_bullish_and_bearish_exact_thresholds_qualify():
    bullish, _ = evaluate()
    bearish, _ = evaluate(StructuralRegime.BEARISH)
    for record in (bullish, bearish):
        assert record.outcome is DisplacementOutcome.QUALIFIED
        assert record.body == Decimal("3")
        assert record.median_prior_body == Decimal("2")
        assert record.body_expansion == Decimal("1.5")
        assert record.body_ratio == Decimal("0.6")
        assert len(record.reference_candle_ids) == 20


@pytest.mark.parametrize("evaluation,reason", [
    (candle(20, "101", "102", "97", "98"), "THRESHOLD_OR_DIRECTION_NOT_SATISFIED"),
    (candle(20, "98", "101", "97", "100"), "THRESHOLD_OR_DIRECTION_NOT_SATISFIED"),
    (candle(20, "99", "102", "97", "101"), "THRESHOLD_OR_DIRECTION_NOT_SATISFIED"),
    (candle(20, "98", "103", "97", "101"), "THRESHOLD_OR_DIRECTION_NOT_SATISFIED"),
])
def test_direction_clearance_expansion_and_ratio_below_boundaries_do_not_qualify(evaluation, reason):
    record, _ = evaluate(evaluation=evaluation)
    assert record.outcome is DisplacementOutcome.NOT_QUALIFIED
    assert record.reason == reason


def test_above_thresholds_and_exact_one_tick_clearance_qualify():
    record, _ = evaluate(evaluation=candle(20, "97", "102", "96", "101"))
    assert record.qualified and record.body_expansion > Decimal("1.5")
    assert record.body_ratio > Decimal("0.60")
    assert record.evaluation_candle_id == "c20"


def test_zero_body_range_and_median_outcomes_are_distinct():
    zero_body, _ = evaluate(evaluation=candle(20, "101", "103", "97", "101"))
    assert zero_body.outcome is DisplacementOutcome.NOT_QUALIFIED
    zero_range, _ = evaluate(evaluation=candle(20, "101", "101", "101", "101"))
    assert zero_range.outcome is DisplacementOutcome.INVALID_INPUT
    zero_median, _ = evaluate(refs=references("0"))
    assert zero_median.outcome is DisplacementOutcome.INSUFFICIENT_REFERENCE


def test_exact_reference_count_gap_forming_and_future_fail_closed():
    assert evaluate(refs=references()[:-1])[0].outcome is DisplacementOutcome.INSUFFICIENT_REFERENCE
    gapped = list(references())
    gapped[10] = replace(gapped[10], open_time=gapped[10].open_time + timedelta(minutes=1),
                         close_time=gapped[10].close_time + timedelta(minutes=1))
    assert evaluate(refs=tuple(gapped))[0].outcome is DisplacementOutcome.INSUFFICIENT_REFERENCE
    forming = list(references()); forming[3] = replace(forming[3], is_closed=False)
    assert evaluate(refs=tuple(forming))[0].outcome is DisplacementOutcome.INVALID_INPUT
    future = list(references()); future[-1] = replace(future[-1], close_time=BASE + timedelta(minutes=101))
    assert evaluate(refs=tuple(future))[0].outcome is DisplacementOutcome.INSUFFICIENT_REFERENCE


def test_availability_lineage_upstream_invalidation_and_immutability():
    record, ledger = evaluate()
    assert record.occurrence_time == record.available_at == BASE + timedelta(minutes=105)
    assert (record.dataset_id, record.run_id, record.policy_id,
            record.source_version, record.calculation_version) == (
        "dataset", "run", "OWNER_MECHANICAL_V1", "source-v1", "calc-v1")
    with pytest.raises(FrozenInstanceError):
        record.qualified = False
    invalid, updated = DisplacementQualificationProducer.invalidate(
        record=record, reason="UPSTREAM_EVENT_HISTORICAL", ledger=ledger,
    )
    assert not invalid.active and updated.records == (record, invalid)
    upstream, _ = evaluate(upstream_active=False)
    assert upstream.outcome is DisplacementOutcome.UPSTREAM_INVALID


def test_identity_version_timeframe_mismatch_and_duplicate_conflict():
    wrong = replace(candle(20, "98", "102", "97", "101"), symbol="ETH")
    assert evaluate(evaluation=wrong)[0].outcome is DisplacementOutcome.INVALID_INPUT
    record, ledger = evaluate()
    replay, same = evaluate(ledger=ledger)
    assert replay == record and same is ledger
    changed = candle(20, "97", "102", "96", "101")
    with pytest.raises(ValueError, match="Conflicting displacement"):
        evaluate(evaluation=changed, ledger=ledger)


def test_existing_structural_qualifier_consumes_exact_result():
    record, _ = evaluate()
    evaluation = candle(20, "98", "102", "97", "101")
    candidates = StructuralBreakQualifier().qualify(
        state_before=state(),
        candle={"id": evaluation.id, "t": int(evaluation.open_time.timestamp() * 1000),
                "h": evaluation.high, "l": evaluation.low, "c": evaluation.close,
                "is_closed": True},
        qualifying_displacement=record,
    )
    assert len(candidates) == 1 and candidates[0].id == record.structural_candidate_id
    assert candidates[0].qualifying_displacement


def test_policy_provenance_and_dependency_scope_are_explicit():
    policy = MechanicalDisplacementPolicy.owner_mechanical_v1(calculation_version="calc-v1")
    assert policy.provenance == "OWNER_AUTHORED_PENDING_CANONICAL_VALIDATION"
    module = __import__("strategy.trading_brain.p20_displacement", fromlist=["x"])
    text = open(module.__file__, encoding="utf-8").read()
    for forbidden in ("p23_liquidity", "p11_cisd", "p25_fvg", "p27_setup", "p29_"):
        assert forbidden not in text
