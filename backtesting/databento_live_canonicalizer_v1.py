"""Normalize live Databento minute bars into immutable canonical candles."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from backtesting.market_data import HistoricalCandle, CanonicalTimeframe, candle_identity

VERSION = "databento-live-canonicalizer-v1"

def canonicalize_bars(bars: list[dict], *, dataset_id: str = "GLBX.MDP3") -> tuple[HistoricalCandle, ...]:
    result = []
    for b in bars:
        opened = datetime.fromisoformat(b["open_time"])
        closed = datetime.fromisoformat(b["close_time"])
        symbol = str(b["symbol"])
        identity = candle_identity(dataset_id=dataset_id, schema_version="historical-candle-v1",
                                   source="DATABENTO_LIVE", exchange="CME", symbol=symbol,
                                   timeframe=CanonicalTimeframe.M1, open_time=opened, close_time=closed)
        result.append(HistoricalCandle(identity, dataset_id, "historical-candle-v1", "DATABENTO_LIVE", "CME", symbol,
                                       CanonicalTimeframe.M1, opened, closed,
                                       Decimal(b["open"]), Decimal(b["high"]), Decimal(b["low"]), Decimal(b["close"]),
                                       Decimal(b["volume"]), True))
    return tuple(result)
