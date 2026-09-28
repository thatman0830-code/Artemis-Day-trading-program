import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from futures_data.databento_historical_probe import ProbeError, run_probe


START = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)


def mock_open(request, timeout):
    assert timeout == 20
    query = parse_qs(urlparse(request.full_url).query)
    assert query["symbols"] == ["MES.v.0,MNQ.v.0"]
    assert query["schema"] == ["ohlcv-1m"]
    assert query["limit"] == ["20"]
    assert request.get_header("Authorization").startswith("Basic ")
    rows = [
        {"version": 3, "metadata": {"dataset": "GLBX.MDP3"}},
        {"hd": {"ts_event": "2026-09-10T15:00:00.000000000Z", "instrument_id": 11}},
        {"hd": {"ts_event": "2026-09-10T15:00:00.000000000Z", "instrument_id": 22}},
    ]
    return 200, b"\n".join(json.dumps(row).encode() for row in rows)


def test_probe_is_bounded_sanitized_and_nontrading(tmp_path: Path):
    output = tmp_path / "probe.json"
    report = run_probe(key="db-" + "x" * 29, start=START, output=output, opener=mock_open)
    assert report["state"] == "HISTORICAL_CONNECTIVITY_PROBE_PASSED"
    assert report["request_count"] == 1 and report["maximum_records"] == 20
    assert report["trading_authority"] is False
    serialized = output.read_text()
    assert "db-" not in serialized and "Authorization" not in serialized


def test_probe_rejects_bad_key_and_empty_data(tmp_path: Path):
    with pytest.raises(ProbeError, match="credential format"):
        run_probe(key="wrong", start=START, output=tmp_path / "x")
    with pytest.raises(ProbeError, match="NO_DATA"):
        run_probe(key="db-" + "x" * 29, start=START, output=tmp_path / "x",
                  opener=lambda request, timeout: (200, b""))


def test_wrapper_keeps_key_off_arguments_and_environment():
    text = (Path(__file__).resolve().parents[1] / "scripts" /
            "run_databento_historical_probe.ps1").read_text(encoding="utf-8")
    assert "StandardInput.WriteLine($plain)" in text
    assert "--api-key" not in text.lower()
    assert "DATABENTO_API_KEY" not in text
    assert "ZeroFreeBSTR" in text
    assert "FAILED_SANITIZED" in text
    assert "StandardError.ReadToEnd" in text
