from dataclasses import FrozenInstanceError, replace
from decimal import Decimal, localcontext

import pytest

from strategy.trading_brain.p20_structural_classification import StructuralRegime
from strategy.trading_brain.p27_setup_qualification import SetupModel
from strategy.trading_brain.p29_7_2_7_drawdown import DrawdownSnapshot
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodStatisticsSnapshot, PeriodType
from strategy.trading_brain.p29_7_2_11_risk_adjusted_statistics import *


DAY = 86400


def scope(**changes):
    return replace(RiskAdjustedScope("scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "source-v1", "analytics-v1", "history-v1", "UTC"), **changes)


def config(**changes):
    return replace(RiskAdjustedConfiguration("risk-adjusted-config", Decimal(252), Decimal(0), "config-v1"), **changes)


def period(index, *, start=0, trades=0, **changes):
    begin = start + index * DAY
    values = PeriodStatisticsSnapshot(
        f"period-snapshot-{index}", f"period-{index}", "scope", "canonical", "BTC", "1m",
        SetupModel.CONTINUATION, StructuralRegime.BULLISH, "v1", "analytics-v1", "source-v1", "history-v1",
        PeriodType.DAILY, "UTC", begin, begin + DAY, begin + DAY, trades, 0, 0, trades,
        Decimal(0), Decimal(0), None, None, None, (), (), (), (), "ROUND_HALF_UP",
    )
    return replace(values, **changes)


def observation(index, equity, *, start=0, **changes):
    source = period(index, start=start)
    values = DailyEquityObservation(
        f"equity-observation-{index}", source.id, source.period_id, source.period_start, source.period_end,
        source.period_end, Decimal(equity), "equity-curve", f"equity-point-{index}", "source-v1", "history-v1",
    )
    return replace(values, **changes)


def drawdown(as_of, maximum_pct="10", **changes):
    values = DrawdownSnapshot(
        "drawdown", "scope", "canonical", "BTC", "1m", SetupModel.CONTINUATION,
        StructuralRegime.BULLISH, "v1", "analytics-v1", as_of, Decimal(100), 0,
        Decimal(100), Decimal(0), Decimal(0), Decimal(10),
        None if maximum_pct is None else Decimal(maximum_pct), (), (), (), "equity-curve", (), "ROUND_HALF_UP",
    )
    return replace(values, **changes)


def calculate(equities=(), *, periods=None, observations=None, as_of=None, dd="10", history=RiskAdjustedHistory(), **changes):
    periods = tuple(period(i) for i in range(len(equities))) if periods is None else periods
    observations = tuple(observation(i, value) for i, value in enumerate(equities)) if observations is None else observations
    as_of = len(periods) * DAY if as_of is None else as_of
    values = dict(scope=scope(), configuration=config(), trades=(), periods=periods,
                  equity_observations=observations, drawdown=drawdown(as_of, dd), as_of_time=as_of, history=history)
    values.update(changes)
    return RiskAdjustedStatisticsEngine().calculate(**values)


def test_exact_returns_mean_sample_volatility_downside_and_ratios():
    snapshot = calculate(("100", "110", "99")).snapshot
    assert tuple(item.return_value for item in snapshot.returns) == (Decimal("0.1"), Decimal("-0.1"))
    assert snapshot.mean_daily_return == snapshot.annualized_return == 0
    with localcontext() as context:
        context.prec = 34
        assert snapshot.daily_volatility == Decimal("0.02").sqrt()
        assert snapshot.daily_downside_deviation == (Decimal("0.01") / Decimal(2)).sqrt()
    assert snapshot.sharpe_ratio == snapshot.sortino_ratio == Decimal(0)
    assert snapshot.calmar_ratio == Decimal(0)


def test_positive_constant_returns_have_infinite_sharpe_sortino_and_calmar_without_drawdown():
    snapshot = calculate(("100", "110", "121"), dd="0").snapshot
    assert snapshot.sharpe_ratio == Decimal("Infinity")
    assert snapshot.sortino_ratio == Decimal("Infinity")
    assert snapshot.calmar_ratio == Decimal("Infinity")


def test_negative_constant_returns_have_negative_infinite_ratios_at_zero_denominators():
    snapshot = calculate(("100", "90", "81"), dd="0").snapshot
    assert snapshot.sharpe_ratio == Decimal("-Infinity")
    assert snapshot.sortino_ratio < 0  # downside deviation is nonzero
    assert snapshot.calmar_ratio == Decimal("-Infinity")


def test_empty_and_one_return_null_sample_metrics_follow_canonical_boundaries():
    empty = calculate(()).snapshot
    assert empty.return_count == 0 and empty.mean_daily_return is None
    assert empty.sharpe_ratio is empty.sortino_ratio is empty.calmar_ratio is None
    one = calculate(("100", "101")).snapshot
    assert one.mean_daily_return == Decimal("0.01")
    assert one.daily_volatility is one.sharpe_ratio is one.sortino_ratio is None
    assert one.calmar_ratio == Decimal("25.2")


def test_zero_return_zero_denominators_are_null_not_arbitrarily_zero():
    snapshot = calculate(("100", "100", "100"), dd="0").snapshot
    assert snapshot.daily_volatility == snapshot.daily_downside_deviation == 0
    assert snapshot.sharpe_ratio is snapshot.sortino_ratio is snapshot.calmar_ratio is None


def test_maximum_drawdown_percent_points_are_preserved_and_converted_for_calmar():
    snapshot = calculate(("100", "110"), dd="5").snapshot
    assert snapshot.maximum_drawdown_percentage == Decimal("5")
    assert snapshot.maximum_drawdown_fraction == Decimal("0.05")
    assert snapshot.calmar_ratio == Decimal("504")


def test_missing_and_zero_trade_periods_are_not_forward_filled():
    periods = (period(0), period(1), period(2))
    observations = (observation(0, "100"), observation(2, "121"))
    snapshot = calculate(periods=periods, observations=observations).snapshot
    assert snapshot.return_count == 0
    assert snapshot.missing_equity_period_ids == ("period-1",)
    assert snapshot.gap_period_pairs == (("period-0", "period-2"),)
    zero_trade_observations = tuple(observation(i, value) for i, value in enumerate(("100", "100", "110")))
    snapshot = calculate(periods=periods, observations=zero_trade_observations).snapshot
    assert tuple(item.return_value for item in snapshot.returns) == (Decimal(0), Decimal("0.1"))


def test_nonpositive_equity_stops_later_return_computation():
    snapshot = calculate(("100", "0", "50", "60")).snapshot
    assert tuple(item.return_value for item in snapshot.returns) == (Decimal("-1"),)
    assert snapshot.nonpositive_equity_cutoff_observation_id == "equity-observation-1"


def test_future_periods_are_excluded_without_lookahead():
    periods = (period(0), period(1), period(2))
    observations = tuple(observation(i, value) for i, value in enumerate(("100", "110", "1000")))
    snapshot = calculate(periods=periods, observations=observations, as_of=2 * DAY, drawdown=drawdown(2 * DAY)).snapshot
    assert snapshot.return_count == 1 and snapshot.returns[0].return_value == Decimal("0.1")
    assert snapshot.future_excluded_period_ids == ("period-2",)


@pytest.mark.parametrize("field", ["scope", "configuration", "trades", "periods", "equity_observations", "drawdown"])
def test_missing_inputs_fail_closed(field):
    values = dict(scope=scope(), configuration=config(), trades=(), periods=(), equity_observations=(), drawdown=drawdown(0), as_of_time=0)
    values[field] = None
    assert RiskAdjustedStatisticsEngine().calculate(**values).error.reason == "REQUIRED_RISK_ADJUSTED_INPUT_MISSING"


def test_scope_version_timezone_and_nonfinal_inputs_fail_closed():
    assert calculate(("100",), scope=scope(symbol="ETH")).error.reason == "RISK_ADJUSTED_PERIOD_SCOPE_MISMATCH"
    assert calculate(("100",), scope=scope(source_version="source-v2")).error.reason == "RISK_ADJUSTED_PERIOD_VERSION_MISMATCH"
    assert calculate(("100",), scope=scope(account_timezone="America/Phoenix")).error.reason == "RISK_ADJUSTED_PERIOD_VERSION_MISMATCH"
    assert calculate(("100",), periods=(replace(period(0), immutable=False),)).error.reason == "DAILY_PERIOD_INVALID_OR_NON_FINAL"


def test_duplicates_and_nonfinite_values_fail_closed():
    duplicate = observation(1, "101", id="equity-observation-0")
    result = calculate(periods=(period(0), period(1)), observations=(observation(0, "100"), duplicate))
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    result = calculate(("NaN",))
    assert result.error.reason == "EQUITY_OBSERVATION_NON_FINITE"


def test_noncanonical_configuration_and_drawdown_point_in_time_fail_closed():
    assert calculate((), configuration=config(annualization_periods=Decimal(365))).error.reason == "NON_CANONICAL_RISK_ADJUSTED_CONFIGURATION"
    assert calculate((), drawdown=drawdown(1), as_of=0).error.reason == "DRAWDOWN_NOT_FINAL_AT_AS_OF"


def test_idempotent_replay_conflict_prevention_and_immutable_history():
    engine = RiskAdjustedStatisticsEngine()
    args = dict(scope=scope(), configuration=config(), trades=(), periods=(period(0), period(1)),
                equity_observations=(observation(0, "100"), observation(1, "110")), drawdown=drawdown(2 * DAY), as_of_time=2 * DAY)
    first = engine.calculate(**args)
    replay = engine.calculate(**args, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = engine.calculate(**{**args, "equity_observations": (observation(0, "100"), observation(1, "120")), "history": first.history})
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.mean_daily_return = Decimal(0)
