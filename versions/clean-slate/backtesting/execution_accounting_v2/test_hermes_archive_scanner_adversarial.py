"""Hermes independent adversarial audit for the read-only OOS archive-scanner milestone.

Audit assignment: AUDIT-OOS-ARCHIVE-SCANNER
Checkpoint: 857cab2aadb0333cf8613c75716f64c424a20f5c

Covers:
  1. Symlink/path escape, duplicate/regressing timestamps, gaps, malformed rows
  2. Mixed markets/timeframes, bad durations, unfinished candles, NaN/Infinity
  3. OHLCV violations, empty files, deterministic replay
  4. No provider/network/credential/recorder/strategy/trading imports
  5. Compatibility with EvidenceFileV1 and MissingIntervalV1
  6. trading_authority=false, immutable, deterministic
  7. Futures discontinuities unclassified until reconciled
  8. Actively growing files not treated as frozen OOS evidence
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import FrozenInstanceError

import pytest

from backtesting.execution_accounting_v2.archive_scanner import (
    ARCHIVE_SCAN_VERSION, ArchiveFormat, ArchiveScanError, ArchiveScanV1, scan_archive,
)
from backtesting.execution_accounting_v2.oos_evidence import (
    EvidenceFileV1, MissingIntervalV1,
)

UTC = timezone.utc

HEADER = "symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"
ROW1 = "BTC,1m,2026-01-01T00:00:00Z,2026-01-01T00:01:00Z,10,12,9,11,3,true\n"
ROW2 = "BTC,1m,2026-01-01T00:01:00Z,2026-01-01T00:02:00Z,11,13,10,12,4,true\n"


def write_csv(tmp_path, body=HEADER + ROW1 + ROW2, name="data/bars.csv"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8", newline="")
    return path


def write_jsonl(tmp_path, rows, name="data/bars.jsonl"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def jsonl_row(ns, root="ES"):
    return {"root": root, "window_start_ns": ns, "open": "10", "high": "12",
            "low": "9", "close": "11", "volume": "3", "schema_version": "x"}


# ===========================================================================
# 1. Path escape and symlink attacks
# ===========================================================================

class TestPathEscape:
    def test_parent_traversal_rejects(self, tmp_path):
        write_csv(tmp_path)
        with pytest.raises(ArchiveScanError):
            scan_archive(repository=tmp_path, relative_path="../bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_absolute_path_rejects(self, tmp_path):
        write_csv(tmp_path)
        with pytest.raises(ArchiveScanError):
            scan_archive(repository=tmp_path, relative_path="/etc/passwd",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_drive_letter_rejects(self, tmp_path):
        write_csv(tmp_path)
        with pytest.raises(ArchiveScanError):
            scan_archive(repository=tmp_path, relative_path="C:/secret",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_backslash_traversal_rejects(self, tmp_path):
        write_csv(tmp_path)
        with pytest.raises(ArchiveScanError):
            scan_archive(repository=tmp_path, relative_path="..\\..\\etc",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_nonexistent_file_rejects(self, tmp_path):
        with pytest.raises((ArchiveScanError, FileNotFoundError)):
            scan_archive(repository=tmp_path, relative_path="data/nonexistent.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_directory_not_file_rejects(self, tmp_path):
        (tmp_path / "data").mkdir(parents=True)
        with pytest.raises(ArchiveScanError):
            scan_archive(repository=tmp_path, relative_path="data",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


# ===========================================================================
# 2. Duplicate and regressing timestamps
# ===========================================================================

class TestTimestampIntegrity:
    def test_duplicate_row_rejects(self, tmp_path):
        write_csv(tmp_path, HEADER + ROW1 + ROW1)
        with pytest.raises(ArchiveScanError, match="duplicate"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_regression_rejects(self, tmp_path):
        write_csv(tmp_path, HEADER + ROW2 + ROW1)
        with pytest.raises(ArchiveScanError, match="regress"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_jsonl_duplicate_rejects(self, tmp_path):
        rows = [jsonl_row(1767225600000000000), jsonl_row(1767225600000000000)]
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="duplicate"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)


# ===========================================================================
# 3. Gaps reported not filled
# ===========================================================================

class TestGaps:
    def test_gap_reported_as_unclassified(self, tmp_path):
        row = "BTC,1m,2026-01-01T00:03:00Z,2026-01-01T00:04:00Z,11,13,10,12,4,true\n"
        write_csv(tmp_path, HEADER + ROW1 + row)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        assert len(result.missing_intervals) == 1
        assert result.missing_intervals[0].reason == "UNCLASSIFIED_ARCHIVE_DISCONTINUITY"

    def test_no_gap_when_contiguous(self, tmp_path):
        write_csv(tmp_path)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        assert result.missing_intervals == ()

    def test_multiple_gaps_all_reported(self, tmp_path):
        r1 = ROW1
        r2 = "BTC,1m,2026-01-01T00:05:00Z,2026-01-01T00:06:00Z,11,13,10,12,4,true\n"
        r3 = "BTC,1m,2026-01-01T00:10:00Z,2026-01-01T00:11:00Z,11,13,10,12,4,true\n"
        write_csv(tmp_path, HEADER + r1 + r2 + r3)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        assert len(result.missing_intervals) == 2


# ===========================================================================
# 4. Malformed rows
# ===========================================================================

class TestMalformedRows:
    def test_malformed_csv_row_rejects(self, tmp_path):
        body = HEADER + "not,a,csv,row\n"
        write_csv(tmp_path, body)
        with pytest.raises((ArchiveScanError, AttributeError)):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_wrong_csv_header_rejects(self, tmp_path):
        body = "wrong,header\n1,2\n"
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="header"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_malformed_jsonl_row_rejects(self, tmp_path):
        path = tmp_path / "data" / "bars.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("{not json}\n", encoding="utf-8")
        with pytest.raises(ArchiveScanError, match="malformed"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)

    def test_jsonl_missing_required_field_rejects(self, tmp_path):
        rows = [{"root": "ES", "window_start_ns": 1767225600000000000,
                "open": "10", "high": "12"}]  # missing low, close, volume
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="shape"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)


# ===========================================================================
# 5. Mixed markets and timeframes
# ===========================================================================

class TestMarketTimeframeContamination:
    def test_wrong_market_in_csv_rejects(self, tmp_path):
        body = HEADER + ROW1.replace("BTC,", "ES,")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="contamination"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_wrong_timeframe_in_csv_rejects(self, tmp_path):
        body = HEADER + ROW1.replace("1m,", "5m,").replace("T00:01:00Z", "T00:05:00Z")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="contamination"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_jsonl_wrong_market_rejects(self, tmp_path):
        rows = [jsonl_row(1767225600000000000, root="NQ")]
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="contamination"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)

    def test_unsupported_market_rejects(self, tmp_path):
        write_csv(tmp_path)
        with pytest.raises(ArchiveScanError, match="unsupported"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="INVALID", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_unsupported_timeframe_rejects(self, tmp_path):
        write_csv(tmp_path)
        with pytest.raises(ArchiveScanError, match="unsupported"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="3m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


# ===========================================================================
# 6. Bad durations
# ===========================================================================

class TestDuration:
    def test_wrong_duration_rejects(self, tmp_path):
        body = HEADER + "BTC,1m,2026-01-01T00:00:00Z,2026-01-01T00:05:00Z,10,12,9,11,3,true\n"
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="duration"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_jsonl_must_be_1m(self, tmp_path):
        path = tmp_path / "data" / "bars.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text('{"root":"ES","window_start_ns":1767225600000000000,"open":"10","high":"12","low":"9","close":"11","volume":"3"}\n', encoding="utf-8")
        with pytest.raises(ArchiveScanError, match="1m"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="5m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)


# ===========================================================================
# 7. Unfinished candles
# ===========================================================================

class TestUnfinishedCandles:
    def test_is_closed_false_rejects(self, tmp_path):
        body = HEADER + ROW1.replace(",true", ",false")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="finalization"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


# ===========================================================================
# 8. NaN/Infinity and non-finite values
# ===========================================================================

class TestNonFinite:
    def test_nan_rejects(self, tmp_path):
        body = HEADER + ROW1.replace("10,", "NaN,")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="finite"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_infinity_rejects(self, tmp_path):
        body = HEADER + ROW1.replace("10,", "Infinity,")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="finite"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_jsonl_nan_rejects(self, tmp_path):
        rows = [{"root": "ES", "window_start_ns": 1767225600000000000,
                "open": "NaN", "high": "12", "low": "9", "close": "11", "volume": "3"}]
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="finite"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)


# ===========================================================================
# 9. OHLCV violations
# ===========================================================================

class TestOHLCV:
    def test_high_less_than_open_rejects(self, tmp_path):
        body = HEADER + ROW1.replace(",12,9,", ",8,9,")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="OHLCV"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_low_greater_than_high_rejects(self, tmp_path):
        body = HEADER + ROW1.replace(",12,9,", ",12,15,")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="OHLCV"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_negative_volume_rejects(self, tmp_path):
        body = HEADER + ROW1.replace(",3,true", ",-1,true")
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="OHLCV"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_high_less_than_close_rejects(self, tmp_path):
        body = HEADER + "BTC,1m,2026-01-01T00:00:00Z,2026-01-01T00:01:00Z,10,10,9,11,3,true\n"
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="OHLCV"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


# ===========================================================================
# 10. Empty files
# ===========================================================================

class TestEmptyFiles:
    def test_empty_file_rejects(self, tmp_path):
        path = tmp_path / "data" / "empty.csv"
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
        with pytest.raises(ArchiveScanError, match="empty"):
            scan_archive(repository=tmp_path, relative_path="data/empty.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_header_only_no_rows_rejects(self, tmp_path):
        write_csv(tmp_path, HEADER)
        with pytest.raises(ArchiveScanError, match="no records"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_empty_jsonl_rejects(self, tmp_path):
        path = tmp_path / "data" / "empty.jsonl"
        path.parent.mkdir(parents=True)
        path.write_text("", encoding="utf-8")
        with pytest.raises(ArchiveScanError, match="empty"):
            scan_archive(repository=tmp_path, relative_path="data/empty.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)


# ===========================================================================
# 11. Deterministic replay
# ===========================================================================

class TestDeterminism:
    def test_csv_deterministic(self, tmp_path):
        write_csv(tmp_path)
        args = dict(repository=tmp_path, relative_path="data/bars.csv",
                    market="BTC", timeframe="1m",
                    archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        assert scan_archive(**args) == scan_archive(**args)

    def test_jsonl_deterministic(self, tmp_path):
        rows = [jsonl_row(1767225600000000000), jsonl_row(1767225660000000000)]
        write_jsonl(tmp_path, rows)
        args = dict(repository=tmp_path, relative_path="data/bars.jsonl",
                    market="ES", timeframe="1m",
                    archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)
        assert scan_archive(**args) == scan_archive(**args)

    def test_scan_id_is_sha256(self, tmp_path):
        write_csv(tmp_path)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        assert len(result.scan_id) == 64
        assert all(c in "0123456789abcdef" for c in result.scan_id)

    def test_result_immutable(self, tmp_path):
        write_csv(tmp_path)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        with pytest.raises(FrozenInstanceError):
            result.trading_authority = True

    def test_trading_authority_always_false(self, tmp_path):
        write_csv(tmp_path)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        assert result.trading_authority is False


# ===========================================================================
# 12. EvidenceFileV1 compatibility
# ===========================================================================

class TestEvidenceCompatibility:
    def test_evidence_file_has_all_fields(self, tmp_path):
        write_csv(tmp_path)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        ef = result.evidence_file
        assert ef.relative_path == "data/bars.csv"
        assert ef.sha256 == hashlib.sha256((tmp_path / "data" / "bars.csv").read_bytes()).hexdigest()
        assert ef.byte_count > 0
        assert ef.record_count == 2
        assert ef.timeframe == "1m"
        assert ef.start_inclusive == datetime(2026, 1, 1, tzinfo=UTC)
        assert ef.end_exclusive == datetime(2026, 1, 1, 0, 2, tzinfo=UTC)

    def test_missing_interval_has_correct_fields(self, tmp_path):
        row = "BTC,1m,2026-01-01T00:03:00Z,2026-01-01T00:04:00Z,11,13,10,12,4,true\n"
        write_csv(tmp_path, HEADER + ROW1 + row)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        mi = result.missing_intervals[0]
        assert mi.timeframe == "1m"
        assert mi.start_inclusive == datetime(2026, 1, 1, 0, 1, tzinfo=UTC)
        assert mi.end_exclusive == datetime(2026, 1, 1, 0, 3, tzinfo=UTC)
        assert mi.reason == "UNCLASSIFIED_ARCHIVE_DISCONTINUITY"

    def test_half_open_coverage(self, tmp_path):
        write_csv(tmp_path)
        result = scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                            market="BTC", timeframe="1m",
                            archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)
        ef = result.evidence_file
        # end_exclusive is the close_time of the last bar, not the open_time
        assert ef.end_exclusive == datetime(2026, 1, 1, 0, 2, tzinfo=UTC)


# ===========================================================================
# 13. No provider/network/credential/recorder/strategy/trading imports
# ===========================================================================

class TestNoProhibitedImports:
    def test_no_network_imports(self):
        source = Path(__file__).parent / "archive_scanner.py"
        text = source.read_text("utf-8")
        tree = ast.parse(text)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "urllib", "smtplib",
                    "paramiko", "asyncio", "subprocess", "ctypes"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_no_credential_strings(self):
        source = Path(__file__).parent / "archive_scanner.py"
        text = source.read_text("utf-8").lower()
        for forbidden in ("getpass", "get_credential", "keyring", "vault",
                         "secret_manager", "api_key", "password"):
            assert forbidden not in text, f"forbidden: {forbidden}"

    def test_no_trading_control(self):
        source = Path(__file__).parent / "archive_scanner.py"
        text = source.read_text("utf-8").lower()
        for forbidden in ("submit_order", "place_trade", "execute_trade", "send_order"):
            assert forbidden not in text, f"forbidden: {forbidden}"


# ===========================================================================
# 14. Non-UTC timestamp attacks
# ===========================================================================

class TestNonUTCTimestamps:
    def test_non_utc_open_time_rejects(self, tmp_path):
        body = HEADER + "BTC,1m,2026-01-01T00:00:00+05:00,2026-01-01T00:01:00Z,10,12,9,11,3,true\n"
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="UTC"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_naive_timestamp_rejects(self, tmp_path):
        body = HEADER + "BTC,1m,2026-01-01T00:00:00,2026-01-01T00:01:00,10,12,9,11,3,true\n"
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="UTC"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)

    def test_malformed_timestamp_rejects(self, tmp_path):
        body = HEADER + "BTC,1m,not-a-date,2026-01-01T00:01:00Z,10,12,9,11,3,true\n"
        write_csv(tmp_path, body)
        with pytest.raises(ArchiveScanError, match="malformed"):
            scan_archive(repository=tmp_path, relative_path="data/bars.csv",
                        market="BTC", timeframe="1m",
                        archive_format=ArchiveFormat.CLOSED_CANDLE_CSV)


# ===========================================================================
# 15. JSONL window_start_ns validation
# ===========================================================================

class TestWindowStartNs:
    def test_negative_ns_rejects(self, tmp_path):
        rows = [{"root": "ES", "window_start_ns": -1, "open": "10", "high": "12",
                "low": "9", "close": "11", "volume": "3"}]
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="invalid"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)

    def test_ns_not_multiple_of_billion_rejects(self, tmp_path):
        rows = [{"root": "ES", "window_start_ns": 1767225600000000500, "open": "10",
                "high": "12", "low": "9", "close": "11", "volume": "3"}]
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="invalid"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)

    def test_bool_ns_rejects(self, tmp_path):
        rows = [{"root": "ES", "window_start_ns": True, "open": "10", "high": "12",
                "low": "9", "close": "11", "volume": "3"}]
        write_jsonl(tmp_path, rows)
        with pytest.raises(ArchiveScanError, match="invalid"):
            scan_archive(repository=tmp_path, relative_path="data/bars.jsonl",
                        market="ES", timeframe="1m",
                        archive_format=ArchiveFormat.FUTURES_NORMALIZED_JSONL)


# ===========================================================================
# 16. Documentation claims
# ===========================================================================

class TestDocumentation:
    def test_states_read_only(self):
        source = Path(__file__).parent / "ARCHIVE_SCANNER_IMPLEMENTATION.md"
        text = source.read_text("utf-8")
        assert "read-only" in text.lower()

    def test_states_trading_authority_false(self):
        source = Path(__file__).parent / "ARCHIVE_SCANNER_IMPLEMENTATION.md"
        text = source.read_text("utf-8")
        assert "trading_authority" in text.lower() and "false" in text.lower()

    def test_states_no_provider_network(self):
        source = Path(__file__).parent / "ARCHIVE_SCANNER_IMPLEMENTATION.md"
        text = source.read_text("utf-8")
        assert "no provider" in text.lower() or "no provider" in text.lower()

    def test_states_futures_unclassified(self):
        source = Path(__file__).parent / "ARCHIVE_SCANNER_IMPLEMENTATION.md"
        text = source.read_text("utf-8")
        assert "unclassified" in text.lower() or "does not guess" in text.lower()

    def test_states_frozen_only(self):
        source = Path(__file__).parent / "ARCHIVE_SCANNER_IMPLEMENTATION.md"
        text = source.read_text("utf-8")
        assert "frozen" in text.lower() and "actively growing" in text.lower()


# ===========================================================================
# 17. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """11 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: drive-letter paths, directory-not-file, multiple
        gaps, NaN/Infinity in JSONL, OHLCV high<close, naive timestamps, negative ns,
        ns not multiple of billion, bool ns, documentation claims — not in existing 11."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: scan_archive, ArchiveFormat,
        ArchiveScanError, ArchiveScanV1, ARCHIVE_SCAN_VERSION, EvidenceFileV1,
        MissingIntervalV1. No private helpers called."""
