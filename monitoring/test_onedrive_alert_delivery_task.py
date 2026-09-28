from pathlib import Path

ROOT=Path(__file__).parents[1]


def source(name): return (ROOT/"scripts"/name).read_text("utf-8")


def test_installer_is_disabled_single_instance_and_bounded():
    text=source("install_onedrive_alert_delivery_task.ps1")
    assert "Owner Context OneDrive Alert Delivery" in text
    assert "RepetitionInterval (New-TimeSpan -Minutes 5)" in text
    assert "MultipleInstances IgnoreNew" in text and "ExecutionTimeLimit (New-TimeSpan -Minutes 2)" in text
    assert "RunLevel Limited" in text and "Disable-ScheduledTask" in text
    assert "No trading authority" in text


def test_audit_is_read_only_and_checks_exact_identity():
    text=source("audit_onedrive_alert_delivery_task.ps1")
    assert "exactly one action and one trigger" in text
    assert "PT2M" in text and "PT5M" in text and "IgnoreNew" in text
    assert "action_verified=$true" in text and "trading_authority=$false" in text
    for prohibited in ("Register-ScheduledTask","Unregister-ScheduledTask","Enable-ScheduledTask",
                       "Disable-ScheduledTask","Start-ScheduledTask","Stop-ScheduledTask"):
        assert prohibited not in text


def test_enablement_requires_fresh_task_success_and_complete_delivery():
    text=source("enable_and_verify_onedrive_alert_delivery_task.ps1")
    assert "state-ne'Disabled'" in text and "LastRunTime.ToUniversalTime()-ge$startedAt" in text
    assert "LastTaskResult-ne 0" in text and "monitoring.onedrive_delivery_verifier" in text
    assert "verified_count-lt 1" in text and "trading_authority-ne$false" in text
    assert "Disable-ScheduledTask" in text and "catch" in text


def test_removal_requires_identity_and_preserves_evidence():
    text=source("remove_onedrive_alert_delivery_task.ps1")
    assert "action_verified-ne$true" in text and "Unregister-ScheduledTask" in text
    assert "EVIDENCE_PRESERVED" in text and "Remove-Item" not in text
