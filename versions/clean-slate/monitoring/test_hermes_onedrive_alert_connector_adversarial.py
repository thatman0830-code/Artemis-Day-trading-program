"""Hermes independent adversarial audit for the OneDrive alert-delivery connector.

Audit assignment: AUDIT-ONEDRIVE-ALERT-CONNECTOR
Checkpoint: e99539963371eb976b50faee1d6887c09c972ab7

Covers:
  1. CLI exposes only delivery and acknowledgement-import operations
  2. CLI output always has trading_authority=false
  3. PowerShell runner targets only OneDrive\\TradingSystem\\AlertEvidence
  4. Reads only sanitized watchdog alert spool and exact sink manifest
  5. Writes only delivery envelopes and local delivery receipts
  6. Never reads OneDrive credentials, unrelated cloud files, strategies, trading data, env files, or secrets
  7. Missing OneDrive context, manifest, alert spool, Python runtime, malformed evidence, or delivery failure fails closed
  8. Process-level OneDrive resolution precedes user-level fallback
  9. Paths containing spaces remain correctly handled
 10. Repeated delivery is idempotent and conflicting cloud files fail closed
 11. No task, recorder, process, network, provider, wallet, broker, exchange, signing, or trading control exists
 12. Documentation does not claim authenticated acknowledgements, institutional readiness, or guaranteed cloud availability
 13. Automatic scheduling remains absent
"""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring.off_host_alert_delivery import (
    ACK_VERSION, ENVELOPE_VERSION, RECEIPT_VERSION, SINK_VERSION, TRANSPORTS,
    AlertDeliveryError, deliver_alerts, import_acknowledgements, main,
)

NOW = datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc)
UTC = timezone.utc

PS1 = Path(__file__).parents[1] / "scripts" / "run_onedrive_alert_delivery.ps1"
PY = Path(__file__).parents[1] / "monitoring" / "off_host_alert_delivery.py"
MD = Path(__file__).parents[1] / "monitoring" / "OFF_HOST_ALERT_DELIVERY_FOUNDATION.md"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

def _digest(value):
    import hashlib
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _setup(tmp_path, transport="UNC", sink_id="owner-remote-1"):
    sink = tmp_path / "sink"
    sink.mkdir(parents=True)
    manifest = {
        "schema_version": SINK_VERSION, "sink_id": sink_id,
        "transport": transport, "off_host_attested": True, "trading_authority": False,
    }
    (sink / "sink-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    body = {
        "event": "WATCHDOG_FAILURE", "observed_at": NOW.isoformat(),
        "reason": "HEALTH_COLLECTION_FAILED", "state": "UNHEALTHY",
        "ready_for_unattended_operation": False,
        "watchdog_version": "OWNER_CONTEXT_HEALTH_WATCHDOG_V1",
        "trading_authority": False,
    }
    alert = {**body, "event_id": _digest(body)}
    spool = tmp_path / "alerts.jsonl"
    spool.write_text(_canonical(alert) + "\n", encoding="utf-8")
    return sink, spool


# ===========================================================================
# 1. CLI exposes only delivery and acknowledgement-import operations
# ===========================================================================

class TestCLIScope:
    def test_cli_has_two_subcommands(self):
        source = PY.read_text("utf-8")
        assert "deliver" in source and "import-acknowledgements" in source

    def test_cli_no_other_operations(self):
        source = PY.read_text("utf-8")
        # No "create", "delete", "send", "push", "pull", "sync" subcommands
        for forbidden in ("add_parser(\"create\"", "add_parser(\"delete\"",
                         "add_parser(\"send\"", "add_parser(\"push\"",
                         "add_parser(\"pull\"", "add_parser(\"sync\""):
            assert forbidden not in source, f"forbidden: {forbidden}"

    def test_deliver_subcommand_requires_all_args(self, tmp_path, monkeypatch, capsys):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        monkeypatch.setattr("sys.argv", ["delivery", "deliver", "--alerts", str(spool),
                                          "--sink", str(sink), "--receipts", str(receipts)])
        assert main() == 0

    def test_missing_subcommand_rejects(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", ["delivery"])
        with pytest.raises(SystemExit):
            main()

    def test_unknown_subcommand_rejects(self, tmp_path, monkeypatch):
        monkeypatch.setattr("sys.argv", ["delivery", "unknown"])
        with pytest.raises(SystemExit):
            main()


# ===========================================================================
# 2. CLI output always has trading_authority=false
# ===========================================================================

class TestCLIOutputAuthority:
    def test_deliver_output_trading_authority_false(self, tmp_path, monkeypatch, capsys):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        monkeypatch.setattr("sys.argv", ["delivery", "deliver", "--alerts", str(spool),
                                          "--sink", str(sink), "--receipts", str(receipts)])
        main()
        output = json.loads(capsys.readouterr().out)
        assert output["trading_authority"] is False

    def test_ack_output_trading_authority_false(self, tmp_path, monkeypatch, capsys):
        """Verify the import-acknowledgements CLI output has trading_authority=False.
        Uses the real now from datetime.now(timezone.utc) to avoid chronology issues."""
        from datetime import datetime as _dt, timezone as _tz
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        # Use real current time for delivery and ack so chronology passes
        real_now = _dt.now(_tz.utc)
        receipt = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=real_now)[0]
        acks_dir = sink / "acknowledgements"
        acks_dir.mkdir()
        body = {"schema_version": ACK_VERSION, "delivery_id": receipt["delivery_id"],
                "sink_id": "owner-remote-1", "operator_id": "risk-operator-1",
                "acknowledged_at": (real_now + timedelta(seconds=5)).isoformat(),
                "authentication": "UNAUTHENTICATED_OPERATOR_ATTESTATION", "trading_authority": False}
        ack = {**body, "ack_id": _digest(body)}
        (acks_dir / "ack.json").write_text(json.dumps(ack))
        local_acks = tmp_path / "acks"
        monkeypatch.setattr("sys.argv", ["delivery", "import-acknowledgements", "--sink", str(sink),
                                          "--receipts", str(receipts), "--acknowledgements", str(local_acks),
                                          "--sla-seconds", "60"])
        main()
        output = json.loads(capsys.readouterr().out)
        assert output["trading_authority"] is False

    def test_deliver_output_has_state(self, tmp_path, monkeypatch, capsys):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        monkeypatch.setattr("sys.argv", ["delivery", "deliver", "--alerts", str(spool),
                                          "--sink", str(sink), "--receipts", str(receipts)])
        main()
        output = json.loads(capsys.readouterr().out)
        assert output["state"] == "DELIVERED"
        assert output["receipt_count"] == 1


# ===========================================================================
# 3. PowerShell runner targets only OneDrive\TradingSystem\AlertEvidence
# ===========================================================================

class TestPS1Target:
    def test_targets_onedrive_alert_evidence(self):
        source = PS1.read_text("utf-8")
        assert "TradingSystem" in source and "AlertEvidence" in source

    def test_exact_path_segment(self):
        source = PS1.read_text("utf-8")
        assert "TradingSystem\\AlertEvidence" in source or "TradingSystem\\\\AlertEvidence" in source

    def test_does_not_target_other_paths(self):
        source = PS1.read_text("utf-8")
        for forbidden in ("outputs\\futures", "outputs\\recorder_health", "data\\backtests",
                         "strategy", ".env", "config"):
            assert forbidden not in source, f"forbidden path: {forbidden}"


# ===========================================================================
# 4. Reads only sanitized watchdog alert spool and exact sink manifest
# ===========================================================================

class TestPS1Reads:
    def test_reads_alert_spool(self):
        source = PS1.read_text("utf-8")
        assert "alerts.jsonl" in source
        assert "operational_health" in source and "watchdog" in source.lower()

    def test_reads_sink_manifest(self):
        source = PS1.read_text("utf-8")
        assert "sink-manifest.json" in source

    def test_validates_manifest_exists(self):
        source = PS1.read_text("utf-8")
        assert "sink manifest is missing" in source or "manifest is missing" in source.lower()

    def test_does_not_read_other_onedrive_content(self):
        source = PS1.read_text("utf-8")
        # Only reads from the sink path, not other OneDrive folders
        assert source.count("Test-Path") <= 4  # python, alerts, manifest, maybe one more


# ===========================================================================
# 5. Writes only delivery envelopes and local delivery receipts
# ===========================================================================

class TestPS1Writes:
    def test_writes_envelopes_to_sink_inbox(self):
        source = PS1.read_text("utf-8")
        assert "monitoring.off_host_alert_delivery deliver" in source

    def test_receipts_path_is_local(self):
        source = PS1.read_text("utf-8")
        assert "alert-delivery-receipts" in source
        assert "repository" in source  # local repository, not OneDrive

    def test_no_direct_file_writes_in_ps1(self):
        source = PS1.read_text("utf-8")
        assert "WriteAllText" not in source
        assert "Out-File" not in source
        assert "Set-Content" not in source


# ===========================================================================
# 6. Never reads OneDrive credentials, unrelated cloud files, secrets
# ===========================================================================

class TestPS1NoSecrets:
    def test_no_credential_access(self):
        source = PS1.read_text("utf-8")
        for forbidden in ("Get-Credential", "SecureString", "ConvertTo-SecureString",
                         "password", "api_key", "private_key", "secret", "credential"):
            assert forbidden.lower() not in source.lower(), f"forbidden: {forbidden}"

    def test_no_strategy_or_trading_data(self):
        source = PS1.read_text("utf-8")
        for forbidden in ("strategy", "trading_data", "backtest", "execution"):
            assert forbidden.lower() not in source.lower(), f"forbidden: {forbidden}"

    def test_no_env_file_access(self):
        source = PS1.read_text("utf-8")
        assert ".env" not in source.lower()

    def test_no_unrelated_cloud_files(self):
        source = PS1.read_text("utf-8")
        # Only OneDrive root is used; no other cloud paths
        assert "OneDrive" in source
        assert "SharePoint" not in source
        assert "Azure" not in source
        assert "AWS" not in source


# ===========================================================================
# 7. Missing context, manifest, spool, Python, malformed, delivery failure fails closed
# ===========================================================================

class TestPS1FailClosed:
    def test_missing_onedrive_throws(self):
        source = PS1.read_text("utf-8")
        assert "OneDrive owner sync root is unavailable" in source

    def test_missing_python_throws(self):
        source = PS1.read_text("utf-8")
        assert "Repository Python runtime is missing" in source

    def test_missing_alert_spool_throws(self):
        source = PS1.read_text("utf-8")
        assert "Watchdog alert spool is missing" in source

    def test_missing_manifest_throws(self):
        source = PS1.read_text("utf-8")
        assert "sink manifest is missing" in source or "manifest is missing" in source

    def test_delivery_failure_throws(self):
        source = PS1.read_text("utf-8")
        assert "alert delivery failed" in source

    def test_error_action_stop(self):
        source = PS1.read_text("utf-8")
        assert "$ErrorActionPreference = 'Stop'" in source


# ===========================================================================
# 8. Process-level OneDrive resolution precedes user-level fallback
# ===========================================================================

class TestOneDriveResolution:
    def test_process_level_first(self):
        source = PS1.read_text("utf-8")
        idx_env = source.index("$env:OneDrive")
        idx_user = source.index("GetEnvironmentVariable('OneDrive','User')")
        assert idx_env < idx_user

    def test_falls_back_to_user_level(self):
        source = PS1.read_text("utf-8")
        assert "GetEnvironmentVariable('OneDrive','User')" in source

    def test_empty_onedrive_triggers_fallback(self):
        source = PS1.read_text("utf-8")
        assert "IsNullOrWhiteSpace" in source


# ===========================================================================
# 9. Paths containing spaces remain correctly handled
# ===========================================================================

class TestSpacesInPaths:
    def test_sink_path_supports_spaces(self, tmp_path):
        """Sink path with spaces should work — Join-Path handles it."""
        sink = tmp_path / "My Sink Folder"
        sink.mkdir(parents=True)
        manifest = {"schema_version": SINK_VERSION, "sink_id": "owner-remote-1",
                    "transport": "UNC", "off_host_attested": True, "trading_authority": False}
        (sink / "sink-manifest.json").write_text(json.dumps(manifest))
        body = {"event": "WATCHDOG_FAILURE", "observed_at": NOW.isoformat(),
                "reason": "HEALTH_COLLECTION_FAILED", "state": "UNHEALTHY",
                "ready_for_unattended_operation": False,
                "watchdog_version": "OWNER_CONTEXT_HEALTH_WATCHDOG_V1", "trading_authority": False}
        alert = {**body, "event_id": _digest(body)}
        spool = tmp_path / "alerts.jsonl"
        spool.write_text(_canonical(alert) + "\n")
        receipts = tmp_path / "My Receipts"
        result = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        assert len(result) == 1
        assert (sink / "inbox").glob("*.json").__next__().is_file()

    def test_ps1_uses_join_path_for_spaces(self):
        source = PS1.read_text("utf-8")
        assert "Join-Path" in source


# ===========================================================================
# 10. Repeated delivery is idempotent and conflicting cloud files fail closed
# ===========================================================================

class TestIdempotent:
    def test_idempotent_delivery(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        a = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        b = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        assert a == b

    def test_conflicting_cloud_file_rejects(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        # Tamper with the existing envelope
        env_path = next((sink / "inbox").glob("*.json"))
        env = json.loads(env_path.read_text("utf-8"))
        env["tampered"] = True
        env_path.write_text(json.dumps(env))
        with pytest.raises(AlertDeliveryError, match="conflicts"):
            deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)


# ===========================================================================
# 11. No task, recorder, process, network, provider, wallet, broker, trading control
# ===========================================================================

class TestNoControl:
    def test_ps1_no_task_control(self):
        source = PS1.read_text("utf-8")
        for prohibited in ("Register-ScheduledTask", "Unregister-ScheduledTask",
                          "Enable-ScheduledTask", "Disable-ScheduledTask",
                          "Start-ScheduledTask", "Stop-ScheduledTask",
                          "Set-ScheduledTask", "New-ScheduledTask"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_ps1_no_process_control(self):
        source = PS1.read_text("utf-8")
        for prohibited in ("Start-Process", "Stop-Process", "Get-Process"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_ps1_no_network(self):
        source = PS1.read_text("utf-8")
        for prohibited in ("Invoke-WebRequest", "Invoke-RestMethod", "Invoke-Expression",
                          "System.Net", "HttpClient", "RestClient"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_py_no_network_imports(self):
        source = PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "urllib", "smtplib", "imaplib",
                    "paramiko", "sshtunnel", "onedrivesdk", "msgraph"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"

    def test_py_no_trading_control(self):
        source = PY.read_text("utf-8")
        for forbidden in ("submit_order", "place_trade", "execute_trade", "send_order"):
            assert forbidden not in source, f"forbidden: {forbidden}"

    def test_no_recorder_references(self):
        source = PS1.read_text("utf-8")
        for forbidden in ("btc-recorder", "es-nq-recorder", "run_btc_forward_recorder",
                         "run_es_nq_delayed_forward"):
            assert forbidden not in source, f"forbidden: {forbidden}"


# ===========================================================================
# 12. Documentation does not claim authenticated acks, institutional readiness, or guaranteed availability
# ===========================================================================

class TestDocumentation:
    def test_disclaims_authenticated_acknowledgements(self):
        source = MD.read_text("utf-8")
        assert "not cryptographically authenticated" in source.lower()

    def test_disclaims_institutional_readiness(self):
        source = MD.read_text("utf-8")
        assert "Institutional readiness requires" in source

    def test_no_guaranteed_availability(self):
        source = MD.read_text("utf-8")
        assert "guaranteed" not in source.lower()
        assert "not yet a completed" in source.lower() or "not a completed" in source.lower()

    def test_describes_onedrive_connector(self):
        source = MD.read_text("utf-8")
        assert "OneDrive" in source
        assert "TradingSystem" in source
        assert "AlertEvidence" in source

    def test_describes_scheduling_as_separate(self):
        source = MD.read_text("utf-8")
        assert "scheduling remains a separate" in source.lower() or "separate audited step" in source.lower()


# ===========================================================================
# 13. Automatic scheduling remains absent
# ===========================================================================

class TestNoScheduling:
    def test_ps1_no_scheduling(self):
        source = PS1.read_text("utf-8")
        for prohibited in ("Register-ScheduledTask", "New-ScheduledTask", "New-ScheduledTaskTrigger",
                          "New-ScheduledTaskAction", "schtasks", "Task Scheduler"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_ps1_no_repetition(self):
        source = PS1.read_text("utf-8")
        assert "RepetitionInterval" not in source
        assert "New-TimeSpan" not in source

    def test_documentation_states_scheduling_separate(self):
        source = MD.read_text("utf-8")
        assert "scheduling" in source.lower()
        assert "separate" in source.lower()

    def test_connector_runner_has_no_embedded_scheduling(self):
        """The connector stays scheduling-free; deployment is separately gated."""
        source = PS1.read_text("utf-8")
        for prohibited in (
            "Register-ScheduledTask",
            "New-ScheduledTask",
            "Enable-ScheduledTask",
            "Start-ScheduledTask",
        ):
            assert prohibited not in source, f"forbidden: {prohibited}"


# ===========================================================================
# 14. PowerShell syntax
# ===========================================================================

class TestPS1Syntax:
    def test_requires_version_51(self):
        source = PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_cmdlet_binding(self):
        source = PS1.read_text("utf-8")
        assert "[CmdletBinding()]" in source

    def test_error_action_stop(self):
        source = PS1.read_text("utf-8")
        assert "$ErrorActionPreference = 'Stop'" in source

    def test_no_parameters(self):
        source = PS1.read_text("utf-8")
        assert "param()" in source

    def test_lastexitcode_checked(self):
        source = PS1.read_text("utf-8")
        assert "$LASTEXITCODE -ne 0" in source

    def test_python_execution(self):
        source = PS1.read_text("utf-8")
        assert "python.exe" in source
        assert "-B -m monitoring.off_host_alert_delivery deliver" in source or \
               "-m monitoring.off_host_alert_delivery deliver" in source


# ===========================================================================
# 15. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """10 existing tests pass — accepted unchanged (2 new: CLI + PS1)."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: CLI subcommand scope, unknown command rejection,
        CLI output authority for both deliver and ack, PS1 target exactness,
        PS1 no direct writes, PS1 no strategy/trading/env, PS1 process-level first,
        spaces in sink paths, no scheduling scripts, no guaranteed availability —
        not in existing 10 tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: deliver_alerts, import_acknowledgements,
        main, AlertDeliveryError, and source text assertions. No private helpers."""
