"""Credential-free Coinbase BTC-USD shadow recorder.

This module owns research data only.  It has no account, wallet, transaction-authorization, order,
or execution surface and deliberately writes to an isolated shadow archive.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path


SCHEMA = "coinbase-btc-usd-shadow-recorder-v1"
ENDPOINT = "https://api.coinbase.com/api/v3/brokerage/market/products/BTC-USD/candles"
FINALITY_LAG = timedelta(minutes=2)
GRANULARITIES = {
    "1m": ("ONE_MINUTE", timedelta(minutes=1)),
    "5m": ("FIVE_MINUTE", timedelta(minutes=5)),
    "15m": ("FIFTEEN_MINUTE", timedelta(minutes=15)),
    "1h": ("ONE_HOUR", timedelta(hours=1)),
    "4h": ("FOUR_HOUR", timedelta(hours=4)),
}


@dataclass(frozen=True)
class ShadowCandle:
    timeframe: str
    open_time: datetime
    close_time: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    def document(self) -> dict:
        return {
            "close": format(self.close, "f"),
            "close_time_utc": self.close_time.isoformat().replace("+00:00", "Z"),
            "exchange": "coinbase",
            "high": format(self.high, "f"),
            "instrument": "BTC-USD",
            "is_closed": True,
            "low": format(self.low, "f"),
            "open": format(self.open, "f"),
            "open_time_utc": self.open_time.isoformat().replace("+00:00", "Z"),
            "paper_only": True,
            "schema_version": "coinbase-public-candle-v1",
            "source": "coinbase-advanced-trade-public",
            "timeframe": self.timeframe,
            "trading_authority": False,
            "volume": format(self.volume, "f"),
        }


class PublicTransport:
    def get(self, *, url: str, timeout: float) -> bytes:
        request = urllib.request.Request(url, headers={
            "Accept": "application/json", "Cache-Control": "no-cache",
            "User-Agent": "Hermes-Coinbase-BTC-Shadow-Recorder/1",
        })
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()


def _utc(value: int) -> datetime:
    return datetime.fromtimestamp(value, tz=timezone.utc)


def parse_response(raw: bytes, *, timeframe: str, observed_at: datetime) -> tuple[ShadowCandle, ...]:
    if timeframe not in GRANULARITIES:
        raise ValueError("unsupported timeframe")
    if observed_at.tzinfo is None or observed_at.utcoffset() != timedelta(0):
        raise ValueError("UTC observed_at required")
    try:
        payload = json.loads(raw.decode("utf-8"), parse_float=str, parse_int=int)
    except Exception as exc:
        raise ValueError("invalid Coinbase JSON") from exc
    rows = payload.get("candles") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise ValueError("Coinbase candles array required")
    duration = GRANULARITIES[timeframe][1]
    candles: dict[datetime, ShadowCandle] = {}
    for row in rows:
        if not isinstance(row, dict) or not {"start", "open", "high", "low", "close", "volume"} <= set(row):
            raise ValueError("Coinbase candle schema invalid")
        try:
            opened = _utc(int(row["start"])); values = tuple(
                Decimal(str(row[name])) for name in ("open", "high", "low", "close", "volume"))
        except (ValueError, TypeError, InvalidOperation) as exc:
            raise ValueError("Coinbase candle value invalid") from exc
        o, h, l, c, volume = values; closed = opened + duration
        if volume < 0 or min(o, h, l, c) <= 0 or h < max(o, l, c) or l > min(o, h, c):
            raise ValueError("Coinbase candle invariant violated")
        if closed > observed_at - FINALITY_LAG:
            continue
        candle = ShadowCandle(timeframe, opened, closed, o, h, l, c, volume)
        prior = candles.get(opened)
        if prior is not None and prior != candle:
            raise ValueError("conflicting Coinbase candle")
        candles[opened] = candle
    return tuple(candles[key] for key in sorted(candles))


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("wb") as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary, path)


def _read_archive(path: Path) -> dict[str, dict]:
    result = {}
    if not path.exists():
        return result
    for line in path.read_text("utf-8").splitlines():
        row = json.loads(line); key = row["open_time_utc"]
        if key in result and result[key] != row:
            raise ValueError("shadow archive contains conflicting candle")
        result[key] = row
    return result


def poll_once(*, archive: Path, timeframes: tuple[str, ...], transport=None,
              observed_at: datetime | None = None, timeout: float = 15.0) -> dict:
    if not timeframes or len(timeframes) != len(set(timeframes)) or any(t not in GRANULARITIES for t in timeframes):
        raise ValueError("unique supported timeframes required")
    now = (observed_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    client = transport or PublicTransport(); streams = {}; checksums = {}
    for timeframe in timeframes:
        granularity, duration = GRANULARITIES[timeframe]
        end = int(now.timestamp()); start = int((now - duration * 300).timestamp())
        query = urllib.parse.urlencode({"start": start, "end": end,
                                        "granularity": granularity, "limit": 350})
        candles = parse_response(client.get(url=ENDPOINT + "?" + query, timeout=timeout),
                                 timeframe=timeframe, observed_at=now)
        path = archive / f"BTC-USD_{timeframe}.jsonl"; existing = _read_archive(path)
        for candle in candles:
            row = candle.document(); key = row["open_time_utc"]
            if key in existing and existing[key] != row:
                raise ValueError("Coinbase source revised an archived candle")
            existing[key] = row
        ordered = [existing[key] for key in sorted(existing)]
        payload = b"".join(_canonical_bytes(row) for row in ordered); _atomic(path, payload)
        checksums[path.name] = sha256(payload).hexdigest()
        latest = ordered[-1]["close_time_utc"] if ordered else None
        opens = [datetime.fromisoformat(row["open_time_utc"].replace("Z", "+00:00")) for row in ordered]
        gap_count = sum(1 for left, right in zip(opens, opens[1:]) if right - left != duration)
        latest_time = (datetime.fromisoformat(latest.replace("Z", "+00:00"))
                       if latest is not None else None)
        streams[timeframe] = {"count": len(ordered), "latest_close_utc": latest,
                              "poll_record_count": len(candles), "gap_count": gap_count,
                              "stale": (latest_time is None or
                                        now - latest_time > FINALITY_LAG + duration * 2)}
    manifest = {
        "account_access": False, "archive_checksums": checksums,
        "credentials_required": False, "endpoint": ENDPOINT,
        "instrument": "BTC-USD", "observed_at": now.isoformat().replace("+00:00", "Z"),
        "finality_lag_seconds": int(FINALITY_LAG.total_seconds()),
        "order_endpoints_present": False, "paper_only": True,
        "promotion_state": "SHADOW_ONLY", "schema_version": SCHEMA,
        "source": "coinbase-advanced-trade-public", "state": "RECORDING",
        "streams": streams, "trading_authority": False,
    }
    core = _canonical_bytes(manifest); manifest["manifest_sha256"] = sha256(core).hexdigest()
    _atomic(archive / "archive_manifest.json", _canonical_bytes(manifest)); return manifest


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--archive", required=True)
    parser.add_argument("--timeframes", nargs="+", default=list(GRANULARITIES))
    parser.add_argument("--interval", type=float, default=15.0)
    parser.add_argument("--max-cycles", type=int); args = parser.parse_args()
    cycles = 0
    while args.max_cycles is None or cycles < args.max_cycles:
        result = poll_once(archive=Path(args.archive), timeframes=tuple(args.timeframes))
        cycles += 1
        if args.max_cycles is None or cycles < args.max_cycles:
            time.sleep(args.interval)
    print(json.dumps(result, sort_keys=True, separators=(",", ":"))); return 0


if __name__ == "__main__":
    raise SystemExit(main())
