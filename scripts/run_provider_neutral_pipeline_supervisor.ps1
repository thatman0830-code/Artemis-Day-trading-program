#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(1,12)][int]$Hours = 2,
    [ValidateRange(5,50)][int]$CaptureSeconds = 50,
    [ValidateRange(1,60)][int]$PollSeconds = 5,
    [ValidateRange(1,5)][int]$MaxConsecutiveFailures = 3,
    [switch]$Once
)

$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
$capture = Join-Path $repository 'scripts\capture_databento_live_es_nq.py'
$cycle = Join-Path $repository 'scripts\run_provider_neutral_live_paper_cycle.py'
$adaptive = Join-Path $repository 'scripts\run_adaptive_confirmation_lane.py'
$ledger = Join-Path $repository 'scripts\publish_provider_neutral_decision_ledger.py'
$risk = Join-Path $repository 'scripts\publish_provider_neutral_risk_analytics.py'
$cockpit = Join-Path $repository 'scripts\publish_provider_neutral_cockpit.py'
$health = Join-Path $repository 'outputs\provider_neutral_paper_trial\pipeline-supervisor-health.json'

if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual environment is unavailable.' }
if (-not (Test-Path -LiteralPath $capture)) { throw 'Databento capture script is unavailable.' }
if (-not (Test-Path -LiteralPath $cycle)) { throw 'Paper-cycle script is unavailable.' }
if (-not (Test-Path -LiteralPath $adaptive)) { throw 'Adaptive confirmation lane is unavailable.' }
if (-not (Test-Path -LiteralPath $ledger)) { throw 'Decision ledger publisher is unavailable.' }
if (-not (Test-Path -LiteralPath $risk)) { throw 'Risk analytics publisher is unavailable.' }
if (-not (Test-Path -LiteralPath $cockpit)) { throw 'Provider-neutral cockpit publisher is unavailable.' }
# Validate the effective process environment.  Scheduled tasks and managed
# launchers may inject the key at process scope rather than User scope; the
# capture script already uses this effective environment.
if (-not $env:DATABENTO_API_KEY) { throw 'DATABENTO_API_KEY is not configured for this process.' }

$deadline = [DateTimeOffset]::UtcNow.AddHours($Hours)
$failures = 0
$lastError = $null
$healthDir = Split-Path -Parent $health
New-Item -ItemType Directory -Force -Path $healthDir | Out-Null

while ([DateTimeOffset]::UtcNow -lt $deadline) {
    try {
        $env:DATABENTO_CAPTURE_SECONDS = [string]$CaptureSeconds
        & $python $capture
        if ($LASTEXITCODE -ne 0) { throw "Databento capture exited with code $LASTEXITCODE." }

        & $python $cycle
        if ($LASTEXITCODE -ne 0) { throw "Paper-cycle heartbeat exited with code $LASTEXITCODE." }

        & $python $adaptive
        if ($LASTEXITCODE -ne 0) { throw "Adaptive confirmation lane exited with code $LASTEXITCODE." }

        & $python $ledger
        if ($LASTEXITCODE -ne 0) { throw "Decision ledger publisher exited with code $LASTEXITCODE." }

        & $python $risk
        if ($LASTEXITCODE -ne 0) { throw "Risk analytics publisher exited with code $LASTEXITCODE." }

        & $python $cockpit
        if ($LASTEXITCODE -ne 0) { throw "Provider-neutral cockpit publisher exited with code $LASTEXITCODE." }

        $failures = 0
        $lastError = $null
        $state = 'HEALTHY'
    }
    catch {
        $failures++
        $lastError = $_.Exception.Message
        $state = if ($failures -ge $MaxConsecutiveFailures) { 'STOPPED_FAIL_CLOSED' } else { 'DEGRADED_RETRYING' }
        if ($failures -ge $MaxConsecutiveFailures) {
            $doc = [ordered]@{ schema_version='provider-neutral-pipeline-supervisor-health-v1'; observed_at=[DateTimeOffset]::UtcNow.ToString('o'); state=$state; consecutive_failures=$failures; error=$lastError; trading_authority=$false }
            $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath $health -Encoding UTF8
            throw
        }
    }

    $doc = [ordered]@{ schema_version='provider-neutral-pipeline-supervisor-health-v1'; observed_at=[DateTimeOffset]::UtcNow.ToString('o'); state=$state; consecutive_failures=$failures; error=$lastError; trading_authority=$false }
    $doc | ConvertTo-Json -Compress | Set-Content -LiteralPath $health -Encoding UTF8
    if ($Once) { break }
    Start-Sleep -Seconds $PollSeconds
}

Write-Output "PROVIDER_NEUTRAL_PIPELINE_SUPERVISOR_COMPLETE:$Hours hours (once=$Once)"
