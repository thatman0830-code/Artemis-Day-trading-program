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
    assert "ES-NQ Delayed Daily Research Collector" in text
    assert "Expected exactly one action" in text
    assert "Get-ActionScript" in text


def test_collector_hashes_sources_and_verifies_btc_archive_content():
    text = source()
    assert "Get-FileHash" in text and "Test-BtcIntegrity" in text
    assert "manifest.checksums" in text
    assert "source_file_sha256" in text


def test_clock_and_es_integrity_are_derived_from_read_only_verifiers():
    text = source()
    assert "w32tm.exe" in text and "/query /status /verbose" in text
    assert "local cmos clock" in text.lower() and "Last Successful Sync Time" in text
    assert "DateTime]::TryParse" in text and "no parseable successful synchronization timestamp" in text
    assert text.index("not synchronized to an eligible source") < text.index("DateTime]::TryParse")
    assert "VerifiedClockSkewSeconds" not in text
    assert "futures_data.forward_archive_integrity" in text
    assert "esAudit.state -ne 'VERIFIED'" in text
    assert "archive_integrity_verified=$true" in text


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
