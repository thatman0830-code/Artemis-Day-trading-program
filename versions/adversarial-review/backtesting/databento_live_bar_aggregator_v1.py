"""Deterministic one-minute OHLCV aggregation for captured Databento trades."""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal

VERSION = "databento-live-bar-aggregator-v1"

def aggregate_trades(records: list[dict]) -> list[dict]:
    buckets = defaultdict(list)
    for r in records:
        if r.get("action") != "T" or not r.get("symbol"):
            continue
        ts = datetime.fromisoformat(r["ts_event"])
        if ts.tzinfo is None:
            raise ValueError("trade timestamp must be timezone-aware")
        price = Decimal(int(r["price_raw"])) / Decimal(1_000_000_000)
        size = int(r.get("size", 0))
        if price <= 0 or size < 0:
            raise ValueError("invalid trade price or size")
        minute = ts.astimezone(timezone.utc).replace(second=0, microsecond=0)
        buckets[(r["symbol"], minute)].append((ts, price, size))
    bars = []
    for (symbol, minute), values in sorted(buckets.items(), key=lambda x: x[0]):
        values.sort(key=lambda x: x[0])
        prices = [x[1] for x in values]
        bars.append({"schema_version": VERSION, "symbol": symbol, "open_time": minute.isoformat(),
                     "close_time": (minute + timedelta(minutes=1)).isoformat(),
                     "open": format(prices[0], "f"), "high": format(max(prices), "f"),
                     "low": format(min(prices), "f"), "close": format(prices[-1], "f"),
                     "volume": sum(x[2] for x in values), "trade_count": len(values),
                     "read_only": True, "trading_authority": False})
    return bars
