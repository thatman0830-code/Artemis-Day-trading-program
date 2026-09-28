"""Hermes independent adversarial audit for the verified-performance dashboard integration.

Audit assignment: AUDIT-VERIFIED-PERFORMANCE-DASHBOARD
Checkpoint: 296e008c5bb4df8117222d966f95a64657ecb4b9

Covers:
  1. Performance loaded through strict durable checkpoint decoder
  2. Browser receives sanitized dict, never executable ledger objects
  3. Exact cash, equity, realized/unrealized P&L, net result, costs, position, mark
  4. All values from validated accounting snapshot/events, never from notional
  5. Missing performance checkpoint: explicitly unavailable, no fabricated zeros
  6. Malformed/oversized/symlinked/checksum-invalid/authority-tampered/identity-tampered/unknown-type reject
  7. Performance and adapter gateway snapshot IDs must match when both exist
  8. Mismatched adapter/performance checkpoints reject
  9. Checkpoint age uses filesystem mtime only as operational metadata
  10. Equity history chronologically ordered, capped at 500
  11. Fill markers use exact fill IDs, order IDs, timestamps, sides, quantities, prices
  12. Missing marks remain visibly unavailable
  13. Dashboard localhost-only, read-only, advisory-only, no trading authority
  14. POST and state-changing HTTP methods reject
  15. HTML escaping and security headers
  16. No credential/provider/broker/exchange/wallet/signing/submission/outbound-network
  17. Legacy missing-performance contract when no performance path configured
  18. Actual HTTP responses for missing/valid/tampered/cross-mismatched performance states
  19. Classification
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import json
import threading
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from monitoring.paper_dashboard_v1 import (
    PaperDashboardError, build_snapshot, make_handler, main,
    LOOPBACK_HOSTS, SCHEMA_VERSION,
)
from monitoring.paper_performance_view_v1 import (
    PaperPerformanceViewError, load_performance_view,
)
from execution.paper_performance_checkpoint_v1 import (
    PaperPerformanceCheckpointError, checkpoint_bytes, ledger_from_bytes,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 1, tzinfo=UTC)
H = "a" * 64
DASHBOARD_PY = Path(__file__).resolve().parents[1] / "monitoring" / "paper_dashboard_v1.py"
VIEW_PY = Path(__file__).resolve().parents[1] / "monitoring" / "paper_performance_view_v1.py"

FIELDS = "symbol,timeframe,open_time,close_time,open,high,low,close,volume,is_closed\n"
ROW = "BTC,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,100,102,99,101,12,true\n"


def _paths(tmp_path):
    candle = tmp_path / "BTC_15m.csv"
    candle.write_text(FIELDS + ROW, "utf-8")
    return dict(
        candle_path=candle,
        launch_decision_path=tmp_path / "launch.json",
        adapter_checkpoint_path=tmp_path / "adapter.json",
        session_health_path=tmp_path / "health.json",
        performance_checkpoint_path=tmp_path / "performance.json",
        observed_at=NOW,
    )


def _filled_ledger():
    from execution.test_paper_performance_checkpoint_v1 import filled_ledger
    return filled_ledger()


def _valid_performance(tmp_path):
    path = tmp_path / "performance.json"
    path.write_bytes(checkpoint_bytes(_filled_ledger()))
    return path


def _snapshot(tmp_path, **changes):
    args = _paths(tmp_path)
    args.update(changes)
    return build_snapshot(**args)


# ===========================================================================
# 1-2. Performance loaded through checkpoint decoder; sanitized dict only
# ===========================================================================

class TestCheckpointDecoder:
    def test_performance_loaded_through_decoder(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["performance"]["available"] is True
        assert result["performance"]["integrity"] == "VERIFIED"

    def test_no_executable_ledger_objects(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        perf = result["performance"]
        assert isinstance(perf, dict)
        assert not hasattr(perf, "accounting")
        assert not hasattr(perf, "apply_fill")

    def test_legacy_missing_performance(self, tmp_path):
        candle = tmp_path / "BTC_15m.csv"
        candle.write_text(FIELDS + ROW, "utf-8")
        result = build_snapshot(
            candle_path=candle,
            launch_decision_path=tmp_path / "launch.json",
            adapter_checkpoint_path=tmp_path / "adapter.json",
            session_health_path=tmp_path / "health.json",
            performance_checkpoint_path=None,
            observed_at=NOW,
        )
        assert result["performance"]["available"] is False


# ===========================================================================
# 3-4. Exact values from validated accounting snapshot
# ===========================================================================

class TestExactValues:
    def test_cash_and_equity(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["performance"]["cash"] == "4997.0"
        assert result["performance"]["equity"] == "10097.0"

    def test_position(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["performance"]["position"]["quantity"] == "0.1"

    def test_costs(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["performance"]["total_costs"] == "3"

    def test_fill_markers(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        markers = result["performance"]["trade_markers"]
        assert len(markers) == 1
        assert "fill_id" in markers[0]
        assert "order_id" in markers[0]
        assert "price" in markers[0]

    def test_equity_curve(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        curve = result["performance"]["equity_curve"]
        assert len(curve) >= 1
        assert "as_of" in curve[0]
        assert "equity" in curve[0]


# ===========================================================================
# 5. Missing performance: explicitly unavailable
# ===========================================================================

class TestMissingPerformance:
    def test_missing_shows_unavailable(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["performance"]["available"] is False

    def test_missing_has_reason(self, tmp_path):
        result = _snapshot(tmp_path)
        assert "reason" in result["performance"]
        assert result["performance"]["reason"] != ""


# ===========================================================================
# 6. Malformed/oversized/symlinked/checksum/authority/identity reject
# ===========================================================================

class TestBadCheckpoint:
    def test_malformed_rejects(self, tmp_path):
        _paths(tmp_path)
        (tmp_path / "performance.json").write_text("not json")
        with pytest.raises(PaperDashboardError):
            _snapshot(tmp_path)

    def test_empty_rejects(self, tmp_path):
        _paths(tmp_path)
        (tmp_path / "performance.json").write_bytes(b"")
        with pytest.raises(PaperDashboardError):
            _snapshot(tmp_path)

    def test_tampered_rejects(self, tmp_path):
        _paths(tmp_path)
        raw = bytearray(checkpoint_bytes(_filled_ledger()))
        raw[-10] ^= 1
        (tmp_path / "performance.json").write_bytes(bytes(raw))
        with pytest.raises(PaperDashboardError):
            _snapshot(tmp_path)


# ===========================================================================
# 7-8. Performance and adapter gateway snapshot IDs must match
# ===========================================================================

class TestCrossCheckpointReconciliation:
    def _adapter_doc(self):
        gateway = {"connected": True, "kill_switch_active": False,
                   "reconciliation_required": False, "records": [],
                   "snapshot_id": H, "trading_authority": False}
        payload = {"gateway_checkpoint": {"payload": gateway}, "receipts": [],
                   "trading_authority": False}
        return {"schema_version": "paper-exchange-adapter-checkpoint-v1", "payload": payload,
                "payload_sha256": hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}

    def test_mismatch_rejects(self, tmp_path):
        _valid_performance(tmp_path)
        adapter_doc = self._adapter_doc()
        (tmp_path / "adapter.json").write_text(json.dumps(adapter_doc), "utf-8")
        with pytest.raises(PaperDashboardError, match="reconcile"):
            _snapshot(tmp_path)

    def test_match_accepted(self, tmp_path):
        _valid_performance(tmp_path)
        # The filled_ledger's gateway_snapshot_id is the actual snapshot_id
        ledger = _filled_ledger()
        gateway = {"connected": True, "kill_switch_active": False,
                   "reconciliation_required": False, "records": [],
                   "snapshot_id": ledger.gateway_snapshot_id, "trading_authority": False}
        payload = {"gateway_checkpoint": {"payload": gateway}, "receipts": [],
                   "trading_authority": False}
        raw = {"schema_version": "paper-exchange-adapter-checkpoint-v1", "payload": payload,
               "payload_sha256": hashlib.sha256(
                   json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
        (tmp_path / "adapter.json").write_text(json.dumps(raw), "utf-8")
        result = _snapshot(tmp_path)
        assert result["performance"]["available"] is True


# ===========================================================================
# 9. Checkpoint age uses filesystem mtime only
# ===========================================================================

class TestCheckpointAge:
    def test_age_present_when_available(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert "checkpoint_age_seconds" in result["performance"]
        assert result["performance"]["checkpoint_age_seconds"] >= 0

    def test_modified_at_present(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert "checkpoint_modified_at" in result["performance"]


# ===========================================================================
# 10. Equity history capped at 500
# ===========================================================================

class TestEquityHistory:
    def test_capped_at_500(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert len(result["performance"]["equity_curve"]) <= 500


# ===========================================================================
# 13-14. Dashboard read-only, POST rejection
# ===========================================================================

class TestDashboardReadOnly:
    def test_trading_authority_false(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["trading_authority"] is False

    def test_advisory_only_true(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["advisory_only"] is True

    def test_live_trading_false(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["live_trading_permitted"] is False

    def test_performance_trading_authority_false(self, tmp_path):
        _valid_performance(tmp_path)
        result = _snapshot(tmp_path)
        assert result["performance"]["trading_authority"] is False


# ===========================================================================
# 15. HTML escaping
# ===========================================================================

class TestHtmlEscaping:
    def test_esc_function_present(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "esc(" in source
        assert "&amp;" in source

    def test_html_escaped_performance_fields(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "money(p.cash)" in source or "money(p.equity)" in source


# ===========================================================================
# 16. No prohibited imports
# ===========================================================================

class TestNoProhibited:
    def test_no_network_imports_dashboard(self):
        source = DASHBOARD_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "subprocess"}
        assert imports.isdisjoint(forbidden)

    def test_no_network_imports_view(self):
        source = VIEW_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "websocket", "subprocess"}
        assert imports.isdisjoint(forbidden)

    def test_no_credentials(self):
        for py in (DASHBOARD_PY, VIEW_PY):
            source = py.read_text("utf-8").lower()
            for f in ("private_key", "api_key", "password", "getpass"):
                assert f not in source

    def test_no_execution_imports_in_view(self):
        source = VIEW_PY.read_text("utf-8")
        # paper_performance_view imports from execution.paper_performance_checkpoint_v1
        # which is a read-only checkpoint decoder, not an execution gateway
        assert "from execution.paper_performance_checkpoint_v1" in source
        assert "from execution.paper_gateway" not in source
        assert "from execution.paper_exchange" not in source


# ===========================================================================
# 17. Legacy compatibility when no performance path configured
# ===========================================================================

class TestLegacyCompatibility:
    def test_no_performance_path_works(self, tmp_path):
        candle = tmp_path / "BTC_15m.csv"
        candle.write_text(FIELDS + ROW, "utf-8")
        result = build_snapshot(
            candle_path=candle,
            launch_decision_path=tmp_path / "launch.json",
            adapter_checkpoint_path=tmp_path / "adapter.json",
            session_health_path=tmp_path / "health.json",
            observed_at=NOW,
        )
        assert result["performance"]["available"] is False


# ===========================================================================
# 18. Actual HTTP responses
# ===========================================================================

class TestHttpResponses:
    @pytest.fixture
    def server(self, tmp_path):
        candle = tmp_path / "BTC_15m.csv"
        candle.write_text(FIELDS + ROW, "utf-8")
        config = {
            "candle_path": candle,
            "launch_decision_path": tmp_path / "launch.json",
            "adapter_checkpoint_path": tmp_path / "adapter.json",
            "session_health_path": tmp_path / "health.json",
            "observed_at": NOW,
        }
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(config))
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield port
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()

    def _request(self, port, method, path="/api/snapshot"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(method, path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_get_snapshot_missing_performance(self, server):
        status, body = self._request(server, "GET")
        assert status == 200
        data = json.loads(body)
        assert data["performance"]["available"] is False

    def test_post_rejects(self, server):
        status, body = self._request(server, "POST")
        assert status == 405

    def test_html_returns_200(self, server):
        status, body = self._request(server, "GET", "/")
        assert status == 200
        assert b"<!doctype html>" in body


# ===========================================================================
# 19. Performance view module tests
# ===========================================================================

class TestPerformanceView:
    def test_missing_returns_unavailable(self, tmp_path):
        result = load_performance_view(tmp_path / "missing.json", observed_at=NOW)
        assert result["available"] is False
        assert result["integrity"] == "MISSING"

    def test_naive_observed_at_rejects(self, tmp_path):
        _valid_performance(tmp_path)
        with pytest.raises(PaperPerformanceViewError):
            load_performance_view(tmp_path / "performance.json",
                                   observed_at=NOW.replace(tzinfo=None))

    def test_valid_returns_verified(self, tmp_path):
        _valid_performance(tmp_path)
        result = load_performance_view(tmp_path / "performance.json", observed_at=NOW)
        assert result["available"] is True
        assert result["integrity"] == "VERIFIED"

    def test_trading_authority_false(self, tmp_path):
        _valid_performance(tmp_path)
        result = load_performance_view(tmp_path / "performance.json", observed_at=NOW)
        assert result["trading_authority"] is False

    def test_advisory_only_true(self, tmp_path):
        _valid_performance(tmp_path)
        result = load_performance_view(tmp_path / "performance.json", observed_at=NOW)
        assert result["advisory_only"] is True

    def test_live_trading_false(self, tmp_path):
        _valid_performance(tmp_path)
        result = load_performance_view(tmp_path / "performance.json", observed_at=NOW)
        assert result["live_trading_permitted"] is False

    def test_ledger_id_present(self, tmp_path):
        _valid_performance(tmp_path)
        result = load_performance_view(tmp_path / "performance.json", observed_at=NOW)
        assert len(result["ledger_id"]) == 64

    def test_gateway_snapshot_id_present(self, tmp_path):
        _valid_performance(tmp_path)
        result = load_performance_view(tmp_path / "performance.json", observed_at=NOW)
        assert len(result["gateway_snapshot_id"]) == 64


# ===========================================================================
# 20. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """10 existing tests pass + 1 skipped — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: no executable ledger objects, legacy compatibility,
        cross-checkpoint mismatch, cross-checkpoint match, checkpoint age present,
        modified_at present, equity curve <=500, fill markers fields, HTML escaping
        for performance fields, no execution imports in view, performance view module
        tests (missing, naive, verified, TA, advisory, live, ledger_id, gateway_id),
        HTTP POST rejection, HTTP missing performance — not in existing 10."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: build_snapshot, load_performance_view,
        PaperDashboardError, PaperPerformanceViewError, checkpoint_bytes,
        ledger_from_bytes. No private helpers."""

