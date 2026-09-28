from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_runner_is_read_only_fail_closed_and_records_sanitized_failures():
    text=(ROOT/"scripts"/"run_owner_context_health_watchdog.ps1").read_text("utf-8")
    assert "collect_owner_context_health_facts.ps1" in text
    assert "HEALTH_COLLECTION_FAILED" in text and "HEALTH_EVALUATION_FAILED" in text
    assert "Start-ScheduledTask" not in text and "Stop-Process" not in text
    assert "trading" not in text.lower()


def test_installer_is_single_instance_bounded_and_disabled_by_default():
    text=(ROOT/"scripts"/"install_owner_context_health_watchdog_task.ps1").read_text("utf-8")
    assert "RepetitionInterval (New-TimeSpan -Minutes 5)" in text
    assert "MultipleInstances IgnoreNew" in text
    assert "ExecutionTimeLimit (New-TimeSpan -Minutes 4)" in text
    assert "Disable-ScheduledTask" in text
    assert "No trading authority" in text


def test_audit_requires_exact_identity_and_is_read_only():
    text=(ROOT/"scripts"/"audit_owner_context_health_watchdog_task.ps1").read_text("utf-8")
    assert "exactly one action and one trigger" in text
    assert "PT5M" in text and "PT4M" in text and "IgnoreNew" in text
    assert "action_verified=$true" in text and "trading_authority=$false" in text
    for prohibited in ("Register-ScheduledTask","Unregister-ScheduledTask","Enable-ScheduledTask",
                       "Disable-ScheduledTask","Start-ScheduledTask","Stop-ScheduledTask"):
        assert prohibited not in text


def test_enablement_is_guarded_verified_and_rolls_back_to_disabled():
    text=(ROOT/"scripts"/"enable_and_verify_owner_context_health_watchdog_task.ps1").read_text("utf-8")
    assert "state -ne 'Disabled'" in text and "trading_authority -ne $false" in text
    assert "Enable-ScheduledTask" in text and "Start-ScheduledTask" in text
    assert "latest-watchdog-status.json" in text and "ready_for_unattended_operation -eq $true" in text
    assert "observed_at" in text and "LastTaskResult -eq 0" in text
    assert "Disable-ScheduledTask" in text


def test_removal_requires_identity_and_preserves_evidence():
    text=(ROOT/"scripts"/"remove_owner_context_health_watchdog_task.ps1").read_text("utf-8")
    assert "action_verified -ne $true" in text
    assert "Unregister-ScheduledTask" in text and "-Confirm:$false" in text
    assert "EVIDENCE_PRESERVED" in text
    assert "Remove-Item" not in text
