"""Strict, read-only parser for NinjaTrader minute-bar historical exports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
from pathlib import Path

from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import GapPolicy, HistoricalDataset, normalize_historical_candle, validate_dataset

VERSION = "ninjatrader-historical-export-v1"
INSTRUMENTS = {FuturesCanonicalMarket.ES: "MES 09-26", FuturesCanonicalMarket.NQ: "MNQ 09-26"}


@dataclass(frozen=True)
class NinjaTraderHistoricalExportV1:
    market: FuturesCanonicalMarket
    instrument: str
    source_sha256: str
    dataset: HistoricalDataset
    record_count: int
    earliest_close_utc: datetime
    latest_close_utc: datetime
    historical_replay_eligible: bool = True
    immutable_archive_repair_eligible: bool = False
    advisory_only: bool = True
    paper_execution_permitted: bool = False
    trading_authority: bool = False
    schema_version: str = VERSION


def read_ninjatrader_historical_export(path, *, market, as_of, start_at=None, end_at=None):
    if not isinstance(market, FuturesCanonicalMarket):
        raise TypeError("explicit ES or NQ market required")
    if not isinstance(as_of, datetime) or as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("UTC as_of required")
    for label, value in (("start_at", start_at), ("end_at", end_at)):
        if value is not None and (
            not isinstance(value, datetime)
            or value.tzinfo is None
            or value.utcoffset() != timedelta(0)
        ):
            raise ValueError(f"UTC {label} required")
    if start_at is not None and end_at is not None and start_at > end_at:
        raise ValueError("start_at must not exceed end_at")
    source = Path(path)
    if not source.is_file() or source.is_symlink():
        raise ValueError("plain NinjaTrader export required")
    raw = source.read_bytes()
    if len(raw) > 25_000_000:
        raise ValueError("NinjaTrader export exceeds size limit")
    digest = hashlib.sha256(raw).hexdigest()
    window_identity = "".join(
        value.isoformat() if value is not None else ""
        for value in (start_at, end_at)
    )
    dataset_id = hashlib.sha256(
        (VERSION + market.value + INSTRUMENTS[market] + digest + window_identity).encode()
    ).hexdigest()
    candles = []
    for sequence, line in enumerate(raw.decode("ascii").splitlines()):
        parts = line.split(";")
        if len(parts) != 6:
            raise ValueError("NinjaTrader minute row schema invalid")
        try:
            close_time = datetime.strptime(parts[0], "%Y%m%d %H%M%S").replace(tzinfo=timezone.utc)
            prices = tuple(Decimal(value) for value in parts[1:5])
            volume = Decimal(parts[5])
        except Exception as exc:
            raise ValueError("NinjaTrader minute row value invalid") from exc
        if close_time > as_of or volume < 0 or volume != volume.to_integral_value():
            raise ValueError("NinjaTrader minute row violates closed-bar policy")
        if start_at is not None and close_time < start_at:
            continue
        if end_at is not None and close_time > end_at:
            continue
        if any(price % Decimal("0.25") != 0 for price in prices):
            raise ValueError("NinjaTrader price is off tick")
        opened = close_time - timedelta(minutes=1)
        candle = normalize_historical_candle({"symbol": market.value, "timeframe": "1m", "open_time": opened, "close_time": close_time, "open": prices[0], "high": prices[1], "low": prices[2], "close": prices[3], "volume": volume, "is_closed": True}, dataset_id=dataset_id, schema_version="historical-candle-v1", source="ninjatrader-historical-export", exchange="XCME")
        candles.append(candle)
    if not candles:
        raise ValueError("NinjaTrader export is empty")
    dataset = validate_dataset(tuple(candles), dataset_id=dataset_id, schema_version="historical-candle-v1", source="ninjatrader-historical-export", exchange="XCME", gap_policy=GapPolicy.REJECT, validation_time=as_of)
    return NinjaTraderHistoricalExportV1(market, INSTRUMENTS[market], digest, dataset, len(candles), candles[0].close_time, candles[-1].close_time)
