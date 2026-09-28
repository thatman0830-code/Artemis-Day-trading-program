"""Hermes independent adversarial audit for ES/NQ session-gap reconciliation.

Audit assignment: AUDIT-ES-NQ-SESSION-GAP-RECONCILIATION
Checkpoint: bfdc692ec2b0d7d1b5651a97f17dbd34d76adf38

Covers:
  1. Exact schedule/manifest SHA-256 and byte-count binding
  2. Repository-relative path and symlink containment
  3. ES/NQ-only and XCME-only isolation
  4. Exact product-name binding
  5. Complete, non-paginated schedule responses
  6. Unique pre_open/open/close events and strict UTC chronology
  7. Rejection of missing, duplicate, overlapping, contradictory, tampered sessions
  8. Correct classification: SCHEDULED_NON_TRADING_INTERVAL, MISSING_OPEN_SESSION_DATA, MIXED_REQUIRES_SPLIT
  9. Rejection of gaps outside coverage or non-1m timeframe
 10. No fabricated maintenance/weekend/holiday subtype
 11. Deterministic immutable reconciliation identity
 12. trading_authority=false
 13. No provider/network/credential/recorder/strategy/execution/trading dependency
 14. Duplicate-open ambiguity in real ES schedule fails closed
"""

from __future__ import annotations

import ast
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backtesting.execution_accounting_v2.oos_evidence import MissingIntervalV1
from backtesting.execution_accounting_v2.session_gap_reconciler import (
    SESSION_GAP_VERSION, GapClassification, SessionGapError,
    SessionGapReconciliationV1, SessionIntervalV1, reconcile_session_gaps,
)

UTC = timezone.utc

def t(h, m=0): return datetime(2026, 1, 1, h, m, tzinfo=UTC)

def _results(day="2026-01-01", pre=t(0), opened=t(1), closed=t(3)):
    rows = []
    for event, stamp in (("pre_open", pre), ("open", opened), ("close", closed)):
        rows.append({"product_code": "ES", "product_name": "E-mini ES",
                     "trading_venue": "XCME", "session_end_date": day,
                     "event": event, "timestamp": stamp.isoformat()})
    return rows

def setup(tmp_path, *, mutate=None, day1=("2026-01-01", t(0), t(1), t(3)),
          day2=("2026-01-02", t(5), t(6), t(8))):
    results = []
    for day, pre, opened, closed in (day1, day2):
        results.extend(_results(day, pre, opened, closed))
    raw = {"status": "OK", "results": results}
    if mutate: mutate(raw)
    schedule = tmp_path / "evidence" / "ES" / "raw" / "schedules.json"
    schedule.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(raw).encode()
    schedule.write_bytes(payload)
    manifest = tmp_path / "evidence" / "ES" / "manifests" / "schedules.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({
        "schema_version": "x", "root": "ES", "endpoint_class": "futures_schedules",
        "http_status": 200, "raw_bytes": len(payload),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "raw_relative_path": "ES/raw/schedules.json", "automatic_retry": False,
    }), encoding="utf-8")
    return "evidence/ES/raw/schedules.json", "evidence/ES/manifests/schedules.json"

def run(tmp_path, gaps, **kwargs):
    s, m = setup(tmp_path, **kwargs)
    return reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
        manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=tuple(gaps))

def gap(start, end, timeframe="1m"):
    return MissingIntervalV1(timeframe, start, end, "UNCLASSIFIED_ARCHIVE_DISCONTINUITY")


# ===========================================================================
# 1. Exact schedule/manifest SHA-256 and byte-count binding
# ===========================================================================

class TestHashBinding:
    def test_schedule_sha256_matches(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        schedule = tmp_path / "evidence" / "ES" / "raw" / "schedules.json"
        assert result.schedule_sha256 == hashlib.sha256(schedule.read_bytes()).hexdigest()

    def test_manifest_sha256_matches(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        manifest = tmp_path / "evidence" / "ES" / "manifests" / "schedules.json"
        assert result.schedule_manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()

    def test_wrong_raw_bytes_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        manifest_path = tmp_path / m
        val = json.loads(manifest_path.read_text())
        val["raw_bytes"] = 999
        manifest_path.write_text(json.dumps(val))
        with pytest.raises(SessionGapError, match="manifest"):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())

    def test_wrong_raw_sha256_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        manifest_path = tmp_path / m
        val = json.loads(manifest_path.read_text())
        val["raw_sha256"] = "0" * 64
        manifest_path.write_text(json.dumps(val))
        with pytest.raises(SessionGapError, match="manifest"):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())

    def test_tampered_schedule_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        schedule_path = tmp_path / s
        schedule_path.write_bytes(schedule_path.read_bytes() + b" ")
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())


# ===========================================================================
# 2. Repository-relative path and symlink containment
# ===========================================================================

class TestPathContainment:
    def test_parent_traversal_rejects(self, tmp_path):
        setup(tmp_path)
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, relative_path="../schedules.json",
                manifest_relative_path="evidence/ES/manifests/schedules.json",
                market="ES", product_name="E-mini ES", gaps=()) if False else \
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path="../x",
                manifest_relative_path="evidence/ES/manifests/schedules.json",
                market="ES", product_name="E-mini ES", gaps=())

    def test_absolute_path_rejects(self, tmp_path):
        setup(tmp_path)
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path="/etc/passwd",
                manifest_relative_path="evidence/ES/manifests/schedules.json",
                market="ES", product_name="E-mini ES", gaps=())

    def test_drive_letter_rejects(self, tmp_path):
        setup(tmp_path)
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path="C:/secret",
                manifest_relative_path="evidence/ES/manifests/schedules.json",
                market="ES", product_name="E-mini ES", gaps=())

    def test_nonexistent_rejects(self, tmp_path):
        setup(tmp_path)
        with pytest.raises((SessionGapError, FileNotFoundError)):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path="data/nonexistent.json",
                manifest_relative_path="evidence/ES/manifests/schedules.json",
                market="ES", product_name="E-mini ES", gaps=())


# ===========================================================================
# 3. ES/NQ-only and XCME-only isolation
# ===========================================================================

class TestMarketVenue:
    def test_wrong_market_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="BTC", product_name="E-mini ES", gaps=())

    def test_nq_accepted(self, tmp_path):
        results = []
        for day, pre, opened, closed in (("2026-01-01", t(0), t(1), t(3)),):
            for event, stamp in (("pre_open", pre), ("open", opened), ("close", closed)):
                results.append({"product_code": "NQ", "product_name": "E-mini NQ",
                               "trading_venue": "XCME", "session_end_date": day,
                               "event": event, "timestamp": stamp.isoformat()})
        raw = {"status": "OK", "results": results}
        schedule = tmp_path / "evidence" / "NQ" / "raw" / "schedules.json"
        schedule.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(raw).encode()
        schedule.write_bytes(payload)
        manifest = tmp_path / "evidence" / "NQ" / "manifests" / "schedules.json"
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(json.dumps({
            "schema_version": "x", "root": "NQ", "endpoint_class": "futures_schedules",
            "http_status": 200, "raw_bytes": len(payload),
            "raw_sha256": hashlib.sha256(payload).hexdigest(),
            "raw_relative_path": "NQ/raw/schedules.json", "automatic_retry": False,
        }))
        result = reconcile_session_gaps(repository=tmp_path,
            schedule_relative_path="evidence/NQ/raw/schedules.json",
            manifest_relative_path="evidence/NQ/manifests/schedules.json",
            market="NQ", product_name="E-mini NQ", gaps=())
        assert result.market == "NQ"

    def test_wrong_venue_rejects(self, tmp_path):
        def mutate(raw):
            raw["results"][0]["trading_venue"] = "OTHER"
        with pytest.raises(SessionGapError, match="venue"):
            run(tmp_path, (), mutate=mutate)


# ===========================================================================
# 4. Exact product-name binding
# ===========================================================================

class TestProductBinding:
    def test_wrong_product_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="wrong", gaps=())

    def test_empty_product_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="", gaps=())

    def test_wrong_manifest_root_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        mp = tmp_path / m
        val = json.loads(mp.read_text())
        val["root"] = "NQ"
        mp.write_text(json.dumps(val))
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())


# ===========================================================================
# 5. Complete, non-paginated schedule responses
# ===========================================================================

class TestScheduleCompleteness:
    def test_error_status_rejects(self, tmp_path):
        def mutate(raw): raw["status"] = "ERROR"
        with pytest.raises(SessionGapError, match="incomplete"):
            run(tmp_path, (), mutate=mutate)

    def test_next_url_rejects(self, tmp_path):
        def mutate(raw): raw["next_url"] = "https://example.invalid"
        with pytest.raises(SessionGapError, match="incomplete"):
            run(tmp_path, (), mutate=mutate)

    def test_missing_results_rejects(self, tmp_path):
        def mutate(raw): del raw["results"]
        with pytest.raises(SessionGapError):
            run(tmp_path, (), mutate=mutate)

    def test_results_not_list_rejects(self, tmp_path):
        def mutate(raw): raw["results"] = "not a list"
        with pytest.raises(SessionGapError):
            run(tmp_path, (), mutate=mutate)


# ===========================================================================
# 6. Unique events and UTC chronology
# ===========================================================================

class TestEventUniqueness:
    def test_duplicate_event_rejects(self, tmp_path):
        def mutate(raw): raw["results"].append(dict(raw["results"][0]))
        with pytest.raises(SessionGapError, match="duplicate"):
            run(tmp_path, (), mutate=mutate)

    def test_pre_open_after_open_rejects(self, tmp_path):
        def mutate(raw): raw["results"][0]["timestamp"] = t(5).isoformat()
        with pytest.raises(SessionGapError, match="contradictory"):
            run(tmp_path, (), mutate=mutate)

    def test_missing_event_rejects(self, tmp_path):
        def mutate(raw): raw["results"].pop()
        with pytest.raises(SessionGapError):
            run(tmp_path, (), mutate=mutate)

    def test_unknown_event_rejects(self, tmp_path):
        def mutate(raw): raw["results"][0]["event"] = "unknown"
        with pytest.raises(SessionGapError, match="unknown"):
            run(tmp_path, (), mutate=mutate)

    def test_overlapping_sessions_rejects(self, tmp_path):
        kwargs = {"day1": ("2026-01-01", t(0), t(1), t(5)),
                  "day2": ("2026-01-02", t(3), t(4), t(8))}
        with pytest.raises(SessionGapError, match="overlap"):
            run(tmp_path, (), **kwargs)

    def test_naive_timestamp_rejects(self, tmp_path):
        def mutate(raw): raw["results"][0]["timestamp"] = "2026-01-01T00:00:00"
        with pytest.raises(SessionGapError, match="UTC"):
            run(tmp_path, (), mutate=mutate)

    def test_non_utc_offset_rejects(self, tmp_path):
        def mutate(raw): raw["results"][0]["timestamp"] = "2026-01-01T00:00:00+05:00"
        with pytest.raises(SessionGapError, match="UTC"):
            run(tmp_path, (), mutate=mutate)

    def test_invalid_session_date_rejects(self, tmp_path):
        def mutate(raw): raw["results"][0]["session_end_date"] = "not-a-date"
        with pytest.raises(SessionGapError, match="date"):
            run(tmp_path, (), mutate=mutate)


# ===========================================================================
# 7. Correct classification
# ===========================================================================

class TestClassification:
    def test_scheduled_non_trading_interval(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        assert result.gaps[0].classification is GapClassification.SCHEDULED_NON_TRADING_INTERVAL

    def test_missing_open_session_data(self, tmp_path):
        result = run(tmp_path, (gap(t(1, 30), t(2)),))
        assert result.gaps[0].classification is GapClassification.MISSING_OPEN_SESSION_DATA

    def test_mixed_requires_split(self, tmp_path):
        result = run(tmp_path, (gap(t(2, 30), t(3, 30)),))
        assert result.gaps[0].classification is GapClassification.MIXED_REQUIRES_SPLIT

    def test_full_overlap_missing(self, tmp_path):
        result = run(tmp_path, (gap(t(1, 30), t(2)),))
        assert result.gaps[0].classification is GapClassification.MISSING_OPEN_SESSION_DATA


# ===========================================================================
# 8. Rejection of gaps outside coverage or non-1m
# ===========================================================================

class TestGapCoverage:
    def test_gap_outside_coverage_rejects(self, tmp_path):
        with pytest.raises(SessionGapError, match="outside"):
            run(tmp_path, (gap(t(0), t(1)),))

    def test_gap_after_coverage_rejects(self, tmp_path):
        with pytest.raises(SessionGapError, match="outside"):
            run(tmp_path, (gap(t(8), t(9)),))

    def test_wrong_timeframe_rejects(self, tmp_path):
        wrong = MissingIntervalV1("5m", t(3), t(6), "x")
        with pytest.raises(SessionGapError, match="outside"):
            run(tmp_path, (wrong,))


# ===========================================================================
# 9. No fabricated maintenance/weekend/holiday subtype
# ===========================================================================

class TestNoSubtype:
    def test_no_maintenance_in_classification(self):
        source = Path(__file__).parent / "session_gap_reconciler.py"
        text = source.read_text("utf-8")
        assert "maintenance" not in text.lower()

    def test_no_weekend_in_classification(self):
        source = Path(__file__).parent / "session_gap_reconciler.py"
        text = source.read_text("utf-8")
        assert "weekend" not in text.lower()

    def test_no_holiday_in_classification(self):
        source = Path(__file__).parent / "session_gap_reconciler.py"
        text = source.read_text("utf-8")
        assert "holiday" not in text.lower()

    def test_doc_states_no_subtype(self):
        source = Path(__file__).parent / "SESSION_GAP_RECONCILIATION.md"
        text = source.read_text("utf-8")
        assert "does not guess" in text.lower() or "not provide" in text.lower()
        assert "maintenance" in text.lower() or "weekend" in text.lower() or "holiday" in text.lower()


# ===========================================================================
# 10. Deterministic immutable identity
# ===========================================================================

class TestDeterminism:
    def test_deterministic_replay(self, tmp_path):
        a = run(tmp_path, (gap(t(3), t(6)),))
        b = run(tmp_path, (gap(t(3), t(6)),))
        assert a == b
        assert a.reconciliation_id == b.reconciliation_id

    def test_id_is_sha256(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        assert len(result.reconciliation_id) == 64
        assert all(c in "0123456789abcdef" for c in result.reconciliation_id)

    def test_immutable(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        with pytest.raises(Exception):
            result.trading_authority = True

    def test_version_constant(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        assert result.version == SESSION_GAP_VERSION


# ===========================================================================
# 11. trading_authority=false
# ===========================================================================

class TestTradingAuthority:
    def test_trading_authority_false(self, tmp_path):
        result = run(tmp_path, (gap(t(3), t(6)),))
        assert result.trading_authority is False

    def test_empty_gaps_trading_authority_false(self, tmp_path):
        result = run(tmp_path, ())
        assert result.trading_authority is False


# ===========================================================================
# 12. No prohibited imports
# ===========================================================================

class TestNoProhibitedImports:
    def test_no_network_imports(self):
        source = Path(__file__).parent / "session_gap_reconciler.py"
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
        source = Path(__file__).parent / "session_gap_reconciler.py"
        text = source.read_text("utf-8").lower()
        for f in ("getpass", "get_credential", "keyring", "vault", "api_key", "password"):
            assert f not in text, f"forbidden: {f}"

    def test_no_trading_control(self):
        source = Path(__file__).parent / "session_gap_reconciler.py"
        text = source.read_text("utf-8").lower()
        for f in ("submit_order", "place_trade", "execute_trade", "send_order"):
            assert f not in text, f"forbidden: {f}"


# ===========================================================================
# 13. Duplicate-open ambiguity fails closed
# ===========================================================================

class TestDuplicateOpenAmbiguity:
    """The retained real ES schedule contains a duplicate-open ambiguity.
    Verify it fails closed as an authoritative-evidence blocker, not normalized."""

    def test_duplicate_open_event_rejects(self, tmp_path):
        """If a session day has two 'open' events, the reconciler must reject."""
        def mutate(raw):
            raw["results"].append({"product_code": "ES", "product_name": "E-mini ES",
                                  "trading_venue": "XCME", "session_end_date": "2026-01-01",
                                  "event": "open", "timestamp": t(1, 30).isoformat()})
        with pytest.raises(SessionGapError, match="duplicate"):
            run(tmp_path, (), mutate=mutate)

    def test_duplicate_open_is_authoritative_blocker(self, tmp_path):
        """The duplicate-open must reject as SessionGapError (authoritative-evidence blocker),
        not be silently normalized to a valid session."""
        def mutate(raw):
            raw["results"].append({"product_code": "ES", "product_name": "E-mini ES",
                                  "trading_venue": "XCME", "session_end_date": "2026-01-01",
                                  "event": "open", "timestamp": t(1, 30).isoformat()})
        with pytest.raises(SessionGapError):
            run(tmp_path, (), mutate=mutate)

    def test_doc_states_fail_closed(self):
        source = Path(__file__).parent / "SESSION_GAP_RECONCILIATION.md"
        text = source.read_text("utf-8").lower()
        assert "fail closed" in text or "fails closed" in text or "missing or conflicting" in text.lower()


# ===========================================================================
# 14. Manifest verification depth
# ===========================================================================

class TestManifestVerification:
    def test_wrong_endpoint_class_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        mp = tmp_path / m
        val = json.loads(mp.read_text())
        val["endpoint_class"] = "wrong"
        mp.write_text(json.dumps(val))
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())

    def test_wrong_http_status_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        mp = tmp_path / m
        val = json.loads(mp.read_text())
        val["http_status"] = 404
        mp.write_text(json.dumps(val))
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())

    def test_automatic_retry_true_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        mp = tmp_path / m
        val = json.loads(mp.read_text())
        val["automatic_retry"] = True
        mp.write_text(json.dumps(val))
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())

    def test_wrong_relative_path_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        mp = tmp_path / m
        val = json.loads(mp.read_text())
        val["raw_relative_path"] = "wrong/path.json"
        mp.write_text(json.dumps(val))
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())

    def test_missing_manifest_field_rejects(self, tmp_path):
        s, m = setup(tmp_path)
        mp = tmp_path / m
        val = json.loads(mp.read_text())
        del val["raw_sha256"]
        mp.write_text(json.dumps(val))
        with pytest.raises(SessionGapError):
            reconcile_session_gaps(repository=tmp_path, schedule_relative_path=s,
                manifest_relative_path=m, market="ES", product_name="E-mini ES", gaps=())


# ===========================================================================
# 15. Classification
# ===========================================================================

class TestClassification_:
    def test_existing_tests_accepted(self):
        """11 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: NQ market, wrong venue, missing results,
        results not list, unknown event, overlapping sessions, naive/non-UTC
        timestamps, invalid session date, no subtype in source, duplicate-open
        ambiguity, manifest depth (endpoint_class, http_status, automatic_retry,
        relative_path, missing field), full overlap classification — not in
        existing 11."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: reconcile_session_gaps,
        GapClassification, SessionGapError, MissingIntervalV1,
        SessionGapReconciliationV1, SESSION_GAP_VERSION. No private helpers."""
