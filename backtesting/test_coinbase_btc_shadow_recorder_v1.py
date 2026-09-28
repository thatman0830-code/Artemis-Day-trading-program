import json
from datetime import datetime, timezone
from pathlib import Path
import pytest

from backtesting.coinbase_btc_shadow_recorder_v1 import parse_response, poll_once

NOW = datetime(2026, 9, 11, 1, 20, tzinfo=timezone.utc)


def payload(rows):
    return json.dumps({"candles": rows}).encode()


def row(start=None, close="100.5"):
    if start is None:
        start = int(NOW.timestamp()) - 240
    return {"start": str(start), "open": "100", "high": "101", "low": "99",
            "close": close, "volume": "12.5"}


class Fake:
    def __init__(self, raw): self.raw = raw; self.urls = []
    def get(self, *, url, timeout): self.urls.append((url, timeout)); return self.raw


def test_parser_accepts_only_closed_sorted_exact_decimal_rows():
    rows = parse_response(payload([row(int(NOW.timestamp()) - 180),
                                   row(int(NOW.timestamp()) - 240)]),
                          timeframe="1m", observed_at=NOW)
    assert [item.open_time.minute for item in rows] == [16, 17]
    assert str(rows[-1].close) == "100.5"


@pytest.mark.parametrize("bad", [b"[]", b'{"candles":{}}', b"not-json"])
def test_parser_rejects_malformed_payload(bad):
    with pytest.raises(ValueError): parse_response(bad, timeframe="1m", observed_at=NOW)


def test_forming_candle_is_excluded():
    future = int(NOW.timestamp())
    assert parse_response(payload([row(future)]), timeframe="1m", observed_at=NOW) == ()


def test_recently_closed_candle_waits_for_finality_lag():
    recent = int(NOW.timestamp()) - 60
    assert parse_response(payload([row(recent)]), timeframe="1m", observed_at=NOW) == ()


def test_shadow_poll_is_credential_free_atomic_and_fail_closed(tmp_path: Path):
    fake = Fake(payload([row()]))
    report = poll_once(archive=tmp_path, timeframes=("1m",), transport=fake, observed_at=NOW)
    assert report["promotion_state"] == "SHADOW_ONLY"
    assert report["credentials_required"] is False
    assert report["account_access"] is False
    assert report["order_endpoints_present"] is False
    assert report["trading_authority"] is False
    assert report["finality_lag_seconds"] == 120
    assert "/market/products/BTC-USD/candles?" in fake.urls[0][0]
    assert not list(tmp_path.glob("*.tmp"))
    first = (tmp_path / "BTC-USD_1m.jsonl").read_bytes()
    poll_once(archive=tmp_path, timeframes=("1m",), transport=fake, observed_at=NOW)
    assert (tmp_path / "BTC-USD_1m.jsonl").read_bytes() == first


def test_conflicting_revision_rejects(tmp_path: Path):
    poll_once(archive=tmp_path, timeframes=("1m",), transport=Fake(payload([row()])), observed_at=NOW)
    with pytest.raises(ValueError, match="revised"):
        poll_once(archive=tmp_path, timeframes=("1m",),
                  transport=Fake(payload([row(close="100.75")])), observed_at=NOW)
