from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "collect_owner_context_health_facts.ps1"


def source():
    return SCRIPT.read_text("utf-8")


def test_collector_is_explicitly_owner_read_only_and_fail_closed():
    text = source()
    assert "OWNER_CONTEXT" in text and "trading_authority = $false" in text
    assert "Owner-context scheduled task is not visible" in text
    for prohibited in ("Register-ScheduledTask", "Unregister-ScheduledTask", "Enable-ScheduledTask",
                       "Disable-ScheduledTask", "Start-ScheduledTask", "Stop-ScheduledTask",
                       "Start-Process", "Stop-Process", "Invoke-WebRequest", "Invoke-RestMethod"):
        assert prohibited not in text


def test_collector_requires_exact_tasks_and_single_actions():
    text = source()
    assert "BTC Public Candle Research Recorder" in text
    assert "btc_forward_archive_2" in text
    assert "btcManifestObject.updated_at" in text
    assert "NinjaTrader MES-NQ Closed Bar Recorder" in text
    assert "Expected exactly one action" in text
    assert "Get-ActionScript" in text


def test_collector_hashes_sources_and_verifies_btc_archive_content():
    text = source()
    assert "Security.Cryptography.SHA256" in text and "Test-BtcIntegrity" in text
    assert "[IO.File]::OpenRead" in text
    assert "manifest.archive_checksums" in text and "manifest.checksums" in text
    assert "source_file_sha256" in text
    assert "$before -eq $after" in text and "$attempt -lt 5" in text


def test_clock_and_es_integrity_are_derived_from_read_only_verifiers():
    text = source()
    assert "w32tm.exe" in text and "/query /status /verbose" in text
    assert "local cmos clock" in text.lower() and "Last Successful Sync Time" in text
    assert "DateTime]::TryParse" in text and "no parseable successful synchronization timestamp" in text
    assert text.index("not synchronized to an eligible source") < text.index("DateTime]::TryParse")
    assert "VerifiedClockSkewSeconds" not in text
    assert "monitoring.ninjatrader_recorder_health" in text
    assert "esAudit.state -ne 'HEALTHY'" in text
    assert "archive_integrity_verified=$true" in text
    assert "unresolved_gap_count=[int]$esAudit.unresolved_gap_count" in text
    assert "if($esRun -and $esRun.state -eq 'HEALTHY'){0}else{1}" not in text


def test_collection_timestamp_is_refreshed_after_integrity_audit():
    text = source()
    audit = text.index("monitoring.ninjatrader_recorder_health")
    completed_snapshot = text.index("$collectedAt = [DateTime]::UtcNow", audit)
    facts = text.index("$facts = [ordered]@{", completed_snapshot)
    assert audit < completed_snapshot < facts


def test_output_is_atomic_utf8_json_and_contains_no_secret_inputs():
    text = source()
    assert "WriteAllText" in text and "Move-Item" in text and "ConvertTo-Json" in text
    assert "[IO.Path]::IsPathRooted($OutputPath)" in text
    assert "Join-Path $repository $OutputPath" in text
    assert text.index("New-Item -ItemType Directory") < text.index("Get-WindowsTimeEvidence $clockRawPath")
    for prohibited in ("Get-Credential", "SecureString", ".env", "password", "api_key", "private_key"):
        assert prohibited.lower() not in text.lower()


def test_existing_facts_are_atomically_replaced_and_generated_temp_is_cleaned():
    text = source()
    assert "Test-Path -LiteralPath $OutputPath -PathType Leaf" in text
    assert 'backup-$([Guid]::NewGuid().ToString(\'N\'))' in text
    assert "[IO.File]::Replace($temp, $OutputPath, $backup)" in text
    assert "[IO.File]::Exists($temp)" in text
    assert "[IO.File]::Delete($temp)" in text
    assert "[IO.File]::Exists($backup)" in text
    assert "[IO.File]::Delete($backup)" in text


def test_task_result_preserves_full_windows_status_code_range():
    text = source()
    assert "last_result = [int64]$info.LastTaskResult" in text
    assert "last_result = [int]$info.LastTaskResult" not in text


def test_btc_start_verifier_does_not_issue_duplicate_start_request():
    verifier = SCRIPT.with_name("start_and_verify_btc_forward_recorder_task.ps1").read_text("utf-8")
    assert "if ([string]$task.State -ne 'Running')" in verifier
    assert verifier.index("if ([string]$task.State -ne 'Running')") < verifier.index("Start-ScheduledTask")
