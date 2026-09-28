#requires -Version 5.1
[CmdletBinding()]param([ValidateRange(30,600)][int]$FreshSeconds = 90)
$taskName = 'BTC Public Candle Research Recorder'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
$info = if ($task) { Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue } else { $null }
$eventPath = Join-Path $repository 'outputs\recorder_health\btc_forward_archive_2\recorder-events.jsonl'
$manifestPath = Join-Path $repository 'data\backtests\btc_forward_archive_2\archive_manifest.json'
$latest = if (Test-Path -LiteralPath $eventPath) {
    Get-Content -LiteralPath $eventPath -Tail 30 | ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.event -eq 'poll_complete' -and $_.state -eq 'RECORDING' } |
        Select-Object -Last 1
} else { $null }
$age = if ($latest) { ([DateTime]::UtcNow - ([DateTime]$latest.timestamp).ToUniversalTime()).TotalSeconds } else { $null }
$healthy = $latest -and $latest.event -eq 'poll_complete' -and $latest.state -eq 'RECORDING' -and $age -le $FreshSeconds
[pscustomobject]@{
    # A restricted process can receive no task object even when the exact
    # owner-context task exists. Absence is therefore not proof of removal.
    TaskState = if ($task) { [string]$task.State } else { 'UNKNOWN_OR_NOT_VISIBLE' }
    TaskVisibilityVerified = [bool]$task
    LastTaskResult = if ($info) { $info.LastTaskResult } else { $null }
    RecorderHealth = if ($healthy) { 'HEALTHY' } else { 'STALE_OR_STOPPED' }
    LatestCompletedPoll = if ($latest) { $latest.event } else { $null }
    LatestCompletedPollUtc = if ($latest) { $latest.timestamp } else { $null }
    EventAgeSeconds = if ($null -ne $age) { [Math]::Round($age,1) } else { $null }
    ManifestPresent = Test-Path -LiteralPath $manifestPath -PathType Leaf
    Trading = $false
} | Format-List
