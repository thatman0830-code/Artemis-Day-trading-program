from backtesting.databento_live_bar_aggregator_v1 import aggregate_trades
from backtesting.databento_live_canonicalizer_v1 import canonicalize_bars

def test_live_bars_normalize_to_canonical_candles():
    bars = aggregate_trades([{"symbol":"ESU6","action":"T","price_raw":7607000000000,"size":1,"ts_event":"2026-09-15T05:48:07+00:00"}])
    candles = canonicalize_bars(bars)
    assert len(candles) == 1
    assert candles[0].close_time - candles[0].open_time == __import__('datetime').timedelta(minutes=1)
    assert candles[0].is_closed is True
