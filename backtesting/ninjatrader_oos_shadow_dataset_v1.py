"""Verify independent daily NinjaTrader chains for multi-day shadow research only."""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import json

from backtesting.databento_research_dataset_v1 import derive_complete_m5
from backtesting.futures_canonical_lane_v1 import FuturesCanonicalMarket
from backtesting.market_data import GapPolicy, normalize_historical_candle, validate_dataset
from backtesting.ninjatrader_closed_bar_dataset_v1 import (
    NinjaTraderClosedBarDatasetV1, RECORD_VERSION)
from futures_data.sessions import IntervalClassification, SessionCalendar

VERSION = "ninjatrader-oos-shadow-dataset-v1"
INSTRUMENTS = {FuturesCanonicalMarket.ES: "MES SEP26",
               FuturesCanonicalMarket.NQ: "MNQ SEP26"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode()


def utc(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError("UTC timestamp required")
    return parsed


def read_ninjatrader_oos_shadow_days(root, *, market, days, as_of):
    if (not isinstance(market, FuturesCanonicalMarket) or not isinstance(days, tuple)
            or not days or tuple(sorted(set(days))) != days):
        raise ValueError("explicit market and ordered distinct days required")
    if as_of.tzinfo is None or as_of.utcoffset() != timedelta(0):
        raise ValueError("UTC as_of required")
    instrument = INSTRUMENTS[market]; records = []; source_hashes = []
    for day in days:
        path = Path(root) / market.value / f"{day}.jsonl"
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"plain daily archive missing: {market.value} {day}")
        raw = path.read_bytes(); source_hashes.append(sha256(raw).hexdigest())
        previous = "0" * 64; prior_close = None
        for line in raw.splitlines():
            document = json.loads(line); digest = document.pop("record_sha256")
            if (document.get("schema_version") != RECORD_VERSION
                    or document.get("previous_record_sha256") != previous
                    or sha256(canonical(document)).hexdigest() != digest
                    or document.get("market") != market.value
                    or document.get("instrument") != instrument
                    or document.get("paper_only") is not True
                    or document.get("trading_authority") is not False):
                raise ValueError("daily closed-bar chain invalid")
            opened, closed = utc(document["open_time_utc"]), utc(document["close_time_utc"])
            if closed > as_of or closed - opened != timedelta(minutes=1):
                raise ValueError("daily closed-bar chronology invalid")
            if prior_close is not None and opened != prior_close:
                cursor = prior_close
                while cursor < opened:
                    if SessionCalendar().classify(cursor) is IntervalClassification.OPEN:
                        raise ValueError("daily chain contains an open-session gap")
                    cursor += timedelta(minutes=1)
            records.append((opened, closed, *(Decimal(document[x]) for x in
                ("open", "high", "low", "close")), Decimal(document["volume"])))
            previous, prior_close = digest, closed
    records.sort(key=lambda x: x[0])
    if len({x[0] for x in records}) != len(records):
        raise ValueError("multi-day archive overlaps")
    for first, second in zip(records, records[1:]):
        cursor = first[1]
        while cursor < second[0]:
            if SessionCalendar().classify(cursor) is IntervalClassification.OPEN:
                raise ValueError("multi-day archive contains an open-session gap")
            cursor += timedelta(minutes=1)
    dataset_id = sha256((VERSION + market.value + "".join(days)
                         + "".join(source_hashes)).encode()).hexdigest()
    one_minute = tuple(normalize_historical_candle({"symbol": market.value,
        "timeframe": "1m", "open_time": x[0], "close_time": x[1], "open": x[2],
        "high": x[3], "low": x[4], "close": x[5], "volume": x[6], "is_closed": True},
        dataset_id=dataset_id, schema_version="historical-candle-v1",
        source="ninjatrader-oos-shadow", exchange="XCME") for x in records)
    candles = tuple(sorted(one_minute + derive_complete_m5(one_minute,
        dataset_id=dataset_id), key=lambda x: (x.open_time, x.timeframe.value, x.id)))
    dataset = validate_dataset(candles, dataset_id=dataset_id,
        schema_version="historical-candle-v1", source="ninjatrader-oos-shadow",
        exchange="XCME", gap_policy=GapPolicy.RECORD, validation_time=as_of)
    combined_head = sha256("".join(source_hashes).encode()).hexdigest()
    return NinjaTraderClosedBarDatasetV1(market, instrument, days[-1], dataset,
        combined_head, len(candles), smoke_replay_eligible=True,
        training_validation_eligible=False, untouched_oos_eligible=True,
        advisory_only=True, paper_execution_permitted=False,
        live_trading_permitted=False, trading_authority=False)
