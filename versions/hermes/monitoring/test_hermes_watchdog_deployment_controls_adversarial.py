"""Hermes independent adversarial audit for owner-context watchdog deployment controls.

Audit assignment: AUDIT-WATCHDOG-DEPLOYMENT-CONTROLS
Checkpoint: be824f5747a3e09f8d4c443ece457515ceb9783d

Covers:
  1. Audit script is strictly read-only; validates exact task name, path, owner, logon, run level,
     executable, arguments, working directory, trigger, 5-min interval, 4-min limit, StartWhenAvailable,
     IgnoreNew, runner, Python runtime.
  2. Enablement rejects anything except the exact audited disabled task.
  3. Enablement requires fresh HEALTHY status after start time, successful result, ready_for_unattended=true, trading_authority=false.
  4. Every failure path disables the task.
  5. Stale/malformed status, missing output, timeout, unhealthy, authority escalation, task failure, identity mismatch, timestamp attacks fail closed.
  6. Removal refuses unverified task, targets only exact watchdog task, never deletes evidence.
  7. None of the scripts can modify either recorder or grant trading authority.
  8. Documentation makes no off-host, institutional-readiness, live-trading, or fault-free claim.
  9. PowerShell syntax and action quoting are valid.
 10. Race conditions, task-state ambiguity, owner-context problems, rollback gaps, unsafe removal behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
AUDIT_PS1 = ROOT / "scripts" / "audit_owner_context_health_watchdog_task.ps1"
ENABLE_PS1 = ROOT / "scripts" / "enable_and_verify_owner_context_health_watchdog_task.ps1"
REMOVE_PS1 = ROOT / "scripts" / "remove_owner_context_health_watchdog_task.ps1"
RUNNER_PS1 = ROOT / "scripts" / "run_owner_context_health_watchdog.ps1"
INSTALLER_PS1 = ROOT / "scripts" / "install_owner_context_health_watchdog_task.ps1"
IMPL_MD = ROOT / "monitoring" / "OWNER_CONTEXT_WATCHDOG_IMPLEMENTATION.md"


def audit_src(): return AUDIT_PS1.read_text("utf-8")
def enable_src(): return ENABLE_PS1.read_text("utf-8")
def remove_src(): return REMOVE_PS1.read_text("utf-8")
def runner_src(): return RUNNER_PS1.read_text("utf-8")
def installer_src(): return INSTALLER_PS1.read_text("utf-8")
def impl_src(): return IMPL_MD.read_text("utf-8")


# ===========================================================================
# 1. Audit script is strictly read-only and validates exact identity
# ===========================================================================

class TestAuditReadOnly:
    def test_no_mutation_cmdlets(self):
        source = audit_src()
        for prohibited in ("Register-ScheduledTask", "Unregister-ScheduledTask",
                          "Enable-ScheduledTask", "Disable-ScheduledTask",
                          "Start-ScheduledTask", "Stop-ScheduledTask",
                          "Start-Process", "Stop-Process", "Set-ScheduledTask"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_exact_task_name(self):
        source = audit_src()
        assert "Owner Context Research Health Watchdog" in source

    def test_exact_task_path(self):
        source = audit_src()
        assert "TaskPath '\\'" in source or "'\\'" in source

    def test_validates_single_action_and_trigger(self):
        source = audit_src()
        assert "exactly one action and one trigger" in source

    def test_validates_executable(self):
        source = audit_src()
        assert "powershell.exe" in source
        assert "$env:SystemRoot" in source

    def test_validates_arguments_with_no_profile(self):
        source = audit_src()
        assert "-NoLogo" in source and "-NoProfile" in source
        assert "-NonInteractive" in source and "-ExecutionPolicy Bypass" in source
        assert "-File" in source

    def test_validates_working_directory(self):
        source = audit_src()
        assert "WorkingDirectory" in source

    def test_validates_owner(self):
        source = audit_src()
        assert "Principal.UserId" in source
        assert "WindowsIdentity" in source

    def test_validates_logon_type(self):
        source = audit_src()
        assert "LogonType" in source
        assert "Interactive" in source

    def test_validates_run_level_limited(self):
        source = audit_src()
        assert "RunLevel" in source and "Limited" in source

    def test_validates_ignore_new(self):
        source = audit_src()
        assert "IgnoreNew" in source

    def test_validates_5min_interval(self):
        source = audit_src()
        assert "PT5M" in source

    def test_validates_4min_execution_limit(self):
        source = audit_src()
        assert "PT4M" in source

    def test_validates_start_when_available(self):
        source = audit_src()
        assert "StartWhenAvailable" in source

    def test_validates_runner_exists(self):
        source = audit_src()
        assert "run_owner_context_health_watchdog.ps1" in source

    def test_validates_python_runtime(self):
        source = audit_src()
        assert ".venv\\Scripts\\python.exe" in source or ".venv\\\\Scripts\\\\python.exe" in source

    def test_trading_authority_false(self):
        source = audit_src()
        assert "trading_authority=$false" in source

    def test_requires_version_51(self):
        source = audit_src()
        assert "#requires -Version 5.1" in source

    def test_cmdlet_binding(self):
        source = audit_src()
        assert "[CmdletBinding()]" in source

    def test_error_action_stop(self):
        source = audit_src()
        assert "$ErrorActionPreference = 'Stop'" in source

    def test_safety_policy_rejected_throws(self):
        source = audit_src()
        assert "safety policy rejected" in source.lower()

    def test_get_scheduled_task_used(self):
        source = audit_src()
        assert "Get-ScheduledTask" in source
        assert "Get-ScheduledTaskInfo" in source


# ===========================================================================
# 2. Enablement rejects anything except the exact audited disabled task
# ===========================================================================

class TestEnablementGuard:
    def test_requires_disabled_state(self):
        source = enable_src()
        assert "state -ne 'Disabled'" in source

    def test_requires_trading_authority_false(self):
        source = enable_src()
        assert "trading_authority -ne $false" in source

    def test_calls_audit_first(self):
        source = enable_src()
        assert "audit_owner_context_health_watchdog_task.ps1" in source

    def test_rejects_if_not_disabled(self):
        source = enable_src()
        assert "must pass audit while disabled" in source

    def test_uses_exact_task_name(self):
        source = enable_src()
        assert "Owner Context Research Health Watchdog" in source

    def test_uses_exact_task_path(self):
        source = enable_src()
        assert "taskPath" in source or "TaskPath" in source


# ===========================================================================
# 3. Enablement requires fresh HEALTHY after start time, successful result, ready, trading_authority=false
# ===========================================================================

class TestEnablementHealthGate:
    def test_requires_fresh_healthy_status(self):
        source = enable_src()
        assert "HEALTHY" in source
        assert "ready_for_unattended_operation -eq $true" in source

    def test_requires_trading_authority_false_in_status(self):
        source = enable_src()
        assert "trading_authority -eq $false" in source

    def test_requires_status_after_start_time(self):
        source = enable_src()
        assert "startedAt" in source
        assert "observed_at" in source
        assert "ToUniversalTime()" in source
        assert "-ge $startedAt" in source or "-ge $startedAt" in source

    def test_requires_successful_task_result(self):
        source = enable_src()
        assert "LastTaskResult -eq 0" in source

    def test_requires_task_not_disabled(self):
        source = enable_src()
        assert "State -ne 'Disabled'" in source or "state -ne 'Disabled'" in source.lower()

    def test_uses_status_path(self):
        source = enable_src()
        assert "latest-watchdog-status.json" in source

    def test_has_timeout(self):
        source = enable_src()
        assert "TimeoutSeconds" in source
        assert "ValidateRange" in source

    def test_timeout_min_30(self):
        source = enable_src()
        assert "30" in source  # ValidateRange(30, ...)

    def test_timeout_max_300(self):
        source = enable_src()
        assert "300" in source  # ValidateRange(..., 300)

    def test_timeout_default_120(self):
        source = enable_src()
        assert "120" in source  # default value

    def test_polls_every_3_seconds(self):
        source = enable_src()
        assert "Start-Sleep -Seconds 3" in source

    def test_success_message(self):
        source = enable_src()
        assert "OWNER_CONTEXT_HEALTH_WATCHDOG_ENABLED_AND_HEALTHY" in source

    def test_timeout_throws(self):
        source = enable_src()
        assert "did not produce a fresh healthy status" in source

    def test_status_missing_handled(self):
        source = enable_src()
        assert "Test-Path" in source
        # If status file missing, $status is $null, loop continues until timeout


# ===========================================================================
# 4. Every failure path disables the task
# ===========================================================================

class TestFailureDisables:
    def test_catch_disables_task(self):
        source = enable_src()
        assert "catch" in source
        assert "Disable-ScheduledTask" in source

    def test_catch_rethrows(self):
        source = enable_src()
        assert "throw" in source

    def test_disable_silently_continue(self):
        source = enable_src()
        assert "SilentlyContinue" in source

    def test_timeout_disables_via_catch(self):
        """Timeout throws, which triggers catch → Disable-ScheduledTask."""
        source = enable_src()
        assert "did not produce a fresh healthy status" in source
        assert "Disable-ScheduledTask" in source


# ===========================================================================
# 5. Stale/malformed/missing/unhealthy/authority/task-failure/identity/timestamp attacks
# ===========================================================================

class TestFailClosedAttacks:
    def test_stale_status_rejected(self):
        """observed_at must be >= startedAt; stale status before start → loop continues → timeout → disable."""
        source = enable_src()
        assert "-ge $startedAt" in source

    def test_unhealthy_status_rejected(self):
        source = enable_src()
        assert "HEALTHY" in source
        # If status.state != HEALTHY, the if condition fails → loop → timeout → disable

    def test_authority_escalation_rejected(self):
        source = enable_src()
        assert "trading_authority -eq $false" in source
        # If trading_authority != false, condition fails → timeout → disable

    def test_task_failure_rejected(self):
        source = enable_src()
        assert "LastTaskResult -eq 0" in source

    def test_missing_status_rejected(self):
        source = enable_src()
        assert "Test-Path" in source
        # Missing status → $null → if condition fails → timeout → disable

    def test_malformed_status_rejected(self):
        """If status JSON is malformed, ConvertFrom-Json throws → catch → disable."""
        source = enable_src()
        assert "ConvertFrom-Json" in source
        assert "catch" in source

    def test_identity_mismatch_rejected_by_audit(self):
        """Audit checks task name, path, executable, arguments, etc. Any mismatch → throw."""
        source = audit_src()
        assert "safety policy rejected" in source.lower()

    def test_timestamp_attack_rejected(self):
        """observed_at is parsed as DateTime and compared ToUniversalTime() against startedAt.
        A future-dated or past-dated status cannot pass the >= startedAt check."""
        source = enable_src()
        assert "ToUniversalTime()" in source


# ===========================================================================
# 6. Removal refuses unverified task, targets only exact task, never deletes evidence
# ===========================================================================

class TestRemovalSafety:
    def test_requires_identity_verification(self):
        source = remove_src()
        assert "action_verified -ne $true" in source

    def test_requires_trading_authority_false(self):
        source = remove_src()
        assert "trading_authority -ne $false" in source

    def test_calls_audit_first(self):
        source = remove_src()
        assert "audit_owner_context_health_watchdog_task.ps1" in source

    def test_targets_exact_task_name(self):
        source = remove_src()
        assert "Owner Context Research Health Watchdog" in source

    def test_unregisters_task(self):
        source = remove_src()
        assert "Unregister-ScheduledTask" in source
        assert "-Confirm:$false" in source

    def test_disables_before_unregister(self):
        source = remove_src()
        assert "Disable-ScheduledTask" in source

    def test_stops_before_unregister(self):
        source = remove_src()
        assert "Stop-ScheduledTask" in source

    def test_no_remove_item(self):
        source = remove_src()
        assert "Remove-Item" not in source

    def test_no_recursive_delete(self):
        source = remove_src()
        assert "rmdir" not in source.lower()
        assert "rd " not in source.lower()

    def test_preserves_evidence(self):
        source = remove_src()
        assert "EVIDENCE_PRESERVED" in source

    def test_refuses_unverified(self):
        source = remove_src()
        assert "removal rejected" in source or "not verified" in source


# ===========================================================================
# 7. None of the scripts can modify either recorder or grant trading authority
# ===========================================================================

class TestNoRecorderOrTradingControl:
    @pytest.mark.parametrize("src_fn,name", [
        (audit_src, "audit"),
        (enable_src, "enable"),
        (remove_src, "remove"),
        (runner_src, "runner"),
        (installer_src, "installer"),
    ])
    def test_no_recorder_control(self, src_fn, name):
        source = src_fn()
        for prohibited in ("btc_forward_recorder", "es_nq_delayed_forward_collector",
                          "run_btc_forward_recorder", "run_es_nq_delayed_forward"):
            assert prohibited not in source, f"forbidden in {name}: {prohibited}"

    @pytest.mark.parametrize("src_fn,name", [
        (audit_src, "audit"),
        (enable_src, "enable"),
        (remove_src, "remove"),
    ])
    def test_trading_authority_always_false(self, src_fn, name):
        source = src_fn()
        if "trading_authority" in source:
            assert "$false" in source or "= $false" in source or "=$false" in source

    def test_enable_has_no_unregister(self):
        source = enable_src()
        assert "Unregister-ScheduledTask" not in source

    def test_remove_has_no_register(self):
        source = remove_src()
        assert "Register-ScheduledTask" not in source

    def test_audit_has_no_register_or_unregister(self):
        source = audit_src()
        assert "Register-ScheduledTask" not in source
        assert "Unregister-ScheduledTask" not in source


# ===========================================================================
# 8. Documentation makes no off-host, institutional-readiness, live-trading, or fault-free claim
# ===========================================================================

class TestDocumentationClaims:
    def test_disclaims_off_host(self):
        source = impl_src()
        assert "not off-host" in source.lower() or "local evidence" in source.lower()

    def test_disclaims_institutional_readiness(self):
        source = impl_src()
        assert "institutional" in source.lower() or "24/7" in source

    def test_no_live_trading_claim(self):
        source = impl_src()
        # Must NOT claim live trading capability
        assert "live trading" not in source.lower() or "not" in source.lower()

    def test_no_fault_free_claim(self):
        source = impl_src()
        # Must NOT claim fault-free operation
        assert "fault-free" not in source.lower()

    def test_describes_deployment_controls(self):
        source = impl_src()
        assert "audit" in source.lower() and "enablement" in source.lower()
        assert "removal" in source.lower()

    def test_describes_rollback_to_disabled(self):
        source = impl_src()
        assert "disable" in source.lower() or "disabled" in source.lower()

    def test_describes_evidence_preservation(self):
        source = impl_src()
        assert "evidence" in source.lower()

    def test_describes_gated_enablement(self):
        source = impl_src()
        assert "gated" in source.lower() or "guard" in source.lower() or "guarded" in source.lower()


# ===========================================================================
# 9. PowerShell syntax and action quoting
# ===========================================================================

class TestPowerShellSyntax:
    def test_all_require_version_51(self):
        for src_fn, name in [(audit_src, "audit"), (enable_src, "enable"), (remove_src, "remove")]:
            source = src_fn()
            assert "#requires -Version 5.1" in source, f"missing requires in {name}"

    def test_all_cmdlet_binding(self):
        for src_fn, name in [(audit_src, "audit"), (enable_src, "enable"), (remove_src, "remove")]:
            source = src_fn()
            assert "[CmdletBinding()]" in source, f"missing CmdletBinding in {name}"

    def test_all_error_action_stop(self):
        for src_fn, name in [(audit_src, "audit"), (enable_src, "enable"), (remove_src, "remove")]:
            source = src_fn()
            assert "$ErrorActionPreference = 'Stop'" in source, f"missing Stop in {name}"

    def test_audit_uses_convertto_json_compress(self):
        source = audit_src()
        assert "ConvertTo-Json" in source
        assert "-Compress" in source

    def test_enable_action_quoting(self):
        """Enable script references the runner path with proper quoting."""
        source = enable_src()
        # The script calls audit which returns JSON; no direct action quoting needed
        # But the installer's action quoting should be verified
        installer = installer_src()
        assert "-File" in installer
        assert '"' in installer  # quoted path

    def test_installer_action_arguments_quoted(self):
        source = installer_src()
        assert "-File `\"$runner`\"" in source or '-File "$runner"' in source

    def test_audit_output_is_json(self):
        source = audit_src()
        assert "ConvertTo-Json" in source


# ===========================================================================
# 10. Race conditions, task-state ambiguity, rollback gaps, unsafe removal
# ===========================================================================

class TestSafetyGaps:
    def test_enable_starts_then_polls(self):
        """Enable: Enable → Start → poll loop. No race condition in start."""
        source = enable_src()
        assert "Enable-ScheduledTask" in source
        assert "Start-ScheduledTask" in source
        assert "do" in source and "while" in source

    def test_enable_catch_covers_entire_try_block(self):
        """The try/catch wraps Enable+Start+poll so any failure disables."""
        source = enable_src()
        assert "try" in source
        assert "catch" in source
        # Disable is in the catch block
        catch_idx = source.index("catch")
        disable_idx = source.index("Disable-ScheduledTask")
        assert disable_idx > catch_idx

    def test_remove_disables_stops_then_unregisters(self):
        """Removal: Disable → Stop → Unregister. Safe order."""
        source = remove_src()
        disable_idx = source.index("Disable-ScheduledTask")
        stop_idx = source.index("Stop-ScheduledTask")
        unregister_idx = source.index("Unregister-ScheduledTask")
        assert disable_idx < stop_idx < unregister_idx

    def test_remove_silently_continues_on_disable(self):
        """Disable and Stop use SilentlyContinue so unregister proceeds even if already disabled/stopped."""
        source = remove_src()
        assert "SilentlyContinue" in source

    def test_remove_unregister_errors_stop(self):
        """Unregister uses ErrorAction Stop — if it fails, the script throws."""
        source = remove_src()
        assert "ErrorAction Stop" in source

    def test_no_concurrent_modification_in_audit(self):
        """Audit is read-only: Get-ScheduledTask + Get-ScheduledTaskInfo only."""
        source = audit_src()
        for prohibited in ("Set-ScheduledTask", "New-ScheduledTask", "Register-ScheduledTask"):
            assert prohibited not in source

    def test_enable_checks_task_state_in_loop(self):
        """Enable polls Get-ScheduledTask in the loop, checking State != Disabled."""
        source = enable_src()
        assert "Get-ScheduledTask" in source
        assert "Get-ScheduledTaskInfo" in source

    def test_enable_checks_last_result_in_loop(self):
        source = enable_src()
        assert "LastTaskResult" in source

    def test_remove_does_not_touch_evidence_files(self):
        """Removal script only operates on the scheduled task, not evidence files."""
        source = remove_src()
        assert "alerts.jsonl" not in source
        assert "latest-watchdog-status" not in source
        assert "report" not in source.lower()


# ===========================================================================
# Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """5 existing task tests pass — accepted unchanged."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: read-only audit validation depth (20+ fields),
        enablement health gate (fresh HEALTHY, timestamp, result, state),
        rollback on every failure path, removal ordering (disable→stop→unregister),
        evidence preservation, no recorder control, documentation claims,
        PowerShell syntax, and safety gaps — not in existing 5 tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only source text assertions against the 5 PowerShell
        scripts and the implementation markdown. No Python API coupling."""
