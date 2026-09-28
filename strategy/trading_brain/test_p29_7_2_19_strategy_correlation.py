from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_15_strategy_aggregation import StrategyPeriodReturnObservation
from strategy.trading_brain.p29_7_2_19_strategy_correlation import *


AS_OF = 100


def scope(**changes):
    return replace(CorrelationScope(
        "correlation-scope", "A", "B", "BTC", "ETH", "1m", "5m",
        SetupModel.CONTINUATION, SetupModel.REVERSAL_1,
        StructuralRegime.BULLISH, StructuralRegime.BEARISH,
        PeriodType.DAILY, "UTC", "source-v1", "strategy-calc-v1",
        "correlation-calc-v1", "history-v1",
    ), **changes)


def observation(strategy, end, value, **changes):
    is_a = strategy == "A"
    return replace(StrategyPeriodReturnObservation(
        id=f"observation-{strategy}-{end}", strategy_id=strategy,
        symbol="BTC" if is_a else "ETH", timeframe="1m" if is_a else "5m",
        setup_model=SetupModel.CONTINUATION if is_a else SetupModel.REVERSAL_1,
        direction=StructuralRegime.BULLISH if is_a else StructuralRegime.BEARISH,
        period_type=PeriodType.DAILY, period_id=f"period-{strategy}-{end}",
        period_start=end - 10, period_end=end, account_timezone="UTC",
        net_pnl=Decimal(value), net_r=Decimal(value), trade_count=0 if Decimal(value) == 0 else 1,
        finalized=True, finalized_time=end, source_version="source-v1",
        calculation_version="strategy-calc-v1", historical_version="history-v1",
        source_period_snapshot_id=f"period-snapshot-{strategy}-{end}",
        source_trade_ids=(), source_accounting_ids=(),
    ), **changes)


def ordered(*items):
    return tuple(sorted(items, key=lambda item: (item.period_end, item.strategy_id, item.id)))


def series(values_a, values_b, ends=None):
    ends = ends or tuple(range(10, 10 * (len(values_a) + 1), 10))
    return ordered(
        *(observation("A", end, value) for end, value in zip(ends, values_a)),
        *(observation("B", end, value) for end, value in zip(ends, values_b)),
    )


def calculate(items, *, selected_scope=None, as_of=AS_OF, history=CorrelationHistory()):
    return StrategyCorrelationEngine().calculate(
        scope=selected_scope or scope(), observations=items, as_of_time=as_of, history=history,
    )


def test_perfect_positive_identical_series_and_exact_sample_intermediates():
    record = calculate(series(("1", "2", "3"), ("2", "4", "6"))).record
    assert record.status == CorrelationStatus.VALID
    assert record.classification == CorrelationClassification.POSITIVE
    assert record.correlation == Decimal("1") and record.sample_size == 3
    assert record.mean_a == 2 and record.mean_b == 4
    assert record.covariance == 2 and record.variance_a == 1 and record.variance_b == 4
    assert record.standard_deviation_a == 1 and record.standard_deviation_b == 2


def test_perfect_negative_and_valid_exact_zero_relationships():
    negative = calculate(series(("1", "2", "3"), ("3", "2", "1"))).record
    assert negative.correlation == -1 and negative.classification == CorrelationClassification.NEGATIVE
    zero = calculate(series(("-1", "0", "1"), ("1", "-2", "1"))).record
    assert zero.correlation == 0 and zero.classification == CorrelationClassification.ZERO
    assert zero.status == CorrelationStatus.VALID


def test_empty_and_single_observation_are_null_insufficient_samples():
    empty = calculate(()).record
    assert empty.sample_size == 0 and empty.correlation is None
    assert empty.mean_a is empty.mean_b is None and empty.status == CorrelationStatus.INSUFFICIENT_SAMPLE
    single = calculate(series(("1",), ("2",))).record
    assert single.sample_size == 1 and single.mean_a == 1 and single.mean_b == 2
    assert single.covariance is single.variance_a is single.correlation is None
    assert single.status == CorrelationStatus.INSUFFICIENT_SAMPLE


def test_constant_series_is_null_not_zero_or_infinity():
    record = calculate(series(("1", "1", "1"), ("1", "2", "3"))).record
    assert record.status == CorrelationStatus.UNDEFINED_CONSTANT_SERIES
    assert record.correlation is None and record.classification is None
    assert record.variance_a == 0 and record.standard_deviation_a == 0
    both = calculate(series(("0", "0"), ("0", "0"))).record
    assert both.status == CorrelationStatus.UNDEFINED_CONSTANT_SERIES and both.correlation is None


def test_missing_periods_use_intersection_and_genuine_zero_is_retained():
    items = ordered(
        observation("A", 10, "1"), observation("A", 20, "0"), observation("A", 30, "-1"),
        observation("B", 10, "2"), observation("B", 30, "-2"), observation("B", 40, "9"),
    )
    record = calculate(items).record
    assert record.sample_size == 2 and record.source_period_end_ids == (10, 30)
    assert record.missing_period_end_ids_a == (40,) and record.missing_period_end_ids_b == (20,)
    assert tuple(pair.net_r_a for pair in record.aligned_pairs) == (Decimal("1"), Decimal("-1"))
    zero_items = series(("0", "1"), ("0", "2"))
    zero_record = calculate(zero_items).record
    assert zero_record.sample_size == 2 and zero_record.aligned_pairs[0].net_r_a == 0


def test_exact_period_boundaries_timezone_and_period_type_must_align():
    a = observation("A", 20, "1")
    b = observation("B", 20, "2", period_start=9)
    assert calculate(ordered(a, b)).error.reason == "CORRELATION_PERIOD_ALIGNMENT_INVALID"
    assert calculate((replace(a, account_timezone="America/Phoenix"),), selected_scope=scope(account_timezone="UTC")).error.reason == "CORRELATION_PERIOD_OR_VERSION_MISMATCH"
    assert calculate((replace(a, period_type=PeriodType.MONTHLY),)).error.reason == "CORRELATION_PERIOD_OR_VERSION_MISMATCH"


def test_pair_order_is_canonical_and_series_dimensions_are_isolated():
    assert calculate((), selected_scope=scope(strategy_a_id="B", strategy_b_id="A")).error.reason == "CORRELATION_PAIR_ORDER_INVALID"
    source = observation("A", 10, "1")
    for changed in (
        replace(source, symbol="SOL"), replace(source, timeframe="15m"),
        replace(source, setup_model=SetupModel.REVERSAL_1), replace(source, direction=StructuralRegime.BEARISH),
    ):
        assert calculate((changed,)).error.reason == "CORRELATION_SERIES_SCOPE_MISMATCH"
    assert calculate((observation("C", 10, "1"),)).error.reason == "CORRELATION_STRATEGY_PAIR_MISMATCH"


def test_point_in_time_excludes_future_observations_without_lookahead():
    items = series(("1", "2", "3"), ("2", "4", "6"), ends=(10, 20, 110))
    record = calculate(items, as_of=100).record
    assert record.sample_size == 2 and record.source_period_end_ids == (10, 20)
    assert record.future_excluded_observation_ids == ("observation-A-110", "observation-B-110")
    assert record.correlation == 1


def test_nonfinal_future_chronology_nonfinite_and_versions_fail_closed():
    base = observation("A", 10, "1")
    assert calculate((replace(base, finalized=False),)).error.reason == "NON_FINAL_PERIOD_RETURN_OBSERVATION"
    assert calculate((replace(base, finalized_time=9),)).error.reason == "CORRELATION_PERIOD_CHRONOLOGY_INVALID"
    assert calculate((replace(base, net_r=Decimal("NaN")),)).error.reason == "NON_FINITE_CORRELATION_INPUT"
    for changed in (
        replace(base, source_version="source-v2"), replace(base, calculation_version="strategy-calc-v2"),
        replace(base, historical_version="history-v2"),
    ):
        assert calculate((changed,)).error.reason == "CORRELATION_PERIOD_OR_VERSION_MISMATCH"


def test_duplicate_canonical_period_or_observation_identity_fails_closed():
    first = observation("A", 10, "1")
    duplicate_period = replace(first, id="another-observation")
    assert calculate(ordered(first, duplicate_period)).error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    duplicate_id = replace(observation("B", 10, "2"), id=first.id)
    assert calculate(ordered(first, duplicate_id)).error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_input_order_is_strict_and_sources_and_intermediates_are_auditable():
    items = series(("1", "2"), ("2", "4"))
    assert calculate(tuple(reversed(items))).error.reason == "CORRELATION_OBSERVATION_ORDER_INVALID"
    record = calculate(items).record
    assert record.source_observation_a_ids == ("observation-A-10", "observation-A-20")
    assert record.source_observation_b_ids == ("observation-B-10", "observation-B-20")
    assert tuple(pair.sequence for pair in record.aligned_pairs) == (1, 2)


def test_missing_inputs_idempotent_replay_conflicts_and_immutability():
    assert StrategyCorrelationEngine().calculate(scope=scope(), observations=None, as_of_time=AS_OF).error.reason == "REQUIRED_CORRELATION_INPUT_MISSING"
    items = series(("1", "2"), ("2", "4"))
    first = calculate(items)
    replay = calculate(items, history=first.history)
    assert replay.record == first.record and replay.history == first.history
    changed = series(("1", "2", "3"), ("2", "4", "6"))
    conflict = calculate(changed, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert conflict.error.reason == "CONFLICTING_CORRELATION_RECORD"
    with pytest.raises(FrozenInstanceError):
        first.record.correlation = Decimal("0")
