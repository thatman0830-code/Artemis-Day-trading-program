#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
$collector = Join-Path $repository 'scripts\collect_owner_context_health_facts.ps1'
$output = Join-Path $repository 'outputs\operational_health\watchdog'
$facts = Join-Path $output 'owner-context-facts.json'
$alerts = Join-Path $output 'alerts.jsonl'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository Python runtime is missing.' }

function Get-LatestAlert {
    if (-not (Test-Path -LiteralPath $alerts -PathType Leaf)) { return $null }
    try { return (Get-Content -LiteralPath $alerts -Tail 1 -ErrorAction Stop | ConvertFrom-Json) }
    catch { return $null }
}

function Send-LocalTransitionNotification([string]$PreviousEventId) {
    $latest = Get-LatestAlert
    if (-not $latest -or [string]$latest.event_id -eq $PreviousEventId) { return }
    $message = if ([string]$latest.state -eq 'HEALTHY') {
        'Market data recovered: recorder health is healthy. No order authority was granted.'
    } else {
        'Market data needs attention: check NinjaTrader MES/MNQ charts and recorder health. No orders were placed.'
    }
    try { & "$env:SystemRoot\System32\msg.exe" $env:USERNAME $message 2>$null | Out-Null } catch {}
}

$mutex=[Threading.Mutex]::new($false,'Global\HyperliquidOwnerContextHealthWatchdogV1')
$held=$false
try {
    $held=$mutex.WaitOne([TimeSpan]::FromSeconds(15))
    if(-not$held){throw 'Owner-context watchdog writer lock timed out.'}
    $previousAlert = Get-LatestAlert
    $previousEventId = if ($previousAlert) { [string]$previousAlert.event_id } else { '' }
    try {
        & $collector -OutputPath $facts
        if ($LASTEXITCODE -ne 0) { throw 'Owner-context fact collection failed.' }
    } catch {
        & $python -B -m monitoring.owner_context_health_watchdog --repository $repository `
            --output-dir $output --record-failure HEALTH_COLLECTION_FAILED
        Send-LocalTransitionNotification $previousEventId
        exit 1
    }
    try {
        & $python -B -m monitoring.owner_context_health_watchdog --repository $repository `
            --output-dir $output --facts $facts
        if ($LASTEXITCODE -ne 0) { throw 'Owner-context health evaluation failed.' }
    } catch {
        & $python -B -m monitoring.owner_context_health_watchdog --repository $repository `
            --output-dir $output --record-failure HEALTH_EVALUATION_FAILED
        Send-LocalTransitionNotification $previousEventId
        exit 1
    }
    Send-LocalTransitionNotification $previousEventId
    Write-Output 'OWNER_CONTEXT_HEALTH_WATCHDOG_COMPLETE'
} finally {
    if($held){$mutex.ReleaseMutex()}
    $mutex.Dispose()
}
