from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "invoke_controlled_btc_recorder_recovery_drill.ps1"
SOURCE = SCRIPT.read_text("utf-8")


def test_drill_defaults_to_non_disruptive_preflight():
    assert "[switch] $Execute" in SOURCE
    assert "if (-not $Execute)" in SOURCE
    assert "PREFLIGHT_ONLY" in SOURCE
    assert SOURCE.index("if (-not $Execute)") < SOURCE.index("Stop-ScheduledTask")


def test_exact_recorder_identity_and_btc_only_control_boundary():
    assert "BTC Public Candle Research Recorder" in SOURCE
    assert "ES-NQ Delayed Daily Research Collector" in SOURCE
    stop_lines = [line for line in SOURCE.splitlines() if "Stop-ScheduledTask" in line]
    start_lines = [line for line in SOURCE.splitlines() if "Start-ScheduledTask" in line]
    assert stop_lines and start_lines
    assert all("$btcTaskName" in line for line in stop_lines + start_lines)
    assert all("$esTaskName" not in line for line in stop_lines + start_lines)


def test_preflight_requires_fresh_btc_and_healthy_unchanged_es_nq():
    assert "prePollTime).TotalSeconds -gt 90" in SOURCE
    assert "$esInfo.LastTaskResult -ne 0" in SOURCE
    assert "$esInfo.NumberOfMissedRuns -ne 0" in SOURCE
    assert "ES/NQ collector changed during the BTC-only recovery drill" in SOURCE


def test_recovery_is_bounded_and_requires_new_poll_without_new_gaps():
    assert "[ValidateRange(60, 600)]" in SOURCE
    assert "$postTime -le $prePollTime" in SOURCE
    assert "$postGapCount -ne $preGapCount" in SOURCE
    assert "RECOVERY_VERIFIED" in SOURCE


def test_failure_attempts_recovery_and_retains_fail_closed_evidence():
    catch = SOURCE[SOURCE.index("} catch {"):]
    assert "RECOVERY_FAILED" in catch
    assert "Start-ScheduledTask -TaskName $btcTaskName" in catch
    assert "Write-Report $report" in catch
    assert "throw" in catch


def test_evidence_is_repository_bounded_sanitized_and_non_trading():
    assert "Recovery evidence path must remain inside the repository" in SOURCE
    assert "report_id" in SOURCE
    assert "trading_authority = $false" in SOURCE
    assert "es_nq_collector_operated = $false" in SOURCE
    for prohibited in ("credential.dpapi", "ConvertTo-SecureString", "private_key", "api_key",
                       "place_order", "submit_live", "wallet", "broker"):
        assert prohibited not in SOURCE
