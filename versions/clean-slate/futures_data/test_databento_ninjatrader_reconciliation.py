import json
from hashlib import sha256
from pathlib import Path

import pytest

from futures_data.databento_ninjatrader_reconciliation import (
    NINJA_VERSION, ReconciliationError, _canonical, reconcile,
)


def ninja_file(path: Path, rows):
    previous = "0" * 64
    encoded = []
    for minute, close in rows:
        body = {"close": close, "close_time_utc": minute.replace(":00Z", ":01:00Z"),
                "high": "101", "instrument": "MES SEP26", "low": "99",
                "market": "ES", "open": "100", "open_time_utc": minute,
                "paper_only": True, "previous_record_sha256": previous,
                "schema_version": NINJA_VERSION, "source_payload_sha256": "a" * 64,
                "trading_authority": False, "volume": 10}
        digest = sha256(_canonical(body)).hexdigest(); previous = digest
        encoded.append(_canonical({**body, "record_sha256": digest}))
    path.write_bytes(b"\n".join(encoded) + b"\n")


def db_file(path: Path, rows):
    docs = [{"hd": {"ts_event": minute, "instrument_id": 7}, "open": "100",
             "high": "101", "low": "99", "close": close, "volume": "10"}
            for minute, close in rows]
    path.write_bytes(b"\n".join(_canonical(row) for row in docs) + b"\n")


def test_reconciliation_matches_without_merging(tmp_path: Path):
    minute = "2026-09-10T15:00:00Z"; ninja = tmp_path / "n.jsonl"; db = tmp_path / "d.jsonl"
    ninja_file(ninja, [(minute, "100.5")]); db_file(db, [(minute, "100.500")])
    report = reconcile(lane="ES", session_date="2026-09-10", ninja_path=ninja, databento_path=db)
    assert report["state"] == "MATCHED" and report["matched_minute_count"] == 1
    assert report["cross_source_merge_performed"] is False
    assert report["trading_authority"] is False


def test_reconciliation_reports_gaps_and_conflicts(tmp_path: Path):
    a = "2026-09-10T15:00:00Z"; b = "2026-09-10T15:01:00Z"
    ninja = tmp_path / "n.jsonl"; db = tmp_path / "d.jsonl"
    ninja_file(ninja, [(a, "100.5")]); db_file(db, [(a, "100.75"), (b, "100.5")])
    report = reconcile(lane="ES", session_date="2026-09-10", ninja_path=ninja, databento_path=db)
    assert report["state"] == "REVIEW_REQUIRED"
    assert report["price_or_volume_conflict_count"] == 1
    assert report["price_conflict_count"] == 1
    assert report["volume_only_conflict_count"] == 0
    assert report["missing_ninjatrader_count"] == 1
    assert report["recovery_candidates_are_noncanonical"] is True


def test_tampered_ninja_chain_fails_closed(tmp_path: Path):
    minute = "2026-09-10T15:00:00Z"; ninja = tmp_path / "n.jsonl"; db = tmp_path / "d.jsonl"
    ninja_file(ninja, [(minute, "100.5")]); db_file(db, [(minute, "100.5")])
    text = ninja.read_text().replace('"close":"100.5"', '"close":"100.75"')
    ninja.write_text(text)
    with pytest.raises(ReconciliationError, match="chain invalid"):
        reconcile(lane="ES", session_date="2026-09-10", ninja_path=ninja, databento_path=db)


def test_record_outside_declared_day_fails_closed(tmp_path: Path):
    minute = "2026-09-10T15:00:00Z"; ninja = tmp_path / "n.jsonl"; db = tmp_path / "d.jsonl"
    ninja_file(ninja, [(minute, "100.5")]); db_file(db, [(minute, "100.5")])
    with pytest.raises(ReconciliationError, match="outside declared"):
        reconcile(lane="ES", session_date="2026-09-09", ninja_path=ninja, databento_path=db)
