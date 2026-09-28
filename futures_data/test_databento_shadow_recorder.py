import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from futures_data.databento_shadow_recorder import (
    DatabentoShadowError, append_minutes, normalize_record, record_once, replay_window,
)


NOW = datetime(2026, 9, 11, 18, 2, tzinfo=timezone.utc)


def raw(opened=NOW - timedelta(minutes=5), close="6500.25", instrument=123):
    return {"ts_event": int(opened.timestamp() * 1_000_000_000), "instrument_id": instrument,
            "raw_symbol": "MESZ6", "open": "6500.00", "high": "6500.50",
            "low": "6499.75", "close": close, "volume": "42"}


def test_restart_window_is_bounded_and_resumes_at_archive_close():
    result = replay_window(observed_at=NOW, latest_close=NOW - timedelta(minutes=10))
    assert result.start == NOW - timedelta(minutes=10)
    assert result.end == NOW - timedelta(minutes=2)
    assert result.reason == "RESTART_CONTINUATION"
    with pytest.raises(DatabentoShadowError, match="24-hour"):
        replay_window(observed_at=NOW, latest_close=NOW - timedelta(hours=25))


def test_normalization_preserves_exact_values_and_rejects_forming_or_float():
    item = normalize_record(raw(), lane="ES", finality_horizon=NOW - timedelta(minutes=2))
    assert item.parent_symbol == "MES.FUT"
    assert item.close == Decimal("6500.25")
    bad = raw(); bad["close"] = 6500.25
    with pytest.raises(DatabentoShadowError, match="binary float"):
        normalize_record(bad, lane="ES", finality_horizon=NOW)
    with pytest.raises(DatabentoShadowError, match="forming"):
        normalize_record(raw(NOW), lane="ES", finality_horizon=NOW)


def test_append_only_chain_is_idempotent_and_rejects_revision(tmp_path: Path):
    window = replay_window(observed_at=NOW, latest_close=None)
    item = normalize_record(raw(), lane="ES", finality_horizon=window.end)
    first = append_minutes(archive_root=tmp_path, lane="ES", minutes=(item,),
                           observed_at=NOW, replay=window, source_id="databento-live")
    second = append_minutes(archive_root=tmp_path, lane="ES", minutes=(item,),
                            observed_at=NOW, replay=window, source_id="databento-live")
    assert first["accepted_record_count"] == 1
    assert second["accepted_record_count"] == 0
    assert second["account_access"] is False
    assert second["order_endpoints_present"] is False
    assert second["trading_authority"] is False
    revised = normalize_record(raw(close="6500.00"), lane="ES", finality_horizon=window.end)
    with pytest.raises(DatabentoShadowError, match="revision"):
        append_minutes(archive_root=tmp_path, lane="ES", minutes=(revised,),
                       observed_at=NOW, replay=window, source_id="databento-live")


class FakeSource:
    source_id = "databento-live"

    def __init__(self): self.calls = []

    def fetch(self, **request):
        self.calls.append(request)
        lane = "ES" if request["parent_symbol"] == "MES.FUT" else "NQ"
        value = raw(request["end"] - timedelta(minutes=1), instrument=123 if lane == "ES" else 456)
        value["raw_symbol"] = "MESZ6" if lane == "ES" else "MNQZ6"
        return (value,)


def test_record_once_is_market_isolated_and_has_no_trading_authority(tmp_path: Path):
    source = FakeSource()
    result = record_once(source=source, archive_root=tmp_path, observed_at=NOW)
    assert result["state"] == "SHADOW_COMPLETE"
    assert result["trading_authority"] is False
    assert [call["parent_symbol"] for call in source.calls] == ["MES.FUT", "MNQ.FUT"]
    assert all(call["dataset"] == "GLBX.MDP3" and call["schema"] == "ohlcv-1m"
               for call in source.calls)
    assert (tmp_path / "ES" / "manifest.json").exists()
    assert (tmp_path / "NQ" / "manifest.json").exists()


def test_single_writer_and_cross_lane_contamination_fail_closed(tmp_path: Path):
    window = replay_window(observed_at=NOW, latest_close=None)
    item = normalize_record(raw(), lane="ES", finality_horizon=window.end)
    lane = tmp_path / "ES"; lane.mkdir(); (lane / ".writer.lock").write_text("occupied")
    with pytest.raises(DatabentoShadowError, match="single-writer"):
        append_minutes(archive_root=tmp_path, lane="ES", minutes=(item,),
                       observed_at=NOW, replay=window, source_id="databento-live")
    (lane / ".writer.lock").unlink()
    with pytest.raises(DatabentoShadowError, match="cross-lane"):
        append_minutes(archive_root=tmp_path, lane="NQ", minutes=(item,),
                       observed_at=NOW, replay=window, source_id="databento-live")


def test_hash_chain_continues_across_utc_day_files(tmp_path: Path):
    first_open = datetime(2026, 9, 10, 23, 59, tzinfo=timezone.utc)
    second_open = datetime(2026, 9, 11, 0, 0, tzinfo=timezone.utc)
    horizon = datetime(2026, 9, 11, 0, 2, tzinfo=timezone.utc)
    window = replay_window(observed_at=horizon + timedelta(minutes=2), latest_close=None)
    first = normalize_record(raw(first_open), lane="ES", finality_horizon=horizon)
    second = normalize_record(raw(second_open), lane="ES", finality_horizon=horizon)
    append_minutes(archive_root=tmp_path, lane="ES", minutes=(first, second),
                   observed_at=horizon, replay=window, source_id="databento-live")
    result = append_minutes(archive_root=tmp_path, lane="ES", minutes=(first, second),
                            observed_at=horizon, replay=window, source_id="databento-live")
    assert result["accepted_record_count"] == 0
    assert (tmp_path / "ES" / "2026-09-10.jsonl").exists()
    assert (tmp_path / "ES" / "2026-09-11.jsonl").exists()


def test_record_once_rejects_tampered_restart_manifest(tmp_path: Path):
    source = FakeSource()
    record_once(source=source, archive_root=tmp_path, observed_at=NOW)
    manifest_path = tmp_path / "ES" / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8"))
    manifest["last_open_time_utc"] = "2026-09-11T00:00:00Z"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(DatabentoShadowError, match="manifest digest invalid"):
        record_once(source=source, archive_root=tmp_path, observed_at=NOW)
