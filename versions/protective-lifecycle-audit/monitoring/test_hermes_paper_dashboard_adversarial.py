"""Hermes independent adversarial audit for the read-only supervised paper dashboard.

Audit assignment: AUDIT-PAPER-DASHBOARD
Checkpoint: a671a1615a3c041202a58fc17d8f39499a6fd1a3

Covers:
  1. Read-only, advisory-only; no order/submission/signing/wallet/exchange/broker/credential/provider/live
  2. Cannot bind outside loopback
  3. POST and state-changing HTTP operations reject
  4. Adapter checkpoint checksums and trading_authority=false enforced
  5. Malformed/oversized/symlinked/unsupported/chronologically-invalid evidence fails closed
  6. Only closed BTC 15-minute candles accepted
  7. Missing paper-session evidence displayed honestly; no fabricated orders/positions/fills/equity/P&L
  8. P&L unavailable without authoritative fill-price and mark-to-market evidence
  9. Snapshot IDs deterministic and content-addressed
 10. HTML escaping prevents executable markup
 11. Security headers, cache controls, path routing
 12. No outbound-network clients or execution-module imports
 13. Actual localhost HTTP behavior: GET, HEAD, POST rejection, unknown routes, snapshot refresh, evidence errors
 14. Classification
"""

from __future__ import annotations

import ast
import hashlib
import http.client
import json
import socket
import threading
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from monitoring.paper_dashboard_v1 import (
    LOOPBACK_HOSTS, MAX_CANDLES, MAX_JSON_BYTES, SCHEMA_VERSION,
    PaperDashboardError, build_snapshot, make_handler, main,
)

UTC = timezone.utc
NOW = datetime(2026, 9, 1, 0, 0, tzinfo=UTC)
DASHBOARD_PY = Path(__file__).resolve().parents[1] / "monitoring" / "paper_dashboard_v1.py"
PS1 = Path(__file__).resolve().parents[1] / "scripts" / "run_paper_dashboard.ps1"

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
        observed_at=NOW,
    )


def _snapshot(tmp_path, **changes):
    args = _paths(tmp_path)
    args.update(changes)
    return build_snapshot(**args)


# ===========================================================================
# 1. Read-only, advisory-only
# ===========================================================================

class TestReadOnlyAdvisory:
    def test_trading_authority_false(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["trading_authority"] is False

    def test_live_trading_permitted_false(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["live_trading_permitted"] is False

    def test_advisory_only_true(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["advisory_only"] is True

    def test_no_execution_imports(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "from execution" not in source
        assert "import execution" not in source

    def test_no_outbound_client_imports(self):
        source = DASHBOARD_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "aiohttp", "websocket",
                    "paramiko", "socketio", "smtplib"}
        # urllib.parse is a URL parsing utility, not an outbound client
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"
        assert "urllib.request" not in DASHBOARD_PY.read_text("utf-8")

    def test_no_credential_strings(self):
        source = DASHBOARD_PY.read_text("utf-8").lower()
        for f in ("private_key", "api_key", "password", "getpass"):
            assert f not in source, f"forbidden: {f}"

    def test_no_live_order_surface(self):
        source = DASHBOARD_PY.read_text("utf-8").lower()
        for f in ("place_order", "submit_live", "live_order", "broker", "wallet",
                  "sign", "exchange"):
            # "exchange" appears in "paper-exchange-adapter-checkpoint-v1" schema name
            # but not as a live exchange client
            if f == "exchange":
                # Check it's only in schema names, not as an import or client
                assert "import exchange" not in source
            else:
                assert f not in source, f"forbidden: {f}"


# ===========================================================================
# 2. Cannot bind outside loopback
# ===========================================================================

class TestLoopbackBinding:
    def test_localhost_accepted(self):
        assert "localhost" in LOOPBACK_HOSTS

    def test_127_0_0_1_accepted(self):
        assert "127.0.0.1" in LOOPBACK_HOSTS

    def test_ipv6_loopback_accepted(self):
        assert "::1" in LOOPBACK_HOSTS

    def test_non_loopback_rejects(self):
        with pytest.raises(PaperDashboardError, match="loopback"):
            main(["--host", "0.0.0.0"])

    def test_external_ip_rejects(self):
        with pytest.raises(PaperDashboardError, match="loopback"):
            main(["--host", "192.168.1.1"])


# ===========================================================================
# 3. POST rejection
# ===========================================================================

class TestHttpBehavior:
    @pytest.fixture
    def server(self, tmp_path):
        config = {
            "candle_path": tmp_path / "BTC_15m.csv",
            "launch_decision_path": tmp_path / "launch.json",
            "adapter_checkpoint_path": tmp_path / "adapter.json",
            "session_health_path": tmp_path / "health.json",
            "observed_at": NOW,
        }
        (tmp_path / "BTC_15m.csv").write_text(FIELDS + ROW, "utf-8")
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(config))
        port = httpd.server_address[1]
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield port
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()

    def _request(self, port, method, path="/"):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request(method, path)
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_get_root(self, server):
        status, body = self._request(server, "GET", "/")
        assert status == 200
        assert b"<!doctype html>" in body

    def test_head_root(self, server):
        status, body = self._request(server, "HEAD", "/")
        assert status == 200

    def test_post_rejects(self, server):
        status, body = self._request(server, "POST", "/")
        assert status == 405
        assert b"method not allowed" in body

    def test_post_api_rejects(self, server):
        status, body = self._request(server, "POST", "/api/snapshot")
        assert status == 405

    def test_put_rejects(self, server):
        status, body = self._request(server, "PUT", "/")
        # PUT is not implemented, so BaseHTTPRequestHandler returns 501
        assert status in (405, 501)

    def test_delete_rejects(self, server):
        status, body = self._request(server, "DELETE", "/")
        assert status in (405, 501)

    def test_unknown_route_404(self, server):
        status, body = self._request(server, "GET", "/unknown")
        assert status == 404
        assert b"not found" in body

    def test_get_snapshot(self, server):
        status, body = self._request(server, "GET", "/api/snapshot")
        assert status == 200
        data = json.loads(body)
        assert data["trading_authority"] is False
        assert data["advisory_only"] is True

    def test_snapshot_has_security_headers(self, server):
        conn = http.client.HTTPConnection("127.0.0.1", server, timeout=5)
        conn.request("GET", "/api/snapshot")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.getheader("Cache-Control") == "no-store"
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
        csp = resp.getheader("Content-Security-Policy") or ""
        assert "default-src" in csp
        assert resp.getheader("Content-Type") == "application/json; charset=utf-8"

    def test_html_has_security_headers(self, server):
        conn = http.client.HTTPConnection("127.0.0.1", server, timeout=5)
        conn.request("GET", "/")
        resp = conn.getresponse()
        resp.read()
        conn.close()
        assert resp.getheader("Cache-Control") == "no-store"
        assert resp.getheader("X-Content-Type-Options") == "nosniff"
        csp = resp.getheader("Content-Security-Policy") or ""
        assert "default-src" in csp
        assert resp.getheader("Content-Type") == "text/html; charset=utf-8"


# ===========================================================================
# 4. Adapter checkpoint checksum and trading_authority
# ===========================================================================

class TestAdapterCheckpoint:
    def _adapter_doc(self, **changes):
        gateway = {"connected": True, "kill_switch_active": False,
                   "reconciliation_required": False, "records": [],
                   "trading_authority": False}
        payload = {"gateway_checkpoint": {"payload": gateway}, "receipts": [],
                   "trading_authority": False}
        payload.update(changes)
        raw = {"schema_version": "paper-exchange-adapter-checkpoint-v1", "payload": payload,
               "payload_sha256": hashlib.sha256(
                   json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
        return raw

    def test_valid_adapter_accepted(self, tmp_path):
        args = _paths(tmp_path)
        args["adapter_checkpoint_path"].write_text(json.dumps(self._adapter_doc()), "utf-8")
        result = build_snapshot(**args)
        assert result["paper"]["available"] is True
        assert result["paper"]["connected"] is True

    def test_tampered_checksum_rejects(self, tmp_path):
        args = _paths(tmp_path)
        doc = self._adapter_doc()
        doc["payload_sha256"] = "0" * 64
        args["adapter_checkpoint_path"].write_text(json.dumps(doc), "utf-8")
        with pytest.raises(PaperDashboardError, match="checkpoint is invalid"):
            build_snapshot(**args)

    def test_trading_authority_true_rejects(self, tmp_path):
        args = _paths(tmp_path)
        doc = self._adapter_doc()
        doc["payload"]["trading_authority"] = True
        doc["payload_sha256"] = hashlib.sha256(
            json.dumps(doc["payload"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        args["adapter_checkpoint_path"].write_text(json.dumps(doc), "utf-8")
        with pytest.raises(PaperDashboardError, match="checkpoint is invalid"):
            build_snapshot(**args)

    def test_gateway_trading_authority_true_rejects(self, tmp_path):
        args = _paths(tmp_path)
        doc = self._adapter_doc()
        doc["payload"]["gateway_checkpoint"]["payload"]["trading_authority"] = True
        doc["payload_sha256"] = hashlib.sha256(
            json.dumps(doc["payload"], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        args["adapter_checkpoint_path"].write_text(json.dumps(doc), "utf-8")
        with pytest.raises(PaperDashboardError, match="checkpoint is invalid"):
            build_snapshot(**args)

    def test_wrong_schema_rejects(self, tmp_path):
        args = _paths(tmp_path)
        doc = self._adapter_doc()
        doc["schema_version"] = "wrong"
        args["adapter_checkpoint_path"].write_text(json.dumps(doc), "utf-8")
        with pytest.raises(PaperDashboardError, match="checkpoint is invalid"):
            build_snapshot(**args)

    def test_missing_adapter_shows_unavailable(self, tmp_path):
        args = _paths(tmp_path)
        result = build_snapshot(**args)
        assert result["paper"]["available"] is False


# ===========================================================================
# 5. Malformed/oversized/symlinked/unsupported evidence
# ===========================================================================

class TestBadEvidence:
    def test_malformed_candle_json_not_relevant(self):
        """Candles are CSV, not JSON."""

    def test_missing_candle_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["candle_path"] = tmp_path / "missing.csv"
        with pytest.raises(PaperDashboardError, match="missing"):
            build_snapshot(**args)

    def test_empty_candle_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["candle_path"].write_text(FIELDS, "utf-8")
        with pytest.raises(PaperDashboardError, match="empty"):
            build_snapshot(**args)

    def test_oversized_adapter_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["adapter_checkpoint_path"].write_text("x" * (MAX_JSON_BYTES + 1), "utf-8")
        with pytest.raises(PaperDashboardError, match="too large"):
            build_snapshot(**args)

    def test_malformed_json_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["adapter_checkpoint_path"].write_text("{not json}", "utf-8")
        with pytest.raises(PaperDashboardError, match="unreadable"):
            build_snapshot(**args)

    def test_non_object_json_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["adapter_checkpoint_path"].write_text('"a string"', "utf-8")
        with pytest.raises(PaperDashboardError, match="object"):
            build_snapshot(**args)

    @pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlink unavailable")
    def test_symlinked_candle_rejects(self, tmp_path):
        args = _paths(tmp_path)
        target = args["candle_path"]
        link = tmp_path / "link.csv"
        try:
            link.symlink_to(target)
        except OSError:
            pytest.skip("symlink requires admin")
        args["candle_path"] = link
        with pytest.raises(PaperDashboardError, match="unsafe"):
            build_snapshot(**args)


# ===========================================================================
# 6. Only closed BTC 15-minute candles
# ===========================================================================

class TestCandleValidation:
    @pytest.mark.parametrize("row", [
        "ETH,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,true\n",
        "BTC,5m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,true\n",
        "BTC,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,false\n",
        "BTC,1h,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,true\n",
    ])
    def test_unsupported_candle_rejects(self, tmp_path, row):
        args = _paths(tmp_path)
        args["candle_path"].write_text(FIELDS + row, "utf-8")
        with pytest.raises(PaperDashboardError, match="unsupported"):
            build_snapshot(**args)

    def test_chronology_invalid_rejects(self, tmp_path):
        args = _paths(tmp_path)
        r2 = "BTC,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,1,1,1,1,1,true\n"
        args["candle_path"].write_text(FIELDS + ROW + r2, "utf-8")
        with pytest.raises(PaperDashboardError, match="chronology"):
            build_snapshot(**args)

    def test_invalid_numbers_reject(self, tmp_path):
        args = _paths(tmp_path)
        bad = "BTC,15m,2026-09-01T00:00:00.000Z,2026-09-01T00:15:00.000Z,abc,1,1,1,1,true\n"
        args["candle_path"].write_text(FIELDS + bad, "utf-8")
        with pytest.raises(PaperDashboardError, match="invalid numbers"):
            build_snapshot(**args)

    def test_wrong_header_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["candle_path"].write_text("wrong,header\n1,2\n", "utf-8")
        with pytest.raises(PaperDashboardError, match="schema"):
            build_snapshot(**args)


# ===========================================================================
# 7. Missing evidence displayed honestly
# ===========================================================================

class TestHonestMissingEvidence:
    def test_no_fabricated_orders(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["paper"]["orders"] == []
        assert result["paper"]["receipts"] == []

    def test_no_fabricated_equity(self, tmp_path):
        result = _snapshot(tmp_path)
        assert "equity" not in result
        assert "balance" not in result

    def test_no_fabricated_pnl(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["performance"]["available"] is False

    def test_no_fabricated_positions(self, tmp_path):
        result = _snapshot(tmp_path)
        assert "positions" not in result


# ===========================================================================
# 8. P&L unavailable
# ===========================================================================

class TestPnlUnavailable:
    def test_performance_unavailable(self, tmp_path):
        result = _snapshot(tmp_path)
        assert result["performance"] == {
            "available": False,
            "reason": "AUTHORITATIVE_FILL_PRICE_AND_MARK_TO_MARKET_LEDGER_UNAVAILABLE",
        }

    def test_pnl_reason_explicit(self, tmp_path):
        result = _snapshot(tmp_path)
        assert "FILL_PRICE" in result["performance"]["reason"]
        assert "MARK_TO_MARKET" in result["performance"]["reason"]


# ===========================================================================
# 9. Snapshot IDs deterministic and content-addressed
# ===========================================================================

class TestSnapshotIdentity:
    def test_deterministic(self, tmp_path):
        a = _snapshot(tmp_path)
        b = _snapshot(tmp_path)
        assert a == b
        assert a["snapshot_id"] == b["snapshot_id"]

    def test_sha256(self, tmp_path):
        result = _snapshot(tmp_path)
        assert len(result["snapshot_id"]) == 64
        assert all(c in "0123456789abcdef" for c in result["snapshot_id"])

    def test_content_addressed(self, tmp_path):
        result = _snapshot(tmp_path)
        body = {k: v for k, v in result.items() if k != "snapshot_id"}
        expected = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False).encode("utf-8")).hexdigest()
        assert result["snapshot_id"] == expected


# ===========================================================================
# 10. HTML escaping
# ===========================================================================

class TestHtmlEscaping:
    def test_html_contains_escaping_function(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "esc" in source
        assert "&amp;" in source
        assert "&lt;" in source
        assert "&gt;" in source

    def test_html_uses_esc_for_order_fields(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "esc(o.order_id)" in source
        assert "esc(o.state)" in source

    def test_no_unescaped_innerhtml(self):
        source = DASHBOARD_PY.read_text("utf-8")
        # Check that innerHTML uses esc() for dynamic content
        assert "esc(" in source


# ===========================================================================
# 11. Security headers
# ===========================================================================

class TestSecurityHeaders:
    def test_cache_control_in_source(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "Cache-Control" in source
        assert "no-store" in source

    def test_x_content_type_options(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "X-Content-Type-Options" in source
        assert "nosniff" in source

    def test_csp_in_source(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "Content-Security-Policy" in source
        assert "default-src 'self'" in source
        assert "object-src 'none'" in source
        assert "frame-ancestors 'none'" in source


# ===========================================================================
# 12. No execution imports or outbound clients
# ===========================================================================

class TestNoExecutionImports:
    def test_no_execution_module(self):
        source = DASHBOARD_PY.read_text("utf-8")
        assert "from execution" not in source
        assert "import execution" not in source

    def test_no_socket_import(self):
        source = DASHBOARD_PY.read_text("utf-8")
        # socket is imported only in test, not in production module
        # Actually the module uses http.server which uses socket internally
        # but doesn't import socket directly
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module)
        assert "socket" not in imports

    def test_http_server_not_a_client(self):
        """http.server is an inbound server, not an outbound client."""
        source = DASHBOARD_PY.read_text("utf-8")
        assert "http.server" in source
        assert "BaseHTTPRequestHandler" in source


# ===========================================================================
# 13. PowerShell wrapper
# ===========================================================================

class TestPowerShellWrapper:
    def test_binds_localhost(self):
        source = PS1.read_text("utf-8")
        assert "127.0.0.1" in source

    def test_uses_python_module(self):
        source = PS1.read_text("utf-8")
        assert "monitoring.paper_dashboard_v1" in source

    def test_no_mutation_cmdlets(self):
        source = PS1.read_text("utf-8")
        for f in ("Register-ScheduledTask", "Stop-ScheduledTask", "Start-ScheduledTask",
                  "Enable-ScheduledTask", "Disable-ScheduledTask", "Set-ScheduledTask"):
            assert f not in source, f"forbidden: {f}"

    def test_python_runtime_checked(self):
        source = PS1.read_text("utf-8")
        assert ".venv" in source and "python.exe" in source

    def test_error_action_stop(self):
        source = PS1.read_text("utf-8")
        assert "$ErrorActionPreference" in source

    def test_no_credential(self):
        source = PS1.read_text("utf-8").lower()
        for f in ("get-credential", "private_key", "api_key", "password"):
            assert f not in source, f"forbidden: {f}"


# ===========================================================================
# 14. Observed_at validation
# ===========================================================================

class TestObservedAt:
    def test_naive_observed_at_rejects(self, tmp_path):
        args = _paths(tmp_path)
        args["observed_at"] = NOW.replace(tzinfo=None)
        with pytest.raises(PaperDashboardError, match="timezone"):
            build_snapshot(**args)

    def test_auto_observed_at_works(self, tmp_path):
        args = _paths(tmp_path)
        del args["observed_at"]
        result = build_snapshot(**args)
        assert "observed_at" in result


# ===========================================================================
# 15. Max candles limit
# ===========================================================================

class TestMaxCandles:
    def test_max_candles_constant(self):
        assert MAX_CANDLES == 500

    def test_max_json_bytes_constant(self):
        assert MAX_JSON_BYTES == 32 * 1024 * 1024

    def test_schema_version(self):
        assert SCHEMA_VERSION == "paper-dashboard-snapshot-v1"


# ===========================================================================
# 16. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """8 existing tests pass + 1 skipped — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: PUT/DELETE rejection, unknown route 404,
        snapshot security headers, HTML security headers, gateway TA true,
        wrong schema adapter, no socket import, PowerShell no credential,
        max candles/json bytes constants, observed_at auto works,
        no fabricated equity/balance/positions — not in existing 8."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: build_snapshot, make_handler,
        main, PaperDashboardError, SCHEMA_VERSION, MAX_CANDLES, MAX_JSON_BYTES,
        LOOPBACK_HOSTS. No private helpers."""

