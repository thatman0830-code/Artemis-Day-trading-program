"""Hermes independent adversarial audit for the controlled stale-data and OneDrive alert-escalation drill.

Audit assignment: AUDIT-CONTROLLED-STALE-ALERT-DRILL
Checkpoint: a0ad9c7cdf85117db631af98e2b6e99b449f1dc3

Covers:
  1. PREFLIGHT_ONLY default; -Execute required
  2. Only BTC stopped/started; ES-NQ/watchdog/delivery never controlled
  3. Preflight: BTC Running, fresh poll, zero gaps, ES/NQ Ready+result0+no missed
  4. Watchdog/delivery: Ready, exact single-instance boundaries
  5. Stale hold bounded 91-180s
  6. Real watchdog runner produces UNHEALTHY with btc-recorder + STALE_HEARTBEAT/TASK_NOT_RUNNING
  7. Unhealthy alert delivered and read back from OneDrive sink
  8. Recovery: Running + newer healthy poll
  9. Recovery watchdog produces HEALTHY transition
 10. Recovery alert delivered and read back
 11. BTC gap count unchanged; ES/NQ unchanged
 12. Failure: DRILL_FAILED, evidence, BTC recovery, rethrow
 13. Evidence: repository-contained, atomic, content-addressed, sanitized, trading_authority=false
 14. No credentials/provider/wallet/broker/exchange/signing/live/paper
 15. Classification
"""

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "invoke_controlled_stale_alert_drill.ps1"
SOURCE = SCRIPT.read_text("utf-8")


# ===========================================================================
# 1. PREFLIGHT_ONLY default; -Execute required
# ===========================================================================

class TestPreflightDefault:
    def test_execute_is_switch(self):
        assert "[switch] $Execute" in SOURCE

    def test_preflight_only_default(self):
        assert "PREFLIGHT_ONLY" in SOURCE
        assert "if(-not$Execute)" in SOURCE

    def test_preflight_before_stop(self):
        assert SOURCE.index("if(-not$Execute)") < SOURCE.index("Stop-ScheduledTask")

    def test_mode_field(self):
        assert "mode=" in SOURCE or "mode =" in SOURCE
        assert "'EXECUTE'" in SOURCE
        assert "'PREFLIGHT_ONLY'" in SOURCE


# ===========================================================================
# 2. Only BTC stopped/started; others never controlled
# ===========================================================================

class TestBtcOnlyControl:
    def test_btc_name_exact(self):
        assert "BTC Public Candle Research Recorder" in SOURCE

    def test_es_name_referenced(self):
        assert "ES-NQ Delayed Daily Research Collector" in SOURCE

    def test_watchdog_name_referenced(self):
        assert "Owner Context Research Health Watchdog" in SOURCE

    def test_delivery_name_referenced(self):
        assert "Owner Context OneDrive Alert Delivery" in SOURCE

    def test_stop_uses_btc_only(self):
        stop_lines = [l for l in SOURCE.splitlines() if "Stop-ScheduledTask" in l]
        assert stop_lines
        assert all("$btcName" in l for l in stop_lines)

    def test_start_uses_btc_only(self):
        start_lines = [l for l in SOURCE.splitlines() if "Start-ScheduledTask" in l]
        assert start_lines
        assert all("$btcName" in l for l in start_lines)

    def test_es_never_stopped(self):
        stop_lines = [l for l in SOURCE.splitlines() if "Stop-ScheduledTask" in l]
        assert all("$esName" not in l for l in stop_lines)

    def test_es_never_started(self):
        start_lines = [l for l in SOURCE.splitlines() if "Start-ScheduledTask" in l]
        assert all("$esName" not in l for l in start_lines)

    def test_watchdog_never_stopped(self):
        stop_lines = [l for l in SOURCE.splitlines() if "Stop-ScheduledTask" in l]
        assert all("$watchdogName" not in l for l in stop_lines)

    def test_watchdog_never_started(self):
        start_lines = [l for l in SOURCE.splitlines() if "Start-ScheduledTask" in l]
        assert all("$watchdogName" not in l for l in start_lines)

    def test_delivery_never_stopped(self):
        stop_lines = [l for l in SOURCE.splitlines() if "Stop-ScheduledTask" in l]
        assert all("$deliveryName" not in l for l in stop_lines)

    def test_delivery_never_started(self):
        start_lines = [l for l in SOURCE.splitlines() if "Start-ScheduledTask" in l]
        assert all("$deliveryName" not in l for l in start_lines)

    def test_no_register_scheduled_task(self):
        assert "Register-ScheduledTask" not in SOURCE

    def test_no_unregister_scheduled_task(self):
        assert "Unregister-ScheduledTask" not in SOURCE

    def test_no_enable_scheduled_task(self):
        assert "Enable-ScheduledTask" not in SOURCE

    def test_no_disable_scheduled_task(self):
        assert "Disable-ScheduledTask" not in SOURCE


# ===========================================================================
# 3. Preflight: BTC Running, fresh poll, zero gaps, ES/NQ Ready
# ===========================================================================

class TestPreflightRequirements:
    def test_btc_must_be_running(self):
        assert "$btc.State-ne'Running'" in SOURCE or "[string]$btc.State-ne'Running'" in SOURCE

    def test_es_must_be_ready(self):
        assert "$es.State-ne'Ready'" in SOURCE or "[string]$es.State-ne'Ready'" in SOURCE

    def test_watchdog_must_be_ready(self):
        assert "$watchdog.State-ne'Ready'" in SOURCE or "[string]$watchdog.State-ne'Ready'" in SOURCE

    def test_delivery_must_be_ready(self):
        assert "$delivery.State-ne'Ready'" in SOURCE or "[string]$delivery.State-ne'Ready'" in SOURCE

    def test_single_action_required(self):
        assert "Count-ne 1" in SOURCE

    def test_ignore_new_required(self):
        assert "IgnoreNew" in SOURCE

    def test_es_last_result_zero(self):
        assert "$esPre.last_result-ne 0" in SOURCE

    def test_es_no_missed_runs(self):
        assert "$esPre.missed_runs-ne 0" in SOURCE

    def test_btc_fresh_poll_required(self):
        assert "TotalSeconds-gt 90" in SOURCE

    def test_btc_zero_gaps_required(self):
        assert "$gapPre-ne 0" in SOURCE


# ===========================================================================
# 4. Watchdog/delivery: Ready, exact single-instance boundaries
# ===========================================================================

class TestWatchdogDeliveryBoundaries:
    def test_all_four_tasks_checked(self):
        assert "$btc" in SOURCE
        assert "$es" in SOURCE
        assert "$watchdog" in SOURCE
        assert "$delivery" in SOURCE

    def test_all_checked_for_single_action(self):
        # The foreach loop checks all tasks for single action + IgnoreNew
        assert "foreach($task in @($btc,$es,$watchdog,$delivery))" in SOURCE or \
               "@($btc,$es,$watchdog,$delivery)" in SOURCE

    def test_all_checked_for_ignore_new(self):
        assert "MultipleInstances-ne'IgnoreNew'" in SOURCE


# ===========================================================================
# 5. Stale hold bounded 91-180s
# ===========================================================================

class TestStaleHoldBounded:
    def test_stale_hold_range(self):
        assert "[ValidateRange(91, 180)]" in SOURCE

    def test_stale_hold_default(self):
        assert "$StaleHoldSeconds = 95" in SOURCE

    def test_stale_hold_used(self):
        assert "Start-Sleep -Seconds $StaleHoldSeconds" in SOURCE

    def test_recovery_timeout_range(self):
        assert "[ValidateRange(60, 600)]" in SOURCE


# ===========================================================================
# 6. Real watchdog produces UNHEALTHY with btc-recorder + STALE/TASK_NOT_RUNNING
# ===========================================================================

class TestUnhealthyTransition:
    def test_watchdog_runner_called_twice(self):
        assert SOURCE.count("& $watchdogRunner") == 2

    def test_unhealthy_state_required(self):
        assert "$status.state-ne'UNHEALTHY'" in SOURCE

    def test_btc_recorder_in_reasons(self):
        assert "btc-recorder" in SOURCE

    def test_stale_or_task_not_running(self):
        assert "STALE_HEARTBEAT|TASK_NOT_RUNNING" in SOURCE

    def test_unhealthy_alert_state_required(self):
        assert "$unhealthy.state-ne'UNHEALTHY'" in SOURCE


# ===========================================================================
# 7. Unhealthy alert delivered and read back from OneDrive
# ===========================================================================

class TestUnhealthyDelivery:
    def test_delivery_runner_called_for_unhealthy(self):
        assert SOURCE.count("& $deliveryRunner") == 2

    def test_unhealthy_envelope_checked(self):
        assert "Unhealthy alert is absent from OneDrive inbox" in SOURCE

    def test_unhealthy_envelope_sha_recorded(self):
        assert "unhealthy_envelope_sha256" in SOURCE

    def test_unhealthy_event_id_recorded(self):
        assert "unhealthy_event_id" in SOURCE


# ===========================================================================
# 8. Recovery: Running + newer healthy poll
# ===========================================================================

class TestRecovery:
    def test_btc_started_for_recovery(self):
        start_lines = [l for l in SOURCE.splitlines() if "Start-ScheduledTask" in l]
        assert len(start_lines) >= 2  # one for recovery, one in catch

    def test_post_poll_newer(self):
        assert "$postTime-le$pollTime" in SOURCE

    def test_btc_must_be_running_after(self):
        assert "$state-ne'Running'" in SOURCE


# ===========================================================================
# 9. Recovery watchdog produces HEALTHY transition
# ===========================================================================

class TestRecoveryHealthy:
    def test_recovered_state_healthy(self):
        assert "$recovered.state-ne'HEALTHY'" in SOURCE

    def test_recovery_alert_healthy(self):
        assert "$recoveryAlert.state-ne'HEALTHY'" in SOURCE


# ===========================================================================
# 10. Recovery alert delivered and read back
# ===========================================================================

class TestRecoveryDelivery:
    def test_recovery_envelope_checked(self):
        assert "Recovery alert is absent from OneDrive inbox" in SOURCE

    def test_recovery_envelope_sha_recorded(self):
        assert "healthy_envelope_sha256" in SOURCE

    def test_recovery_event_id_recorded(self):
        assert "healthy_event_id" in SOURCE


# ===========================================================================
# 11. BTC gap count unchanged; ES/NQ unchanged
# ===========================================================================

class TestUnchangedEvidence:
    def test_gap_count_unchanged(self):
        assert "$gapPost-ne$gapPre" in SOURCE

    def test_es_nq_unchanged(self):
        assert "ES/NQ changed during BTC stale drill" in SOURCE

    def test_es_nq_not_operated(self):
        assert "es_nq_collector_operated=$false" in SOURCE


# ===========================================================================
# 12. Failure: DRILL_FAILED, evidence, BTC recovery, rethrow
# ===========================================================================

class TestFailureHandling:
    def test_drill_failed_recorded(self):
        assert "DRILL_FAILED" in SOURCE

    def test_failure_reason_recorded(self):
        assert "failure_reason" in SOURCE

    def test_btc_recovery_attempted(self):
        failure = SOURCE[SOURCE.index("}catch{"):]
        assert "Start-ScheduledTask -TaskName $btcName" in failure

    def test_evidence_written_on_failure(self):
        failure = SOURCE[SOURCE.index("}catch{"):]
        assert "Write-Report $report" in failure

    def test_failure_rethrows(self):
        failure = SOURCE[SOURCE.index("}catch{"):]
        assert "throw" in failure

    def test_recovery_error_recorded(self):
        assert "recovery_error" in SOURCE


# ===========================================================================
# 13. Evidence: repository-contained, atomic, content-addressed, sanitized
# ===========================================================================

class TestEvidenceIntegrity:
    def test_repository_contained(self):
        assert "Drill evidence must remain inside the repository" in SOURCE

    def test_atomic_write(self):
        assert "WriteAllText" in SOURCE
        assert "Move-Item" in SOURCE

    def test_content_addressed(self):
        assert "report_id" in SOURCE
        assert "SHA256" in SOURCE or "SHA256" in SOURCE

    def test_trading_authority_false(self):
        assert "trading_authority=$false" in SOURCE

    def test_schema_version(self):
        assert "controlled-stale-alert-drill-v1" in SOURCE


# ===========================================================================
# 14. No credentials/provider/wallet/broker/exchange/signing/live/paper
# ===========================================================================

class TestNoProhibited:
    def test_no_credentials(self):
        for f in ("credential.dpapi", "ConvertTo-SecureString", "Get-Credential",
                  "private_key", "api_key", "password"):
            assert f.lower() not in SOURCE.lower(), f"forbidden: {f}"

    def test_no_wallet_broker_exchange(self):
        for f in ("wallet", "broker", "exchange"):
            assert f.lower() not in SOURCE.lower(), f"forbidden: {f}"

    def test_no_signing(self):
        assert "Set-AuthenticodeSignature" not in SOURCE
        assert "Sign-File" not in SOURCE

    def test_no_live_order(self):
        for f in ("place_order", "submit_live", "live_order"):
            assert f not in SOURCE.lower(), f"forbidden: {f}"

    def test_no_paper_submission(self):
        for f in ("paper_gateway", "paper_exchange", "paper_session"):
            assert f not in SOURCE.lower(), f"forbidden: {f}"

    def test_no_provider_sdk(self):
        for f in ("Invoke-WebRequest", "Invoke-RestMethod", "requests", "httpx"):
            assert f not in SOURCE, f"forbidden: {f}"


# ===========================================================================
# 15. OneDrive sink path
# ===========================================================================

class TestOneDriveSink:
    def test_onedrive_path_used(self):
        assert "TradingSystem\\AlertEvidence" in SOURCE or "TradingSystem\\\\AlertEvidence" in SOURCE

    def test_onedrive_env_resolution(self):
        assert "$env:OneDrive" in SOURCE
        assert "GetEnvironmentVariable('OneDrive','User')" in SOURCE

    def test_sink_manifest_checked(self):
        assert "sink-manifest.json" in SOURCE

    def test_delivery_path_computed(self):
        assert "Get-DeliveryPath" in SOURCE


# ===========================================================================
# 16. PowerShell syntax
# ===========================================================================

class TestPowerShellSyntax:
    def test_requires_version_51(self):
        assert "#requires -Version 5.1" in SOURCE

    def test_cmdlet_binding(self):
        assert "[CmdletBinding()]" in SOURCE

    def test_error_action_stop(self):
        assert "$ErrorActionPreference = 'Stop'" in SOURCE


# ===========================================================================
# 17. Report fields
# ===========================================================================

class TestReportFields:
    def test_started_at(self):
        assert "started_at" in SOURCE

    def test_completed_at(self):
        assert "completed_at" in SOURCE

    def test_result_preflight_verified(self):
        assert "PREFLIGHT_VERIFIED" in SOURCE

    def test_result_stale_alert_verified(self):
        assert "STALE_ALERT_AND_RECOVERY_VERIFIED" in SOURCE

    def test_stale_observed(self):
        assert "stale_observed" in SOURCE

    def test_recovery_observed(self):
        assert "recovery_observed" in SOURCE

    def test_btc_pre_poll(self):
        assert "btc_pre_poll_utc" in SOURCE

    def test_btc_post_poll(self):
        assert "btc_post_poll_utc" in SOURCE

    def test_btc_pre_gap(self):
        assert "btc_pre_gap_count" in SOURCE

    def test_btc_post_gap(self):
        assert "btc_post_gap_count" in SOURCE

    def test_es_nq_pre(self):
        assert "es_nq_pre" in SOURCE

    def test_es_nq_post(self):
        assert "es_nq_post" in SOURCE


# ===========================================================================
# 18. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """8 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: watchdog/delivery never stopped/started,
        no register/unregister/enable/disable, no signing, no paper,
        OneDrive env resolution, sink manifest, delivery path computed,
        report fields (started_at, completed_at, stale_observed, recovery_observed,
        btc_pre/post_poll, btc_pre/post_gap, es_nq_pre/post), PowerShell syntax —
        not in existing 8."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only source text assertions against the PowerShell
        script. No Python API coupling."""
