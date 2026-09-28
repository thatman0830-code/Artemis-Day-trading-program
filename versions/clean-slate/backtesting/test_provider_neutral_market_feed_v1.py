from datetime import datetime, timezone

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.provider_neutral_market_feed_v1 import read_provider_neutral_replay


def test_databento_replay_is_exposed_as_non_live_provider_neutral_feed():
    feed = read_provider_neutral_replay("data/databento_recovery_staging",
        market=FuturesCanonicalMarket.ES,
        days=("2026-09-09", "2026-09-10"),
        as_of=datetime(2026, 9, 11, tzinfo=timezone.utc))
    assert feed.bars and feed.live is False and feed.trading_authority is False
    assert feed.market is FuturesCanonicalMarket.ES
