#requires -Version 5.1
[CmdletBinding()]param([ValidateRange(30,180)][int]$TimeoutSeconds = 90)
$ErrorActionPreference = 'Stop'
$taskName = 'BTC Public Candle Research Recorder'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$eventPath = Join-Path $repository 'outputs\recorder_health\btc_forward_archive_2\recorder-events.jsonl'
$task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
if ([string]$task.State -eq 'Disabled') { throw 'BTC recorder task is disabled.' }
Start-ScheduledTask -TaskName $taskName -TaskPath '\'
$deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Seconds 3
    $latest = if (Test-Path -LiteralPath $eventPath) {
        Get-Content -LiteralPath $eventPath -Tail 30 | ForEach-Object { $_ | ConvertFrom-Json } |
            Where-Object { $_.event -eq 'poll_complete' -and $_.state -eq 'RECORDING' } |
            Select-Object -Last 1
    } else { $null }
    if ($latest -and $latest.event -eq 'poll_complete' -and $latest.state -eq 'RECORDING') {
        $age = ([DateTime]::UtcNow - ([DateTime]$latest.timestamp).ToUniversalTime()).TotalSeconds
        if ($age -le 30) { Write-Output 'BTC_TASK_STARTED_AND_HEALTHY'; exit 0 }
    }
} while ([DateTimeOffset]::UtcNow -lt $deadline)
throw 'BTC task did not produce a fresh healthy poll before timeout.'
