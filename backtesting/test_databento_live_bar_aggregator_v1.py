from backtesting.databento_live_bar_aggregator_v1 import aggregate_trades

def test_aggregates_trade_prices_into_minute_ohlcv():
    bars = aggregate_trades([
        {"symbol":"ESU6","action":"T","price_raw":7607000000000,"size":1,"ts_event":"2026-09-15T05:48:07.000000+00:00"},
        {"symbol":"ESU6","action":"T","price_raw":7607250000000,"size":2,"ts_event":"2026-09-15T05:48:30.000000+00:00"},
    ])
    assert bars[0]["open"] == "7607"
    assert bars[0]["high"] == "7607.25"
    assert bars[0]["close"] == "7607.25"
    assert bars[0]["volume"] == 3
    assert bars[0]["trading_authority"] is False
