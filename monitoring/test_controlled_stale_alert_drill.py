from pathlib import Path

SOURCE=(Path(__file__).parents[1]/"scripts"/"invoke_controlled_stale_alert_drill.ps1").read_text("utf-8")


def test_preflight_is_default_and_exits_before_recorder_control():
    assert "[switch] $Execute" in SOURCE and "PREFLIGHT_ONLY" in SOURCE
    assert SOURCE.index("if(-not$Execute)") < SOURCE.index("Stop-ScheduledTask")


def test_only_btc_is_stopped_and_started():
    lines=[line for line in SOURCE.splitlines() if "Stop-ScheduledTask" in line or "Start-ScheduledTask" in line]
    assert lines and all("$btcName" in line for line in lines)
    assert all("$esName" not in line for line in lines)


def test_stale_interval_and_recovery_are_bounded():
    assert "[ValidateRange(91, 180)]" in SOURCE
    assert "[ValidateRange(60, 600)]" in SOURCE
    assert "Start-Sleep -Seconds $StaleHoldSeconds" in SOURCE
    assert "$postTime-le$pollTime" in SOURCE


def test_real_watchdog_transitions_are_required():
    assert SOURCE.count("& $watchdogRunner") == 2
    assert "STALE_HEARTBEAT|TASK_NOT_RUNNING" in SOURCE
    assert "recovered.state-ne'HEALTHY'" in SOURCE


def test_both_alert_transitions_require_onedrive_envelopes():
    assert SOURCE.count("& $deliveryRunner") == 2
    assert "Unhealthy alert is absent from OneDrive inbox" in SOURCE
    assert "Recovery alert is absent from OneDrive inbox" in SOURCE
    assert "unhealthy_envelope_sha256" in SOURCE and "healthy_envelope_sha256" in SOURCE


def test_es_nq_and_gap_counts_must_remain_unchanged():
    assert "ES/NQ changed during BTC stale drill" in SOURCE
    assert "$gapPost-ne$gapPre" in SOURCE
    assert "es_nq_collector_operated=$false" in SOURCE


def test_failure_attempts_btc_recovery_and_writes_evidence():
    failure=SOURCE[SOURCE.index("}catch{"):]
    assert "DRILL_FAILED" in failure and "Start-ScheduledTask -TaskName $btcName" in failure
    assert "Write-Report $report" in failure and "throw" in failure


def test_no_trading_or_sensitive_control_surface():
    assert "trading_authority=$false" in SOURCE
    for value in ("credential.dpapi","ConvertTo-SecureString","private_key","api_key",
                  "place_order","submit_live","wallet","broker","exchange"):
        assert value not in SOURCE
