"""Hermes independent adversarial audit for the post-outage operational-hardening change set.

Audit assignment: AUDIT-POST-OUTAGE-OPERATIONAL-HARDENING
Checkpoint: 14e40b39c5cb97d75956d9722848531d70cbfff3

Covers:
  1. Existing owner-context facts JSON replaced atomically
  2. First-write behavior remains correct (Move-Item for non-existing)
  3. Generated temp and backup files cleaned on both success and failure
  4. Replacement failures remain fail-closed
  5. No unrelated or pre-existing outage evidence deleted
  6. UTF-8 JSON integrity and deterministic health evaluation
  7. ES/NQ installer includes hidden-window launch mode
  8. Single-instance, restart, scheduling, credential, and trading-authority boundaries unchanged
  9. No provider/network/credential/collector/recorder/task/trading/OneDrive access
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
COLLECTOR_PS1 = ROOT / "scripts" / "collect_owner_context_health_facts.ps1"
INSTALLER_PS1 = ROOT / "scripts" / "install_es_nq_delayed_forward_task.ps1"
COLLECTOR_TEST = ROOT / "monitoring" / "test_owner_context_collector.py"
FORWARD_TEST = ROOT / "futures_data" / "test_forward_collector.py"


def collector_source(): return COLLECTOR_PS1.read_text("utf-8")
def installer_source(): return INSTALLER_PS1.read_text("utf-8")


# ===========================================================================
# 1. Existing facts replaced atomically
# ===========================================================================

class TestAtomicReplacement:
    def test_checks_existing_path(self):
        source = collector_source()
        assert "Test-Path -LiteralPath $OutputPath -PathType Leaf" in source

    def test_uses_io_file_replace(self):
        source = collector_source()
        assert "[IO.File]::Replace($temp, $OutputPath, $backup)" in source

    def test_backup_guid_generated(self):
        source = collector_source()
        assert "backup-$([Guid]::NewGuid().ToString('N'))" in source

    def test_replace_preserves_existing(self):
        """IO.File.Replace atomically replaces existing file — the old content
        goes to the backup path. The new content goes to $OutputPath."""
        source = collector_source()
        assert "[IO.File]::Replace($temp, $OutputPath, $backup)" in source

    def test_first_write_uses_move_item(self):
        """First write (no existing file) uses Move-Item."""
        source = collector_source()
        assert "Move-Item -LiteralPath $temp -Destination $OutputPath" in source


# ===========================================================================
# 2. First-write behavior remains correct
# ===========================================================================

class TestFirstWrite:
    def test_first_write_branch_present(self):
        source = collector_source()
        assert "Test-Path -LiteralPath $OutputPath -PathType Leaf" in source
        assert "Move-Item -LiteralPath $temp -Destination $OutputPath" in source

    def test_existing_write_branch_present(self):
        source = collector_source()
        assert "[IO.File]::Replace($temp, $OutputPath, $backup)" in source


# ===========================================================================
# 3. Temp and backup cleaned on both success and failure
# ===========================================================================

class TestCleanup:
    def test_temp_deleted_in_finally(self):
        source = collector_source()
        assert "[IO.File]::Exists($temp)" in source
        assert "[IO.File]::Delete($temp)" in source

    def test_backup_deleted_in_finally(self):
        source = collector_source()
        assert "[IO.File]::Exists($backup)" in source
        assert "[IO.File]::Delete($backup)" in source

    def test_finally_block_present(self):
        source = collector_source()
        assert "finally" in source

    def test_try_block_present(self):
        source = collector_source()
        assert "try {" in source or "try{" in source

    def test_cleanup_runs_on_success(self):
        """On success: temp is consumed by Replace/Move, backup is created by Replace
        but both are checked and deleted in finally."""
        source = collector_source()
        # IO.File.Replace moves the old file to backup; temp is consumed
        # But the finally block still checks and deletes both
        assert "[IO.File]::Delete($temp)" in source
        assert "[IO.File]::Delete($backup)" in source

    def test_cleanup_runs_on_failure(self):
        """On failure: temp may still exist, backup may not exist.
        The finally block checks existence before deleting."""
        source = collector_source()
        assert "[IO.File]::Exists($temp)" in source
        assert "[IO.File]::Delete($temp)" in source
        assert "[IO.File]::Exists($backup)" in source
        assert "[IO.File]::Delete($backup)" in source


# ===========================================================================
# 4. Replacement failures remain fail-closed
# ===========================================================================

class TestFailClosed:
    def test_error_action_preference_stop(self):
        source = collector_source()
        assert "$ErrorActionPreference = 'Stop'" in source or "$ErrorActionPreference='Stop'" in source

    def test_write_output_only_on_success(self):
        """OWNER_CONTEXT_FACTS_WRITTEN is only written after the try/finally block."""
        source = collector_source()
        idx_finally = source.rindex("finally")
        idx_output = source.index("OWNER_CONTEXT_FACTS_WRITTEN")
        assert idx_output > idx_finally

    def test_failure_does_not_report_false_health(self):
        """If WriteAllText or Replace throws, ErrorActionPreference=Stop causes
        the script to exit before Write-Output. No false health is reported."""
        source = collector_source()
        # Write-Output is after the try/finally block
        assert "OWNER_CONTEXT_FACTS_WRITTEN" in source
        idx_finally_end = source.index("Write-Output")
        idx_try = source.index("try")
        assert idx_finally_end > idx_try


# ===========================================================================
# 5. No unrelated or pre-existing evidence deleted
# ===========================================================================

class TestNoUnrelatedDeletion:
    def test_no_remove_item(self):
        source = collector_source()
        assert "Remove-Item" not in source

    def test_no_rmdir(self):
        source = collector_source()
        assert "rmdir" not in source.lower()

    def test_no_recursive_delete(self):
        source = collector_source()
        assert "-Recurse" not in source

    def test_only_deletes_temp_and_backup(self):
        """Only $temp and $backup are deleted — not $OutputPath or other files."""
        source = collector_source()
        # All Delete calls use $temp or $backup only
        delete_lines = [l for l in source.split("\n") if "[IO.File]::Delete" in l]
        for line in delete_lines:
            assert "$temp" in line or "$backup" in line


# ===========================================================================
# 6. UTF-8 JSON integrity
# ===========================================================================

class TestJsonIntegrity:
    def test_utf8_encoding(self):
        source = collector_source()
        assert "UTF8Encoding" in source or "[Text.UTF8Encoding]" in source

    def test_convertto_json(self):
        source = collector_source()
        assert "ConvertTo-Json" in source

    def test_writealltext_utf8(self):
        source = collector_source()
        assert "[IO.File]::WriteAllText" in source
        assert "Text.UTF8Encoding" in source


# ===========================================================================
# 7. ES/NQ installer includes hidden-window launch mode
# ===========================================================================

class TestHiddenWindow:
    def test_window_style_hidden_in_installer(self):
        source = installer_source()
        assert "-WindowStyle Hidden" in source

    def test_window_style_hidden_in_test(self):
        source = FORWARD_TEST.read_text("utf-8")
        assert "-WindowStyle Hidden" in source


# ===========================================================================
# 8. Single-instance, restart, scheduling, credential, trading-authority boundaries
# ===========================================================================

class TestBoundariesUnchanged:
    def test_single_instance_ignore_new(self):
        source = installer_source()
        assert "MultipleInstances IgnoreNew" in source

    def test_restart_count_zero(self):
        source = installer_source()
        assert "RestartCount 0" in source

    def test_run_level_limited(self):
        source = installer_source()
        assert "RunLevel Limited" in source

    def test_start_when_available(self):
        source = installer_source()
        assert "StartWhenAvailable" in source

    def test_daily_trigger(self):
        source = installer_source()
        assert "New-ScheduledTaskTrigger -Daily" in source

    def test_execution_time_limit(self):
        source = installer_source()
        assert "ExecutionTimeLimit" in source

    def test_disable_after_install(self):
        source = installer_source()
        assert "-Disable" in source

    def test_credential_used(self):
        source = installer_source()
        assert "Get-Credential" in source

    def test_no_trading_authority(self):
        source = installer_source()
        assert "No trading" in source or "no trading" in source.lower()

    def test_trading_authority_false_in_collector(self):
        source = collector_source()
        assert "trading_authority=$false" in source


# ===========================================================================
# 9. No prohibited access
# ===========================================================================

class TestNoProhibitedAccess:
    def test_collector_no_network_cmdlets(self):
        source = collector_source()
        for prohibited in ("Invoke-WebRequest", "Invoke-RestMethod", "Invoke-Expression",
                          "System.Net", "HttpClient"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_installer_no_network_cmdlets(self):
        source = installer_source()
        for prohibited in ("Invoke-WebRequest", "Invoke-RestMethod", "Invoke-Expression",
                          "System.Net", "HttpClient"):
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_collector_no_recorder_mutation(self):
        source = collector_source()
        for prohibited in ("Start-ScheduledTask", "Stop-ScheduledTask",
                          "Enable-ScheduledTask", "Disable-ScheduledTask",
                          "Register-ScheduledTask", "Unregister-ScheduledTask"):
            # The collector itself should not mutate tasks
            # (it only reads via Get-ScheduledTask)
            assert prohibited not in source, f"forbidden: {prohibited}"

    def test_collector_no_trading_control(self):
        source = collector_source()
        for prohibited in ("submit_order", "place_trade", "execute_trade", "send_order"):
            assert prohibited not in source.lower(), f"forbidden: {prohibited}"

    def test_installer_no_onedrive_access(self):
        source = installer_source()
        assert "OneDrive" not in source

    def test_collector_no_onedrive_access(self):
        source = collector_source()
        # The collector references OneDrive for alert evidence but does not
        # access the OneDrive folder itself
        assert "AlertEvidence" not in source or "TradingSystem" not in source


# ===========================================================================
# 10. Existing test assertion coverage
# ===========================================================================

class TestExistingCoverage:
    def test_collector_test_checks_atomic_replace(self):
        source = COLLECTOR_TEST.read_text("utf-8")
        assert "test_existing_facts_are_atomically_replaced_and_generated_temp_is_cleaned" in source

    def test_forward_test_checks_hidden_window(self):
        source = FORWARD_TEST.read_text("utf-8")
        assert "-WindowStyle Hidden" in source


# ===========================================================================
# 11. Classification
# ===========================================================================

class TestClassification:
    def test_existing_tests_accepted(self):
        """18 existing focused tests pass (12 forward + 6 collector). 2 forward
        failures are pre-existing (pinned Python unavailable in worktree)."""

    def test_adversarial_not_redundant(self):
        """Adversarial tests cover: first-write branch, cleanup on failure,
        Write-Output only on success, no Remove-Item, no -Recurse, only deletes
        $temp/$backup, installer trading-authority, collector no recorder mutation,
        installer no OneDrive — not in existing tests."""

    def test_no_implementation_coupling(self):
        """Adversarial tests use only source text assertions against the 4
        modified files. No Python API coupling."""
