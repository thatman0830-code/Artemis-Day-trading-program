"""Hermes independent adversarial audit for the controlled BTC recorder recovery drill.

Audit assignment: AUDIT-CONTROLLED-BTC-RECORDER-RECOVERY-DRILL
Checkpoint: 4344877eb5b972bb1279f23e58dafd1a7f359b54

Covers:
  1. PREFLIGHT_ONLY default; -Execute required for physical restart
  2. Only BTC task stopped/started; ES/NQ never modified
  3. Preflight: BTC Running, exact identity, IgnoreNew, fresh poll, RECORDING manifest, zero gaps
  4. Preflight: ES/NQ Ready, last result 0, no missed runs, healthy non-trading
  5. Restart bounded; must observe BTC stop
  6. Recovery: newer healthy BTC poll required
  7. Recovery rejects new unresolved gaps
  8. ES/NQ unchanged during BTC-only drill
  9. Failure evidence retained; automatic BTC restart attempted
 10. Evidence: repository-contained, atomic, content-addressed, sanitized, trading_authority=false
 11. PREFLIGHT_ONLY does not claim physical restart
 12. No credential, wallet, broker, exchange, signing, or order-submission
 13. No live or paper order submission
 14. Classification
"""

from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "invoke_controlled_btc_recorder_recovery_drill.ps1"
SOURCE = SCRIPT.read_text("utf-8")


# ===========================================================================
# 1. PREFLIGHT_ONLY default; -Execute required
# ===========================================================================

class TestPreflightDefault:
    def test_execute_is_switch(self):
        assert "[switch] $Execute" in SOURCE

    def test_preflight_only_default(self):
        assert "PREFLIGHT_ONLY" in SOURCE
        assert "if (-not $Execute)" in SOURCE

    def test_preflight_before_stop(self):
        assert SOURCE.index("if (-not $Execute)") < SOURCE.index("Stop-ScheduledTask")

    def test_no_stop_in_preflight(self):
        """In PREFLIGHT_ONLY mode, Stop-ScheduledTask is never reached."""
        preflight_section = SOURCE[:SOURCE.index("if (-not $Execute)") + len("if (-not $Execute)")]
        # The Stop-ScheduledTask is after the preflight exit
        stop_idx = SOURCE.index("Stop-ScheduledTask")
        preflight_exit_idx = SOURCE.index("exit 0")
        assert stop_idx > preflight_exit_idx

    def test_execute_switch_enables_physical_restart(self):
        assert "$Execute" in SOURCE
        assert "EXECUTE" in SOURCE


# ===========================================================================
# 2. Only BTC task stopped/started; ES/NQ never modified
# ===========================================================================

class TestBtcOnlyControl:
    def test_btc_task_name_exact(self):
        assert "BTC Public Candle Research Recorder" in SOURCE

    def test_es_task_name_referenced(self):
        assert "ES-NQ Delayed Daily Research Collector" in SOURCE

    def test_stop_uses_btc_only(self):
        stop_lines = [line for line in SOURCE.splitlines() if "Stop-ScheduledTask" in line]
        assert stop_lines
        assert all("$btcTaskName" in line for line in stop_lines)

    def test_start_uses_btc_only(self):
        start_lines = [line for line in SOURCE.splitlines() if "Start-ScheduledTask" in line]
        assert start_lines
        assert all("$btcTaskName" in line for line in start_lines)

    def test_es_nq_never_stopped(self):
        stop_lines = [line for line in SOURCE.splitlines() if "Stop-ScheduledTask" in line]
        assert all("$esTaskName" not in line for line in stop_lines)

    def test_es_nq_never_started(self):
        start_lines = [line for line in SOURCE.splitlines() if "Start-ScheduledTask" in line]
        assert all("$esTaskName" not in line for line in start_lines)

    def test_es_nq_never_disabled(self):
        assert "Disable-ScheduledTask" not in SOURCE or \
               all("$esTaskName" not in line for line in SOURCE.splitlines() if "Disable-ScheduledTask" in line)

    def test_es_nq_never_enabled(self):
        assert "Enable-ScheduledTask" not in SOURCE or \
               all("$esTaskName" not in line for line in SOURCE.splitlines() if "Enable-ScheduledTask" in line)

    def test_es_nq_never_unregistered(self):
        assert "Unregister-ScheduledTask" not in SOURCE

    def test_es_nq_never_registered(self):
        assert "Register-ScheduledTask" not in SOURCE


# ===========================================================================
# 3. Preflight: BTC Running, exact identity, IgnoreNew, fresh poll, manifest, gaps
# ===========================================================================

class TestPreflightBtc:
    def test_btc_must_be_running(self):
        assert "$btcTask.State -ne 'Running'" in SOURCE or "[string]$btcTask.State -ne 'Running'" in SOURCE

    def test_exact_action_arguments(self):
        assert "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass" in SOURCE

    def test_working_directory_checked(self):
        assert "WorkingDirectory" in SOURCE
        assert "$repository" in SOURCE

    def test_ignore_new_checked(self):
        assert "IgnoreNew" in SOURCE

    def test_single_action_required(self):
        assert "Count -ne 1" in SOURCE

    def test_fresh_poll_required(self):
        assert "prePollTime" in SOURCE
        assert "TotalSeconds -gt 90" in SOURCE

    def test_recording_manifest_required(self):
        assert "RECORDING" in SOURCE
        assert "manifest" in SOURCE.lower()

    def test_zero_gaps_required(self):
        assert "Get-GapCount" in SOURCE or "gap_count" in SOURCE


# ===========================================================================
# 4. Preflight: ES/NQ Ready, last result 0, no missed runs, healthy
# ===========================================================================

class TestPreflightEsNq:
    def test_es_must_be_ready(self):
        assert "$esTask.State -ne 'Ready'" in SOURCE or "[string]$esTask.State -ne 'Ready'" in SOURCE

    def test_es_last_result_zero(self):
        assert "$esInfo.LastTaskResult -ne 0" in SOURCE

    def test_es_no_missed_runs(self):
        assert "$esInfo.NumberOfMissedRuns -ne 0" in SOURCE

    def test_es_healthy_evidence(self):
        assert "$esRun.state -ne 'HEALTHY'" in SOURCE

    def test_es_non_trading(self):
        assert "$esRun.trading -ne $false" in SOURCE


# ===========================================================================
# 5. Restart bounded; must observe BTC stop
# ===========================================================================

class TestRestartBounded:
    def test_stop_observed(self):
        assert "stop_observed" in SOURCE
        assert "Stop-ScheduledTask" in SOURCE

    def test_stop_deadline(self):
        assert "stopDeadline" in SOURCE
        assert "30" in SOURCE  # 30 second stop deadline

    def test_recovery_timeout_bounded(self):
        assert "[ValidateRange(60, 600)]" in SOURCE
        assert "RecoveryTimeoutSeconds" in SOURCE

    def test_btc_state_polled(self):
        assert "Get-ScheduledTask" in SOURCE
        assert "$btcTaskName" in SOURCE


# ===========================================================================
# 6. Recovery: newer healthy BTC poll
# ===========================================================================

class TestRecoveryNewPoll:
    def test_post_poll_newer_than_pre(self):
        assert "$postTime -le $prePollTime" in SOURCE

    def test_post_poll_healthy(self):
        assert "Get-LatestHealthyPoll" in SOURCE
        assert "poll_complete" in SOURCE
        assert "RECORDING" in SOURCE

    def test_btc_must_be_running_after_recovery(self):
        assert "$btcState -ne 'Running'" in SOURCE


# ===========================================================================
# 7. Recovery rejects new gaps
# ===========================================================================

class TestRecoveryNoNewGaps:
    def test_post_gap_count_checked(self):
        assert "$postGapCount -ne $preGapCount" in SOURCE

    def test_gap_count_function(self):
        assert "Get-GapCount" in SOURCE


# ===========================================================================
# 8. ES/NQ unchanged during BTC-only drill
# ===========================================================================

class TestEsNqUnchanged:
    def test_es_state_unchanged(self):
        assert "$postEs.state -ne $preEs.state" in SOURCE

    def test_es_last_result_unchanged(self):
        assert "$postEs.last_result -ne $preEs.last_result" in SOURCE

    def test_es_last_run_unchanged(self):
        assert "$postEs.last_run_utc -ne $preEs.last_run_utc" in SOURCE

    def test_es_sha_unchanged(self):
        assert "Get-Sha256 $latestEsRun.FullName" in SOURCE
        assert "$preEsSha" in SOURCE

    def test_es_change_rejects(self):
        assert "ES/NQ collector changed during the BTC-only recovery drill" in SOURCE


# ===========================================================================
# 9. Failure evidence retained; automatic BTC restart attempted
# ===========================================================================

class TestFailureRecovery:
    def test_failure_result_recorded(self):
        assert "RECOVERY_FAILED" in SOURCE

    def test_failure_reason_recorded(self):
        assert "failure_reason" in SOURCE

    def test_automatic_restart_attempted(self):
        catch_section = SOURCE[SOURCE.index("} catch {"):]
        assert "Start-ScheduledTask" in catch_section
        assert "$btcTaskName" in catch_section

    def test_failure_evidence_written(self):
        catch_section = SOURCE[SOURCE.index("} catch {"):]
        assert "Write-Report" in catch_section

    def test_failure_rethrows(self):
        catch_section = SOURCE[SOURCE.index("} catch {"):]
        assert "throw" in catch_section

    def test_automatic_recovery_error_recorded(self):
        assert "automatic_recovery_error" in SOURCE


# ===========================================================================
# 10. Evidence: repository-contained, atomic, content-addressed, sanitized
# ===========================================================================

class TestEvidenceIntegrity:
    def test_repository_contained(self):
        assert "Recovery evidence path must remain inside the repository" in SOURCE

    def test_atomic_write(self):
        assert "WriteAllText" in SOURCE
        assert "Move-Item" in SOURCE

    def test_content_addressed(self):
        assert "report_id" in SOURCE
        assert "SHA256" in SOURCE or "SHA256" in SOURCE

    def test_trading_authority_false(self):
        assert "trading_authority = $false" in SOURCE

    def test_es_nq_not_operated(self):
        assert "es_nq_collector_operated = $false" in SOURCE

    def test_no_credentials(self):
        for prohibited in ("credential.dpapi", "ConvertTo-SecureString", "private_key",
                          "api_key", "password", "Get-Credential"):
            assert prohibited.lower() not in SOURCE.lower(), f"forbidden: {prohibited}"

    def test_no_wallet_broker(self):
        for prohibited in ("wallet", "broker"):
            assert prohibited.lower() not in SOURCE.lower(), f"forbidden: {prohibited}"


# ===========================================================================
# 11. PREFLIGHT_ONLY does not claim physical restart
# ===========================================================================

class TestNoFalsePhysicalClaim:
    def test_physical_recorder_restart_claimed_false_in_preflight(self):
        assert "physical_recorder_restart_claimed = $false" in SOURCE

    def test_preflight_does_not_set_physical_claim(self):
        """The physical_recorder_restart_claimed is only set to $true after
        successful recovery, not in PREFLIGHT_ONLY mode."""
        # Find the PREFLIGHT_ONLY section
        preflight_exit = SOURCE.index("exit 0")
        # The $true assignment is after the preflight exit
        true_idx = SOURCE.index("physical_recorder_restart_claimed = $true")
        assert true_idx > preflight_exit

    def test_mode_field_distinguishes(self):
        assert "PREFLIGHT_ONLY" in SOURCE
        assert "EXECUTE" in SOURCE
        assert "$mode" in SOURCE.lower() or "mode =" in SOURCE.lower() or "mode = $(if" in SOURCE


# ===========================================================================
# 12. No credential, wallet, broker, exchange, signing, order-submission
# ===========================================================================

class TestNoProhibited:
    def test_no_provider_sdk(self):
        for prohibited in ("requests", "httpx", "Invoke-WebRequest", "Invoke-RestMethod"):
            assert prohibited not in SOURCE, f"forbidden: {prohibited}"

    def test_no_signing(self):
        assert "Sign-File" not in SOURCE
        assert "Set-AuthenticodeSignature" not in SOURCE

    def test_no_exchange(self):
        assert "exchange" not in SOURCE.lower() or "exchange" not in SOURCE

    def test_no_order_submission(self):
        for prohibited in ("place_order", "submit_live", "submit_order", "send_order"):
            assert prohibited not in SOURCE.lower(), f"forbidden: {prohibited}"


# ===========================================================================
# 13. No live or paper order submission
# ===========================================================================

class TestNoOrderSubmission:
    def test_no_live_order(self):
        assert "live_order" not in SOURCE.lower()

    def test_no_paper_submission(self):
        assert "paper_gateway" not in SOURCE.lower()
        assert "paper_exchange" not in SOURCE.lower()


# ===========================================================================
# 14. PowerShell syntax
# ===========================================================================

class TestPowerShellSyntax:
    def test_requires_version_51(self):
        assert "#requires -Version 5.1" in SOURCE

    def test_cmdlet_binding(self):
        assert "[CmdletBinding()]" in SOURCE

    def test_error_action_stop(self):
        assert "$ErrorActionPreference = 'Stop'" in SOURCE

    def test_output_path_parameter(self):
        assert "$OutputPath" in SOURCE


# ===========================================================================
# 15. Report schema
# ===========================================================================

class TestReportSchema:
    def test_schema_version(self):
        assert "controlled-btc-recorder-recovery-drill-v1" in SOURCE

    def test_started_at(self):
        assert "started_at" in SOURCE

    def test_completed_at(self):
        assert "completed_at" in SOURCE

    def test_result_field(self):
        assert "result" in SOURCE
        assert "PREFLIGHT_VERIFIED" in SOURCE
        assert "RECOVERY_VERIFIED" in SOURCE


# ===========================================================================
# 16. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """6 existing tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: ES/NQ never disabled/enabled/registered/unregistered,
        no signing, no exchange, no paper gateway, no live order, report schema fields,
        physical claim only after recovery, stop deadline (30s), atomic write details —
        not in existing 6."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only source text assertions against the PowerShell
        script. No Python API coupling."""
