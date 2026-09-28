from dataclasses import FrozenInstanceError, replace
from decimal import Decimal

import pytest

from strategy.trading_brain.p29_7_1_trade_accounting import TradeResult
from strategy.trading_brain.p29_7_2_1_trade_classification_count import AnalyticsErrorCode
from strategy.trading_brain.p29_7_2_9_period_statistics import PeriodType
from strategy.trading_brain.p29_7_2_17_portfolio_attribution import *
from strategy.trading_brain import test_p29_7_2_16_portfolio_aggregation as p16


def scope(**changes):
    return replace(AttributionScope(
        "attribution-scope", "portfolio", "v1", PeriodType.DAILY, "UTC",
        "source-v1", "portfolio-calc-v1", "attribution-calc-v1", "history-v1",
    ), **changes)


def calculate(portfolio, *, selected_scope=None, as_of=p16.AS_OF, history=AttributionHistory()):
    return PortfolioAttributionEngine().calculate(
        scope=selected_scope or scope(), portfolio=portfolio, as_of_time=as_of, history=history,
    )


def normal_portfolio():
    a = p16.strategy("A", (p16.trade("A", TradeResult.WIN, "a", p16.BASE + 2, "10", "1"),), (0,))
    b = p16.strategy("B", (p16.trade("B", TradeResult.LOSS, "b", p16.BASE + 1, "-4", "-0.4"),), (0,))
    return p16.calculate((b, a)).snapshot


def test_normal_multi_strategy_attribution_conserves_exact_signed_results():
    snapshot = calculate(normal_portfolio()).snapshot
    assert snapshot.effective_strategy_ids == ("A", "B")
    assert tuple(row.strategy_id for row in snapshot.strategy_attributions) == ("A", "B")
    assert tuple(row.net_pnl_contribution for row in snapshot.strategy_attributions) == (Decimal("10"), Decimal("-4"))
    assert snapshot.portfolio_net_pnl == snapshot.attributed_net_pnl == Decimal("6")
    assert snapshot.portfolio_net_r == snapshot.attributed_net_r == Decimal("0.6")
    assert (snapshot.net_pnl_conservation_delta, snapshot.net_r_conservation_delta) == (0, 0)


def test_single_member_and_empty_portfolios_follow_exact_zero_semantics():
    item = p16.strategy("A", (p16.trade("A", TradeResult.WIN, "a", p16.BASE + 1, "5", "0.5"),))
    single = p16.calculate((item,), portfolio_definition=p16.definition(("A",))).snapshot
    assert calculate(single).snapshot.strategy_attributions[0].net_pnl_contribution == 5
    empty = p16.calculate((), portfolio_definition=p16.definition(())).snapshot
    result = calculate(empty).snapshot
    assert result.strategy_attributions == () and result.attributed_trade_count == 0
    assert result.attributed_net_pnl == result.attributed_net_r == 0


def test_exclusion_wins_and_membership_version_is_preserved():
    a = p16.strategy("A", (p16.trade("A", TradeResult.WIN, "a", p16.BASE + 1, "1", "0.1"),))
    b = p16.strategy("B", (p16.trade("B", TradeResult.WIN, "b", p16.BASE + 1, "100", "10"),))
    portfolio = p16.calculate((a, b), portfolio_definition=p16.definition(("A", "B"), ("B",))).snapshot
    snapshot = calculate(portfolio).snapshot
    assert snapshot.effective_strategy_ids == ("A",) and snapshot.excluded_strategy_ids == ("B",)
    assert calculate(portfolio, selected_scope=scope(portfolio_version="v2")).error.reason == "PORTFOLIO_ATTRIBUTION_SCOPE_OR_VERSION_MISMATCH"


def test_aligned_missing_and_genuine_zero_period_facts_are_preserved_not_rebuilt():
    portfolio = p16.calculate((p16.strategy("A", (), (0, 1)), p16.strategy("B", (), (0,)))).snapshot
    snapshot = calculate(portfolio).snapshot
    assert tuple(row.portfolio_period_observation_id for row in snapshot.period_references) == tuple(row.id for row in portfolio.period_observations)
    assert snapshot.missing_period_ends == (p16.BASE + 2 * p16.DAY,)
    assert snapshot.zero_return_period_ids == portfolio.zero_return_period_ids
    assert snapshot.period_references[0].portfolio_net_r == 0


def test_positive_negative_zero_ties_and_nonpositive_equity_do_not_create_ratios_or_rankings():
    portfolio = normal_portfolio()
    tied = tuple(replace(row, gross_pnl=Decimal("3"), net_pnl=Decimal("3"), gross_r=Decimal("0.3"), net_r=Decimal("0.3")) for row in portfolio.strategy_contributions)
    portfolio = replace(portfolio, strategy_contributions=tied, portfolio_gross_pnl=Decimal("6"), portfolio_net_pnl=Decimal("6"), portfolio_gross_r=Decimal("0.6"), portfolio_net_r=Decimal("0.6"), starting_equity=Decimal("0"), ending_equity=Decimal("-1"))
    rows = calculate(portfolio).snapshot.strategy_attributions
    assert tuple((row.sequence, row.strategy_id, row.net_pnl_contribution) for row in rows) == ((1, "A", Decimal("3")), (2, "B", Decimal("3")))
    assert not hasattr(rows[0], "rank") and not hasattr(rows[0], "contribution_share")


def test_point_in_time_finality_scope_and_version_isolation_fail_closed():
    portfolio = normal_portfolio()
    assert calculate(portfolio, as_of=p16.AS_OF - 1).error.reason == "PORTFOLIO_ATTRIBUTION_SOURCE_NON_FINAL_OR_STALE"
    for changed in (
        scope(account_timezone="America/Phoenix"), scope(period_type=PeriodType.MONTHLY),
        scope(source_version="v2"), scope(portfolio_calculation_version="v2"), scope(historical_version="v2"),
    ):
        assert calculate(portfolio, selected_scope=changed).error.reason == "PORTFOLIO_ATTRIBUTION_SCOPE_OR_VERSION_MISMATCH"


def test_membership_order_and_source_lineage_are_strict():
    portfolio = normal_portfolio()
    invalid = replace(portfolio, strategy_contributions=tuple(reversed(portfolio.strategy_contributions)))
    assert calculate(invalid).error.reason == "PORTFOLIO_MEMBERSHIP_OR_ORDER_MISMATCH"
    invalid = replace(portfolio, source_strategy_snapshot_ids=tuple(reversed(portfolio.source_strategy_snapshot_ids)))
    assert calculate(invalid).error.reason == "PORTFOLIO_STRATEGY_LINEAGE_MISMATCH"


def test_duplicate_trade_or_accounting_lineage_fails_with_data_integrity_error():
    portfolio = normal_portfolio()
    first, second = portfolio.strategy_contributions
    second = replace(second, source_trade_ids=first.source_trade_ids, source_accounting_ids=first.source_accounting_ids)
    result = calculate(replace(portfolio, strategy_contributions=(first, second)))
    assert result.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR


def test_conservation_invalid_nonfinite_and_missing_inputs_fail_closed():
    portfolio = normal_portfolio()
    first, second = portfolio.strategy_contributions
    invalid = replace(portfolio, strategy_contributions=(replace(first, net_pnl=Decimal("11")), second))
    assert calculate(invalid).error.reason == "ATTRIBUTION_CONSERVATION_INVALID"
    invalid = replace(portfolio, strategy_contributions=(replace(first, net_r=Decimal("NaN")), second))
    assert calculate(invalid).error.reason == "NON_FINITE_ATTRIBUTION_INPUT"
    assert PortfolioAttributionEngine().calculate(scope=scope(), portfolio=None, as_of_time=p16.AS_OF).error.reason == "REQUIRED_ATTRIBUTION_INPUT_MISSING"


def test_period_order_future_and_zero_period_lineage_fail_closed():
    portfolio = p16.calculate((p16.strategy("A", (), (0, 1)), p16.strategy("B", (), (0, 1)))).snapshot
    assert calculate(replace(portfolio, period_observations=tuple(reversed(portfolio.period_observations)))).error.reason == "PORTFOLIO_PERIOD_ORDER_INVALID"
    future = replace(portfolio.period_observations[0], finalized_time=p16.AS_OF + 1)
    assert calculate(replace(portfolio, period_observations=(future,) + portfolio.period_observations[1:])).error.reason == "PORTFOLIO_PERIOD_NON_FINAL_OR_FUTURE"
    assert calculate(replace(portfolio, zero_return_period_ids=())).error.reason == "PORTFOLIO_ZERO_PERIOD_LINEAGE_MISMATCH"


def test_idempotent_replay_conflict_prevention_and_immutability():
    portfolio = normal_portfolio()
    first = calculate(portfolio)
    replay = calculate(portfolio, history=first.history)
    assert replay.snapshot == first.snapshot and replay.history == first.history
    conflict = calculate(replace(portfolio, id="different-valid-source-snapshot"), history=first.history)
    assert conflict.error.code == AnalyticsErrorCode.DATA_INTEGRITY_ERROR
    with pytest.raises(FrozenInstanceError):
        first.snapshot.portfolio_net_pnl = Decimal("9")
