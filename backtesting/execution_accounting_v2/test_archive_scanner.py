from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json

import pytest

from .archive_scanner import ArchiveFormat, ArchiveScanError, scan_archive


HEADER = "symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"
ROW1 = "BTC,1m,2026-01-01T00:00:00Z,2026-01-01T00:01:00Z,10,12,9,11,3,true\n"
ROW2 = "BTC,1m,2026-01-01T00:01:00Z,2026-01-01T00:02:00Z,11,13,10,12,4,true\n"


def write_csv(tmp_path, body=HEADER + ROW1 + ROW2):
    path = tmp_path / "data" / "bars.csv"; path.parent.mkdir(); path.write_text(body, encoding="utf-8", newline="")
    return path


def test_csv_scan_computes_exact_evidence(tmp_path):
    path = write_csv(tmp_path)
    result = scan_archive(repository=tmp_path, relative_path="data/bars.csv", market="BTC",
                          timeframe="1m", archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
    assert result.evidence_file.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result.evidence_file.byte_count == len(path.read_bytes())
    assert result.evidence_file.record_count == 2
    assert result.evidence_file.start_inclusive == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert result.evidence_file.end_exclusive == datetime(2026, 1, 1, 0, 2, tzinfo=timezone.utc)
    assert result.missing_intervals == () and result.trading_authority is False


def test_gap_is_reported_not_silently_filled(tmp_path):
    row = "BTC,1m,2026-01-01T00:03:00Z,2026-01-01T00:04:00Z,11,13,10,12,4,true\n"
    write_csv(tmp_path, HEADER + ROW1 + row)
    result = scan_archive(repository=tmp_path, relative_path="data/bars.csv", market="BTC",
                          timeframe="1m", archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
    assert len(result.missing_intervals) == 1
    assert result.missing_intervals[0].reason == "UNCLASSIFIED_ARCHIVE_DISCONTINUITY"


@pytest.mark.parametrize("body", [
    HEADER + ROW1 + ROW1,
    HEADER + ROW2 + ROW1,
    HEADER + ROW1.replace(",true", ",false"),
    HEADER + ROW1.replace("BTC,", "ES,"),
    HEADER + ROW1.replace(",12,9,", ",8,9,"),
    HEADER + ROW1.replace("T00:01:00Z", "T00:02:00Z"),
])
def test_csv_corruption_fails_closed(tmp_path, body):
    write_csv(tmp_path, body)
    with pytest.raises(ArchiveScanError):
        scan_archive(repository=tmp_path, relative_path="data/bars.csv", market="BTC",
                     timeframe="1m", archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


def test_path_escape_fails_closed(tmp_path):
    write_csv(tmp_path)
    with pytest.raises(ArchiveScanError):
        scan_archive(repository=tmp_path, relative_path="../bars.csv", market="BTC",
                     timeframe="1m", archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


def test_short_csv_row_uses_public_scanner_error(tmp_path):
    write_csv(tmp_path, HEADER + "not,a,csv,row\n")
    with pytest.raises(ArchiveScanError):
        scan_archive(repository=tmp_path, relative_path="data/bars.csv", market="BTC",
                     timeframe="1m", archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


def test_futures_jsonl_scan(tmp_path):
    directory = tmp_path / "data"; directory.mkdir(); path = directory / "bars.jsonl"
    rows = []
    for ns in (1767225600000000000, 1767225660000000000):
        rows.append({"root":"ES","window_start_ns":ns,"open":"10","high":"12",
                     "low":"9","close":"11","volume":"3","schema_version":"x"})
    path.write_text("".join(json.dumps(x) + "\n" for x in rows), encoding="utf-8")
    result = scan_archive(repository=tmp_path, relative_path="data/bars.jsonl", market="ES",
                          timeframe="1m", archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)
    assert result.evidence_file.record_count == 2 and result.missing_intervals == ()


def test_scan_is_deterministic(tmp_path):
    write_csv(tmp_path)
    args = dict(repository=tmp_path, relative_path="data/bars.csv", market="BTC",
                timeframe="1m", archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
    assert scan_archive(**args) == scan_archive(**args)
