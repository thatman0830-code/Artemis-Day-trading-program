from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_20_strategy_covariance import *
from strategy.trading_brain import test_p29_7_2_19_strategy_correlation as p19


AS_OF = 100


def member(strategy):
    values = {
        "A": ("BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH),
        "B": ("ETH", "5m", SetupModel.REVERSAL_1, StructuralRegime.BEARISH),
        "C": ("SOL", "15m", SetupModel.CONTINUATION, StructuralRegime.BEARISH),
    }[strategy]
    return CovarianceUniverseMember(strategy, *values)


def universe(strategies=("A", "B"), **changes):
    return replace(CovarianceUniverse(
        "covariance-universe", "v1", tuple(member(item) for item in strategies),
        PeriodType.DAILY, "UTC", "source-v1", "strategy-calc-v1",
        "covariance-calc-v1", "history-v1", CovarianceMode.EXPANDING, None,
    ), **changes)


def observation(strategy, end, value, **changes):
    if strategy in ("A", "B"):
        return p19.observation(strategy, end, value, **changes)
    base = p19.observation("A", end, value)
    return replace(
        base, id=f"observation-{strategy}-{end}", strategy_id=strategy,
        symbol="SOL", timeframe="15m", setup_model=SetupModel.CONTINUATION,
        direction=StructuralRegime.BEARISH, period_id=f"period-{strategy}-{end}",
        source_period_snapshot_id=f"period-snapshot-{strategy}-{end}", **changes,
    )


def ordered(*items):
    return tuple(sorted(items, key=lambda item: (item.period_end, item.strategy_id, item.id)))


def calculate(items, *, selected_universe=None, as_of=AS_OF, history=CovarianceHistory()):
    return StrategyCovarianceEngine().calculate(
        universe=selected_universe or universe(), observations=items, as_of_time=as_of, history=history,
    )


def pair(matrix, a, b):
    key = tuple(sorted((a, b)))
    return next(item for item in matrix.covariance_records if (item.strategy_a_id, item.strategy_b_id) == key)


def test_exact_sample_covariance_diagonal_variance_and_symmetry():
    items = ordered(
        *(observation("A", end, value) for end, value in zip((10, 20, 30), ("1", "2", "3"))),
        *(observation("B", end, value) for end, value in zip((10, 20, 30), ("2", "4", "6"))),
    )
    matrix = calculate(items).matrix
    assert pair(matrix, "A", "B").covariance == 2
    assert pair(matrix, "A", "A").covariance == pair(matrix, "A", "A").variance_a == 1
    assert pair(matrix, "B", "B").covariance == pair(matrix, "B", "B").variance_a == 4
    assert matrix.universe_members == universe().members
    assert pair(matrix, "A", "B").aligned_pairs[0].period_a_id == "period-A-10"
    assert pair(matrix, "A", "B").aligned_pairs[0].source_period_snapshot_b_id == "period-snapshot-B-10"
    assert matrix.covariance_cells[1].covariance == matrix.covariance_cells[2].covariance == 2
    assert matrix.covariance_cells[1].covariance_record_id == matrix.covariance_cells[2].covariance_record_id


def test_positive_negative_zero_and_constant_series_covariance_are_valid():
    positive = ordered(*(observation("A", e, v) for e, v in ((10, "1"), (20, "2"), (30, "3"))), *(observation("B", e, v) for e, v in ((10, "2"), (20, "4"), (30, "6"))))
    assert pair(calculate(positive).matrix, "A", "B").covariance > 0
    negative = ordered(*(observation("A", e, v) for e, v in ((10, "1"), (20, "2"), (30, "3"))), *(observation("B", e, v) for e, v in ((10, "3"), (20, "2"), (30, "1"))))
    assert pair(calculate(negative).matrix, "A", "B").covariance < 0
    zero = ordered(*(observation("A", e, "1") for e in (10, 20, 30)), *(observation("B", e, v) for e, v in ((10, "-1"), (20, "0"), (30, "1"))))
    record = pair(calculate(zero).matrix, "A", "B")
    assert record.covariance == 0 and record.status == CovarianceStatus.VALID
    assert record.variance_a == 0


def test_empty_universe_and_single_strategy_matrix_semantics():
    empty = calculate((), selected_universe=universe(())).matrix
    assert empty.strategy_ids == empty.covariance_records == empty.covariance_cells == ()
    assert empty.complete
    single_empty = calculate((), selected_universe=universe(("A",))).matrix
    assert len(single_empty.covariance_records) == len(single_empty.covariance_cells) == 1
    assert single_empty.covariance_cells[0].diagonal and single_empty.covariance_cells[0].covariance is None
    single = calculate(ordered(observation("A", 10, "1"), observation("A", 20, "3")), selected_universe=universe(("A",))).matrix
    assert single.covariance_cells[0].covariance == Decimal("2")


def test_insufficient_and_unequal_pairwise_overlap_keep_complete_null_cells():
    items = ordered(
        *(observation("A", e, v) for e, v in ((10, "1"), (20, "2"), (30, "3"))),
        *(observation("B", e, v) for e, v in ((10, "2"), (30, "6"))),
        *(observation("C", e, v) for e, v in ((20, "4"), (30, "5"))),
    )
    matrix = calculate(items, selected_universe=universe(("A", "B", "C"))).matrix
    assert len(matrix.covariance_records) == 6 and len(matrix.covariance_cells) == 9 and matrix.complete
    assert pair(matrix, "A", "B").observation_count == 2
    assert pair(matrix, "A", "C").observation_count == 2
    bc = pair(matrix, "B", "C")
    assert bc.observation_count == 1 and bc.covariance is None
    assert bc.status == CovarianceStatus.INSUFFICIENT_OBSERVATIONS


def test_missing_periods_are_not_filled_and_real_zero_is_observed():
    items = ordered(
        observation("A", 10, "0"), observation("A", 20, "1"), observation("A", 30, "2"),
        observation("B", 10, "0"), observation("B", 30, "4"), observation("B", 40, "8"),
    )
    record = pair(calculate(items).matrix, "A", "B")
    assert record.observation_count == 2
    assert tuple(item.period_end for item in record.aligned_pairs) == (10, 30)
    assert record.aligned_pairs[0].net_r_a == record.aligned_pairs[0].net_r_b == 0
    assert record.missing_period_end_ids_a == (40,) and record.missing_period_end_ids_b == (20,)


def test_canonical_universe_row_column_and_pair_ordering():
    matrix = calculate((), selected_universe=universe(("A", "B", "C"))).matrix
    assert matrix.strategy_ids == ("A", "B", "C")
    assert tuple((item.strategy_a_id, item.strategy_b_id) for item in matrix.covariance_records) == (("A", "A"), ("A", "B"), ("A", "C"), ("B", "B"), ("B", "C"), ("C", "C"))
    assert tuple((cell.row_strategy_id, cell.column_strategy_id) for cell in matrix.covariance_cells) == tuple((a, b) for a in matrix.strategy_ids for b in matrix.strategy_ids)
    assert calculate((), selected_universe=universe(("B", "A"))).error.reason == "COVARIANCE_UNIVERSE_ORDER_INVALID"


def test_full_history_expanding_and_explicit_rolling_modes():
    items = ordered(*(observation("A", e, v) for e, v in ((10, "1"), (20, "2"), (30, "9"))), *(observation("B", e, v) for e, v in ((10, "2"), (20, "4"), (30, "3"))))
    rolling_universe = universe(calculation_mode=CovarianceMode.ROLLING, window_size=2)
    rolling = pair(calculate(items, selected_universe=rolling_universe).matrix, "A", "B")
    assert tuple(item.period_end for item in rolling.aligned_pairs) == (20, 30)
    assert calculate(items, selected_universe=universe(calculation_mode=CovarianceMode.FULL_HISTORY)).matrix.calculation_mode == CovarianceMode.FULL_HISTORY
    assert calculate((), selected_universe=universe(calculation_mode=CovarianceMode.ROLLING, window_size=1)).error.reason == "COVARIANCE_WINDOW_INVALID"
    assert calculate((), selected_universe=universe(window_size=2)).error.reason == "COVARIANCE_WINDOW_INVALID"


def test_point_in_time_future_exclusion_finality_and_chronology():
    items = ordered(observation("A", 10, "1"), observation("B", 10, "2"), observation("A", 110, "3"), observation("B", 110, "6"))
    matrix = calculate(items, as_of=100).matrix
    assert pair(matrix, "A", "B").observation_count == 1
    assert matrix.future_excluded_observation_ids == ("observation-A-110", "observation-B-110")
    base = observation("A", 10, "1")
    assert calculate((replace(base, finalized=False),)).error.reason == "NON_FINAL_PERIOD_RETURN_OBSERVATION"
    assert calculate((replace(base, finalized_time=9),)).error.reason == "COVARIANCE_PERIOD_CHRONOLOGY_INVALID"


def test_scope_versions_alignment_nonfinite_membership_and_order_fail_closed():
    base = observation("A", 10, "1")
    assert calculate((replace(base, symbol="SOL"),)).error.reason == "COVARIANCE_SERIES_SCOPE_MISMATCH"
    assert calculate((replace(base, source_version="v2"),)).error.reason == "COVARIANCE_PERIOD_OR_VERSION_MISMATCH"
    assert calculate((replace(base, net_r=Decimal("NaN")),)).error.reason == "NON_FINITE_COVARIANCE_INPUT"
    assert calculate((observation("C", 10, "1"),)).error.reason == "COVARIANCE_UNIVERSE_MEMBERSHIP_MISMATCH"
    items = ordered(observation("A", 10, "1"), observation("B", 10, "2", period_start=1))
    assert calculate(items).error.reason == "COVARIANCE_PERIOD_ALIGNMENT_INVALID"
    valid = ordered(observation("A", 10, "1"), observation("B", 10, "2"))
    assert calculate(tuple(reversed(valid))).error.reason == "COVARIANCE_OBSERVATION_ORDER_INVALID"


def test_duplicate_observations_and_incomplete_historical_matrix_fail_closed():
    first = observation("A", 10, "1")
    assert calculate(ordered(first, replace(first, id="duplicate"))).error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    valid = calculate(ordered(observation("A", 10, "1"), observation("A", 20, "2")), selected_universe=universe(("A",)))
    corrupt = replace(valid.matrix, covariance_cells=(), complete=False)
    result = calculate((), selected_universe=universe(("A",)), history=CovarianceHistory((corrupt,)))
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert result.error.reason == "COVARIANCE_MATRIX_INCOMPLETE"


def test_idempotent_replay_conflicts_and_immutable_upstream_and_matrix():
    items = ordered(observation("A", 10, "1"), observation("A", 20, "2"), observation("B", 10, "2"), observation("B", 20, "4"))
    original = items
    first = calculate(items)
    replay = calculate(items, history=first.history)
    assert replay.matrix == first.matrix and replay.history == first.history and items == original
    changed = ordered(*items, observation("A", 30, "3"), observation("B", 30, "6"))
    conflict = calculate(changed, history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    assert conflict.error.reason == "CONFLICTING_COVARIANCE_MATRIX"
    with pytest.raises(FrozenInstanceError):
        first.matrix.complete = False
