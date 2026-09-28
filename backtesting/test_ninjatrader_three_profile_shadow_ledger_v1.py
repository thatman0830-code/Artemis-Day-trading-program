from datetime import datetime, timedelta, timezone
from decimal import Decimal

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket as Market
from backtesting.ninjatrader_shadow_profile_comparison_v1 import CompletedShadowTradeV1, ShadowSide
from backtesting.ninjatrader_three_profile_shadow_ledger_v1 import build_three_profile_shadow_ledgers

T = datetime(2026, 9, 14, tzinfo=timezone.utc)


def trade(i, market=Market.ES, exit_price="110"):
    return CompletedShadowTradeV1(str(i) * 64, market, ShadowSide.LONG,
        T + timedelta(minutes=i * 2), T + timedelta(minutes=i * 2 + 1),
        Decimal("100"), Decimal("95"), Decimal(exit_price), "r" * 64)


def test_empty_builds_three_isolated_non_executable_ledgers():
    ledgers = build_three_profile_shadow_ledgers(trades=(), evaluated_at=T)
    assert len(ledgers) == 3 and len({x.ledger_id for x in ledgers}) == 3
    assert all(not x.entries and x.starting_equity_usd == x.ending_equity_usd for x in ledgers)
    assert all(x.paper_execution_permitted is x.trading_authority is False for x in ledgers)


def test_identical_signal_prices_are_preserved_with_profile_specific_quantity():
    ledgers = build_three_profile_shadow_ledgers(trades=(trade(1, Market.NQ),),
                                                 evaluated_at=T + timedelta(hours=1))
    assert [x.entries[0].signal_id for x in ledgers] == ["1" * 64] * 3
    assert [x.entries[0].entry_price for x in ledgers] == [Decimal("100")] * 3
    assert [x.entries[0].quantity for x in ledgers] == [1, 2, 4]


def test_session_loss_limit_stops_only_that_profile_ledger():
    trades = tuple(trade(i, Market.NQ, "90") for i in range(50))
    ledgers = build_three_profile_shadow_ledgers(trades=trades,
                                                 evaluated_at=T + timedelta(hours=3))
    assert all(x.session_limit_reached for x in ledgers)
    assert all(len(x.entries) < 50 and x.skipped_signal_ids for x in ledgers)
