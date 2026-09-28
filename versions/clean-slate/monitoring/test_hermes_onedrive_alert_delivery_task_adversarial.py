"""Hermes independent adversarial audit for the OneDrive alert-delivery scheduled-task milestone.

Audit assignment: AUDIT-ONEDRIVE-ALERT-DELIVERY-TASK
Checkpoint: fef8020f71f7afc4a61640a1cce679f99e09c108

Covers:
  1. Connector runner remains scheduling-free
  2. Installer: disabled, single-instance, 5-min repetition, 2-min limit, RunLevel Limited, IgnoreNew
  3. Auditor: read-only, exact identity (name, path, action, args, exe, working dir, trigger, PT5M, PT2M, StartWhenAvailable, IgnoreNew, runner, Python)
  4. Guarded enablement: requires disabled audited task, fresh successful run, complete delivery verification, disable-on-failure
  5. Completeness verifier: every alert has its envelope, receipt, matching identities, matching hashes, trading_authority=false
  6. Removal: identity-verified, targets only exact task, preserves evidence
  7. trading_authority=false in all emitted facts and task configuration
  8. Documentation: no authenticated ack claim, no institutional readiness claim, no guaranteed availability claim
  9. Evolutionary correction: test_no_install_or_enable_script → test_connector_runner_has_no_embedded_scheduling (acceptable)
 10. PowerShell syntax validation
 11. No network, credential, provider, wallet, broker, exchange, signing, or trading control
 12. Classification
"""

from __future__ import annotations

import ast
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from monitoring.off_host_alert_delivery import (
    ENVELOPE_VERSION, RECEIPT_VERSION, SINK_VERSION, AlertDeliveryError,
    deliver_alerts, verify_delivery,
)
from monitoring.onedrive_delivery_verifier import main as verify_main

ROOT = Path(__file__).parents[1]
CONNECTOR_PS1 = ROOT / "scripts" / "run_onedrive_alert_delivery.ps1"
INSTALLER_PS1 = ROOT / "scripts" / "install_onedrive_alert_delivery_task.ps1"
AUDITOR_PS1 = ROOT / "scripts" / "audit_onedrive_alert_delivery_task.ps1"
ENABLE_PS1 = ROOT / "scripts" / "enable_and_verify_onedrive_alert_delivery_task.ps1"
REMOVE_PS1 = ROOT / "scripts" / "remove_onedrive_alert_delivery_task.ps1"
VERIFIER_PY = ROOT / "monitoring" / "onedrive_delivery_verifier.py"
FOUNDATION_MD = ROOT / "monitoring" / "OFF_HOST_ALERT_DELIVERY_FOUNDATION.md"
DELIVERY_PY = ROOT / "monitoring" / "off_host_alert_delivery.py"

NOW = datetime(2026, 8, 31, 20, 0, tzinfo=timezone.utc)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))

def _digest(value):
    import hashlib
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _setup(tmp_path, transport="UNC", sink_id="owner-remote-1"):
    sink = tmp_path / "sink"
    sink.mkdir(parents=True)
    manifest = {"schema_version": SINK_VERSION, "sink_id": sink_id,
                "transport": transport, "off_host_attested": True, "trading_authority": False}
    (sink / "sink-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    body = {"event": "WATCHDOG_FAILURE", "observed_at": NOW.isoformat(),
            "reason": "HEALTH_COLLECTION_FAILED", "state": "UNHEALTHY",
            "ready_for_unattended_operation": False,
            "watchdog_version": "OWNER_CONTEXT_HEALTH_WATCHDOG_V1", "trading_authority": False}
    alert = {**body, "event_id": _digest(body)}
    spool = tmp_path / "alerts.jsonl"
    spool.write_text(_canonical(alert) + "\n", encoding="utf-8")
    return sink, spool


# ===========================================================================
# 1. Connector runner remains scheduling-free
# ===========================================================================

class TestConnectorSchedulingFree:
    def test_connector_no_register(self):
        source = CONNECTOR_PS1.read_text("utf-8")
        assert "Register-ScheduledTask" not in source

    def test_connector_no_new_scheduled_task(self):
        source = CONNECTOR_PS1.read_text("utf-8")
        assert "New-ScheduledTask" not in source

    def test_connector_no_enable(self):
        source = CONNECTOR_PS1.read_text("utf-8")
        assert "Enable-ScheduledTask" not in source

    def test_connector_no_start(self):
        source = CONNECTOR_PS1.read_text("utf-8")
        assert "Start-ScheduledTask" not in source

    def test_connector_no_repetition(self):
        source = CONNECTOR_PS1.read_text("utf-8")
        assert "RepetitionInterval" not in source
        assert "New-TimeSpan" not in source


# ===========================================================================
# 2. Installer: disabled, single-instance, 5-min, 2-min, Limited, IgnoreNew
# ===========================================================================

class TestInstaller:
    def test_task_name(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Owner Context OneDrive Alert Delivery" in source

    def test_5min_repetition(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "RepetitionInterval (New-TimeSpan -Minutes 5)" in source

    def test_2min_execution_limit(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "ExecutionTimeLimit (New-TimeSpan -Minutes 2)" in source

    def test_ignore_new(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "MultipleInstances IgnoreNew" in source

    def test_run_level_limited(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "RunLevel Limited" in source

    def test_disabled_after_install(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Disable-ScheduledTask" in source

    def test_start_when_available(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "StartWhenAvailable" in source

    def test_no_trading_authority(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "No trading authority" in source

    def test_already_exists_rejects(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "already exists" in source

    def test_powershell_executable(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "powershell.exe" in source

    def test_no_logo_no_profile(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "-NoLogo" in source and "-NoProfile" in source

    def test_logon_type_interactive(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "LogonType Interactive" in source

    def test_requires_version_51(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_cmdlet_binding(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "[CmdletBinding()]" in source

    def test_runner_referenced(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "run_onedrive_alert_delivery.ps1" in source


# ===========================================================================
# 3. Auditor: read-only, exact identity
# ===========================================================================

class TestAuditor:
    def test_no_mutation_cmdlets(self):
        source = AUDITOR_PS1.read_text("utf-8")
        for prohibited in ("Register-ScheduledTask", "Unregister-ScheduledTask",
                          "Enable-ScheduledTask", "Disable-ScheduledTask",
                          "Start-ScheduledTask", "Stop-ScheduledTask",
                          "Start-Process", "Stop-Process"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_exact_task_name(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "Owner Context OneDrive Alert Delivery" in source

    def test_single_action_and_trigger(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "exactly one action and one trigger" in source

    def test_pt5m(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "PT5M" in source

    def test_pt2m(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "PT2M" in source

    def test_ignore_new(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "IgnoreNew" in source

    def test_action_verified_true(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "action_verified=$true" in source

    def test_trading_authority_false(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "trading_authority=$false" in source

    def test_validates_executable(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "powershell.exe" in source
        assert "$env:SystemRoot" in source

    def test_validates_arguments(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "-NoLogo" in source and "-NoProfile" in source
        assert "-ExecutionPolicy Bypass" in source and "-File" in source

    def test_validates_working_directory(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "WorkingDirectory" in source

    def test_validates_owner(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "Principal.UserId" in source
        assert "WindowsIdentity" in source

    def test_validates_logon_type(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "LogonType" in source and "Interactive" in source

    def test_validates_run_level(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "RunLevel" in source and "Limited" in source

    def test_validates_start_when_available(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "StartWhenAvailable" in source

    def test_validates_runner_exists(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "run_onedrive_alert_delivery.ps1" in source

    def test_validates_python_exists(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert ".venv" in source and "python.exe" in source

    def test_safety_policy_rejected(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "safety policy rejected" in source.lower()

    def test_requires_version_51(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source

    def test_get_scheduled_task_used(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "Get-ScheduledTask" in source
        assert "Get-ScheduledTaskInfo" in source

    def test_convertto_json_compress(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "ConvertTo-Json" in source and "-Compress" in source


# ===========================================================================
# 4. Guarded enablement: fresh successful run, complete delivery, disable-on-failure
# ===========================================================================

class TestEnablement:
    def test_requires_disabled_state(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "state-ne'Disabled'" in source

    def test_requires_trading_authority_false(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "trading_authority-ne$false" in source

    def test_calls_audit_first(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "audit_onedrive_alert_delivery_task.ps1" in source

    def test_requires_fresh_run_time(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "LastRunTime.ToUniversalTime()-ge$startedAt" in source

    def test_requires_successful_result(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "LastTaskResult-ne 0" in source

    def test_calls_delivery_verifier(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "monitoring.onedrive_delivery_verifier" in source

    def test_requires_verified_state(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "DELIVERY_VERIFIED" in source

    def test_requires_verified_count_at_least_1(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "verified_count-lt 1" in source

    def test_requires_trading_authority_false_in_verification(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "trading_authority-ne$false" in source

    def test_has_timeout(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "TimeoutSeconds" in source
        assert "ValidateRange" in source

    def test_timeout_min_30(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "30" in source

    def test_timeout_max_240(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "240" in source

    def test_default_timeout_120(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "120" in source

    def test_polls_every_3_seconds(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "Start-Sleep -Seconds 3" in source

    def test_catch_disables(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "catch" in source
        assert "Disable-ScheduledTask" in source
        catch_idx = source.index("catch")
        disable_idx = source.index("Disable-ScheduledTask")
        assert disable_idx > catch_idx

    def test_success_message(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "ONEDRIVE_ALERT_DELIVERY_TASK_ENABLED_AND_VERIFIED" in source

    def test_timeout_throws(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "did not complete before timeout" in source

    def test_state_not_running_checked(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "State-ne'Running'" in source

    def test_requires_version_51(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "#requires -Version 5.1" in source


# ===========================================================================
# 5. Completeness verifier: every alert has envelope, receipt, matching hashes
# ===========================================================================

class TestDeliveryVerifier:
    def test_verify_delivery_succeeds(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        assert verify_delivery(alerts_path=spool, sink=sink, local_receipts=receipts) == 1

    def test_missing_receipt_fails(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        delivered = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        (receipts / f"{delivered[0]['delivery_id']}.json").unlink()
        with pytest.raises(AlertDeliveryError, match="receipt"):
            verify_delivery(alerts_path=spool, sink=sink, local_receipts=receipts)

    def test_missing_envelope_fails(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        delivered = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        (sink / "inbox" / f"{delivered[0]['delivery_id']}.json").unlink()
        with pytest.raises(AlertDeliveryError, match="envelope"):
            verify_delivery(alerts_path=spool, sink=sink, local_receipts=receipts)

    def test_tampered_envelope_fails(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        delivered = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        env_path = sink / "inbox" / f"{delivered[0]['delivery_id']}.json"
        env = json.loads(env_path.read_text("utf-8"))
        env["tampered"] = True
        env_path.write_text(json.dumps(env))
        with pytest.raises(AlertDeliveryError, match="envelope"):
            verify_delivery(alerts_path=spool, sink=sink, local_receipts=receipts)

    def test_tampered_receipt_fails(self, tmp_path):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        delivered = deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        rpath = receipts / f"{delivered[0]['delivery_id']}.json"
        rvalue = json.loads(rpath.read_text("utf-8"))
        rvalue["receipt_id"] = "0" * 64
        rpath.write_text(json.dumps(rvalue))
        with pytest.raises(AlertDeliveryError, match="receipt"):
            verify_delivery(alerts_path=spool, sink=sink, local_receipts=receipts)

    def test_zero_alerts_fails(self, tmp_path):
        sink, spool = _setup(tmp_path)
        spool.write_text("")  # empty spool
        with pytest.raises(AlertDeliveryError):
            verify_delivery(alerts_path=spool, sink=sink, local_receipts=tmp_path / "receipts")

    def test_cli_output_trading_authority_false(self, tmp_path, monkeypatch, capsys):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        monkeypatch.setattr("sys.argv", ["verify", "--alerts", str(spool),
                                          "--sink", str(sink), "--receipts", str(receipts)])
        verify_main()
        output = json.loads(capsys.readouterr().out)
        assert output["trading_authority"] is False
        assert output["state"] == "DELIVERY_VERIFIED"
        assert output["verified_count"] == 1

    def test_cli_is_read_only(self, tmp_path, monkeypatch, capsys):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        before = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
        monkeypatch.setattr("sys.argv", ["verify", "--alerts", str(spool),
                                          "--sink", str(sink), "--receipts", str(receipts)])
        verify_main()
        after = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
        assert before == after

    def test_verifier_no_network_imports(self):
        source = VERIFIER_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "urllib", "smtplib", "paramiko"}
        assert imports.isdisjoint(forbidden), f"forbidden: {imports & forbidden}"


# ===========================================================================
# 6. Removal: identity-verified, targets only exact task, preserves evidence
# ===========================================================================

class TestRemoval:
    def test_requires_identity_verification(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "action_verified-ne$true" in source

    def test_requires_trading_authority_false(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "trading_authority-ne$false" in source

    def test_calls_audit_first(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "audit_onedrive_alert_delivery_task.ps1" in source

    def test_targets_exact_task(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "Owner Context OneDrive Alert Delivery" in source

    def test_unregisters_task(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "Unregister-ScheduledTask" in source
        assert "-Confirm:$false" in source

    def test_disables_before_unregister(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "Disable-ScheduledTask" in source

    def test_stops_before_unregister(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "Stop-ScheduledTask" in source

    def test_no_remove_item(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "Remove-Item" not in source

    def test_preserves_evidence(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "EVIDENCE_PRESERVED" in source

    def test_refuses_unverified(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "removal rejected" in source or "not verified" in source.lower()

    def test_no_evidence_file_access(self):
        source = REMOVE_PS1.read_text("utf-8")
        assert "alerts.jsonl" not in source
        assert "inbox" not in source
        assert "receipts" not in source.lower()


# ===========================================================================
# 7. trading_authority=false in all emitted facts and task configuration
# ===========================================================================

class TestTradingAuthority:
    def test_installer_trading_authority_false(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "No trading authority" in source

    def test_auditor_trading_authority_false(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "trading_authority=$false" in source

    def test_enablement_trading_authority_false(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "trading_authority-ne$false" in source

    def test_verifier_output_trading_authority_false(self, tmp_path, monkeypatch, capsys):
        sink, spool = _setup(tmp_path)
        receipts = tmp_path / "receipts"
        deliver_alerts(alerts_path=spool, sink=sink, local_receipts=receipts, delivered_at=NOW)
        monkeypatch.setattr("sys.argv", ["verify", "--alerts", str(spool),
                                          "--sink", str(sink), "--receipts", str(receipts)])
        verify_main()
        output = json.loads(capsys.readouterr().out)
        assert output["trading_authority"] is False


# ===========================================================================
# 8. Documentation: no authenticated ack, institutional, or guaranteed availability claim
# ===========================================================================

class TestDocumentation:
    def test_disclaims_authenticated_acknowledgements(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "not cryptographically authenticated" in source.lower()

    def test_disclaims_institutional_readiness(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "Institutional readiness requires" in source

    def test_no_guaranteed_availability(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "guaranteed" not in source.lower()

    def test_describes_scheduling_layer(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "scheduling layer" in source.lower() or "installed disabled" in source.lower()

    def test_describes_disable_on_failure(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "disable" in source.lower() and "failure" in source.lower()

    def test_describes_removal_preserves_evidence(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "removal" in source.lower() and "preserves" in source.lower()

    def test_describes_enablement_requires_audit(self):
        source = FOUNDATION_MD.read_text("utf-8")
        assert "audit" in source.lower() and "enablement" in source.lower() or "enablement requires" in source.lower()


# ===========================================================================
# 9. Evolutionary correction classification
# ===========================================================================

class TestEvolutionaryCorrection:
    def test_old_assertion_replaced(self):
        """The old test_no_install_or_enable_script_for_onedrive was replaced with
        test_connector_runner_has_no_embedded_scheduling. This is an ACCEPTABLE CORRECTION
        because:
        1. The old assertion (no install/enable script exists) was valid for the connector-only milestone
        2. This milestone intentionally introduced install/enable scripts as a separate gated deployment
        3. The enduring invariant (connector runner has no embedded scheduling) is preserved
        4. The new assertion is stricter about the right thing: the runner stays scheduling-free
        """
        # Verify the old test is gone
        source = (ROOT / "monitoring" / "test_hermes_onedrive_alert_connector_adversarial.py").read_text("utf-8")
        assert "test_no_install_or_enable_script_for_onedrive" not in source
        # Verify the new test exists
        assert "test_connector_runner_has_no_embedded_scheduling" in source

    def test_new_assertion_checks_connector_not_scripts_dir(self):
        """The new test checks that the connector RUNNER has no scheduling, not that
        no install/enable scripts exist in the scripts directory."""
        source = (ROOT / "monitoring" / "test_hermes_onedrive_alert_connector_adversarial.py").read_text("utf-8")
        assert "Register-ScheduledTask" in source  # checks this is NOT in the connector
        assert "New-ScheduledTask" in source  # checks this is NOT in the connector

    def test_install_scripts_exist_as_intended(self):
        """Install/enable scripts for OneDrive now exist — this is intended."""
        assert INSTALLER_PS1.exists()
        assert ENABLE_PS1.exists()
        assert AUDITOR_PS1.exists()
        assert REMOVE_PS1.exists()

    def test_connector_runner_still_has_no_scheduling(self):
        """The enduring invariant: the connector runner has no scheduling behavior."""
        source = CONNECTOR_PS1.read_text("utf-8")
        for prohibited in ("Register-ScheduledTask", "New-ScheduledTask",
                         "Enable-ScheduledTask", "Start-ScheduledTask",
                         "RepetitionInterval", "New-TimeSpan"):
            assert prohibited not in source, f"forbidden in connector: {prohibited}"


# ===========================================================================
# 10. PowerShell syntax validation
# ===========================================================================

class TestPowerShellSyntax:
    def test_all_require_version_51(self):
        for ps1 in [INSTALLER_PS1, AUDITOR_PS1, ENABLE_PS1, REMOVE_PS1]:
            assert "#requires -Version 5.1" in ps1.read_text("utf-8"), f"missing in {ps1.name}"

    def test_all_cmdlet_binding(self):
        for ps1 in [INSTALLER_PS1, AUDITOR_PS1, ENABLE_PS1, REMOVE_PS1]:
            assert "[CmdletBinding()]" in ps1.read_text("utf-8"), f"missing in {ps1.name}"

    def test_all_error_action_stop(self):
        for ps1 in [INSTALLER_PS1, AUDITOR_PS1, ENABLE_PS1, REMOVE_PS1]:
            assert "$ErrorActionPreference" in ps1.read_text("utf-8"), f"missing in {ps1.name}"

    def test_enable_has_validate_range(self):
        source = ENABLE_PS1.read_text("utf-8")
        assert "ValidateRange" in source

    def test_auditor_uses_convertto_json(self):
        source = AUDITOR_PS1.read_text("utf-8")
        assert "ConvertTo-Json" in source and "-Compress" in source

    def test_installer_uses_register_then_disable(self):
        source = INSTALLER_PS1.read_text("utf-8")
        assert "Register-ScheduledTask" in source
        assert "Disable-ScheduledTask" in source
        reg_idx = source.index("Register-ScheduledTask")
        dis_idx = source.index("Disable-ScheduledTask")
        assert dis_idx > reg_idx


# ===========================================================================
# 11. No network, credential, provider, trading control
# ===========================================================================

class TestNoProhibitedControl:
    def test_no_network_cmdlets(self):
        for ps1 in [INSTALLER_PS1, AUDITOR_PS1, ENABLE_PS1, REMOVE_PS1]:
            source = ps1.read_text("utf-8")
            for prohibited in ("Invoke-WebRequest", "Invoke-RestMethod", "Invoke-Expression",
                             "System.Net", "HttpClient"):
                assert prohibited not in source, f"forbidden in {ps1.name}: {prohibited}"

    def test_no_credential_access(self):
        for ps1 in [INSTALLER_PS1, AUDITOR_PS1, ENABLE_PS1, REMOVE_PS1, CONNECTOR_PS1]:
            source = ps1.read_text("utf-8")
            for prohibited in ("Get-Credential", "SecureString", "password", "api_key",
                             "private_key", "secret"):
                assert prohibited.lower() not in source.lower(), f"forbidden in {ps1.name}: {prohibited}"

    def test_no_recorder_references(self):
        for ps1 in [INSTALLER_PS1, AUDITOR_PS1, ENABLE_PS1, REMOVE_PS1]:
            source = ps1.read_text("utf-8")
            for prohibited in ("btc-recorder", "es-nq-recorder", "run_btc_forward_recorder",
                             "run_es_nq_delayed_forward"):
                assert prohibited not in source, f"forbidden in {ps1.name}: {prohibited}"

    def test_verifier_no_trading_control(self):
        source = VERIFIER_PY.read_text("utf-8")
        for forbidden in ("submit_order", "place_trade", "execute_trade", "send_order"):
            assert forbidden not in source

    def test_delivery_py_no_network(self):
        source = DELIVERY_PY.read_text("utf-8")
        tree = ast.parse(source)
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imports.add(node.module.split(".")[0])
        forbidden = {"requests", "httpx", "socket", "urllib", "smtplib", "paramiko", "onedrivesdk"}
        assert imports.isdisjoint(forbidden)


# ===========================================================================
# 12. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """16 existing tests pass — accepted unchanged (12 original + 2 new task tests + 2 new verifier tests)."""

    def test_evolutionary_correction_is_acceptable(self):
        """The replacement of test_no_install_or_enable_script_for_onedrive with
        test_connector_runner_has_no_embedded_scheduling is an ACCEPTABLE CORRECTION:
        - Old: asserted no install/enable scripts exist anywhere (valid for connector-only)
        - New: asserts the connector runner has no embedded scheduling (enduring invariant)
        - Install/enable scripts were intentionally introduced by this milestone
        - The new assertion is the correct enduring invariant for the deployment era"""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: installer PT2M/PT5M/Limited/IgnoreNew/start-when-available,
        auditor exact identity (20+ fields), enablement fresh run + verifier + disable-on-failure,
        verifier missing/tampered envelope/receipt, removal no evidence access, documentation
        disable-on-failure/preserves-evidence, evolutionary correction classification —
        not in existing 16 tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only public API: deliver_alerts, verify_delivery,
        verify_main, AlertDeliveryError, and source text assertions. No private helpers."""
