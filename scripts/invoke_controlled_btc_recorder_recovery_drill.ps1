#requires -Version 5.1
[CmdletBinding()]
param(
    [switch] $Execute,
    [ValidateRange(60, 600)] [int] $RecoveryTimeoutSeconds = 180,
    [string] $OutputPath
)

$ErrorActionPreference = 'Stop'
$btcTaskName = 'BTC Public Candle Research Recorder'
$esTaskName = 'ES-NQ Delayed Daily Research Collector'
$taskPath = '\'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$btcRunner = Join-Path $repository 'scripts\run_btc_forward_recorder_task.ps1'
$eventPath = Join-Path $repository 'outputs\recorder_health\btc_forward_archive_2\recorder-events.jsonl'
$manifestPath = Join-Path $repository 'data\backtests\btc_forward_archive_2\archive_manifest.json'
$esOutput = Join-Path $repository 'outputs\futures_forward'
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
    $OutputPath = Join-Path $repository 'outputs\operational_drills\btc-recorder-recovery-latest.json'
} elseif (-not [IO.Path]::IsPathRooted($OutputPath)) {
    $OutputPath = Join-Path $repository $OutputPath
}
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if (-not $OutputPath.StartsWith($repository + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Recovery evidence path must remain inside the repository.'
}

function Get-Sha256([string] $Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required evidence is missing: $Path" }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Get-LatestHealthyPoll {
    if (-not (Test-Path -LiteralPath $eventPath -PathType Leaf)) { return $null }
    return Get-Content -LiteralPath $eventPath -Tail 100 |
        ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object { $_.event -eq 'poll_complete' -and $_.state -eq 'RECORDING' -and $_.symbol -eq 'BTC' } |
        Select-Object -Last 1
}
function Get-GapCount {
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.state -ne 'RECORDING' -or -not $manifest.streams) {
        throw 'BTC archive manifest is not in RECORDING state.'
    }
    $total = 0
    foreach ($stream in $manifest.streams.PSObject.Properties) { $total += [int]$stream.Value.gap_count }
    return $total
}
function Get-TaskEvidence([string] $Name) {
    $task = Get-ScheduledTask -TaskName $Name -TaskPath $taskPath -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName $Name -TaskPath $taskPath -ErrorAction Stop
    return [ordered]@{
        state = [string]$task.State
        last_result = [int]$info.LastTaskResult
        last_run_utc = $(if ($info.LastRunTime -and $info.LastRunTime.Year -gt 1900) {
            $info.LastRunTime.ToUniversalTime().ToString('o')
        } else { $null })
        next_run_utc = $(if ($info.NextRunTime -and $info.NextRunTime.Year -gt 1900) {
            $info.NextRunTime.ToUniversalTime().ToString('o')
        } else { $null })
        missed_runs = [int]$info.NumberOfMissedRuns
    }
}
function Write-Report([hashtable] $Value) {
    $parent = Split-Path -Parent $OutputPath
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $core = [ordered]@{}
    foreach ($key in $Value.Keys) { $core[$key] = $Value[$key] }
    $json = $core | ConvertTo-Json -Depth 8 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($json)
    $identity = [Security.Cryptography.SHA256]::Create().ComputeHash($bytes)
    $core['report_id'] = ([BitConverter]::ToString($identity)).Replace('-', '').ToLowerInvariant()
    $temporary = "$OutputPath.tmp-$([Guid]::NewGuid().ToString('N'))"
    try {
        [IO.File]::WriteAllText($temporary, ($core | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        Move-Item -LiteralPath $temporary -Destination $OutputPath -Force
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
    }
}

$btcTask = Get-ScheduledTask -TaskName $btcTaskName -TaskPath $taskPath -ErrorAction Stop
$esTask = Get-ScheduledTask -TaskName $esTaskName -TaskPath $taskPath -ErrorAction Stop
$btcInfo = Get-ScheduledTaskInfo -TaskName $btcTaskName -TaskPath $taskPath -ErrorAction Stop
$esInfo = Get-ScheduledTaskInfo -TaskName $esTaskName -TaskPath $taskPath -ErrorAction Stop
$actions = @($btcTask.Actions)
if ($actions.Count -ne 1 -or @($esTask.Actions).Count -ne 1) { throw 'Recorder task action boundary mismatch.' }
$expectedArguments = "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$btcRunner`""
if ([string]$btcTask.State -ne 'Running' -or $actions[0].Arguments -ne $expectedArguments -or
        $actions[0].WorkingDirectory -ne $repository -or [string]$btcTask.Settings.MultipleInstances -ne 'IgnoreNew') {
    throw 'BTC recorder is not in the exact safe running configuration.'
}
if ([string]$esTask.State -ne 'Ready' -or $esInfo.LastTaskResult -ne 0 -or $esInfo.NumberOfMissedRuns -ne 0) {
    throw 'ES/NQ daily collector is not in the required unchanged healthy state.'
}
$prePoll = Get-LatestHealthyPoll
if (-not $prePoll) { throw 'BTC recorder has no healthy completed poll.' }
$prePollTime = ([DateTimeOffset]$prePoll.timestamp).ToUniversalTime()
if (([DateTimeOffset]::UtcNow - $prePollTime).TotalSeconds -gt 90) { throw 'BTC recorder heartbeat is stale.' }
$latestEsRun = Get-ChildItem -LiteralPath $esOutput -Filter 'run-*.json' |
    Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
if (-not $latestEsRun) { throw 'ES/NQ run evidence is missing.' }
$esRun = Get-Content -LiteralPath $latestEsRun.FullName -Raw | ConvertFrom-Json
if ($esRun.state -ne 'HEALTHY' -or $esRun.trading -ne $false) { throw 'ES/NQ run evidence is not healthy.' }
$preBtc = Get-TaskEvidence $btcTaskName
$preEs = Get-TaskEvidence $esTaskName
$preManifestSha = Get-Sha256 $manifestPath
$preGapCount = Get-GapCount
$preEsSha = Get-Sha256 $latestEsRun.FullName
$startedAt = [DateTimeOffset]::UtcNow
$report = [ordered]@{
    schema_version = 'controlled-btc-recorder-recovery-drill-v1'
    started_at = $startedAt.ToString('o')
    completed_at = $null
    mode = $(if ($Execute) { 'EXECUTE' } else { 'PREFLIGHT_ONLY' })
    result = 'PREFLIGHT_VERIFIED'
    btc_pre = $preBtc
    btc_pre_poll_utc = $prePollTime.ToString('o')
    btc_pre_manifest_sha256 = $preManifestSha
    btc_pre_gap_count = $preGapCount
    es_nq_pre = $preEs
    es_nq_run_sha256 = $preEsSha
    stop_observed = $false
    fresh_post_restart_poll_observed = $false
    recovery_seconds = $null
    physical_recorder_restart_claimed = $false
    es_nq_collector_operated = $false
    trading_authority = $false
}
if (-not $Execute) {
    $report.completed_at = [DateTimeOffset]::UtcNow.ToString('o')
    Write-Report $report
    Write-Output "BTC_RECORDER_RECOVERY_PREFLIGHT_VERIFIED:$OutputPath"
    exit 0
}

$stopIssued = $false
try {
    Stop-ScheduledTask -TaskName $btcTaskName -TaskPath $taskPath -ErrorAction Stop
    $stopIssued = $true
    $stopDeadline = [DateTimeOffset]::UtcNow.AddSeconds(30)
    do {
        Start-Sleep -Milliseconds 500
        $state = [string](Get-ScheduledTask -TaskName $btcTaskName -TaskPath $taskPath).State
    } while ($state -eq 'Running' -and [DateTimeOffset]::UtcNow -lt $stopDeadline)
    if ($state -eq 'Running') { throw 'BTC task did not stop within the bounded interval.' }
    $report.stop_observed = $true
    Start-ScheduledTask -TaskName $btcTaskName -TaskPath $taskPath -ErrorAction Stop
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($RecoveryTimeoutSeconds)
    $postPoll = $null
    do {
        Start-Sleep -Seconds 2
        $postPoll = Get-LatestHealthyPoll
        $postTime = if ($postPoll) { ([DateTimeOffset]$postPoll.timestamp).ToUniversalTime() } else { $null }
        $btcState = [string](Get-ScheduledTask -TaskName $btcTaskName -TaskPath $taskPath).State
    } while (($btcState -ne 'Running' -or -not $postTime -or $postTime -le $prePollTime) -and
             [DateTimeOffset]::UtcNow -lt $deadline)
    if ($btcState -ne 'Running' -or -not $postTime -or $postTime -le $prePollTime) {
        throw 'BTC recorder did not produce a fresh healthy poll before the recovery deadline.'
    }
    $postEs = Get-TaskEvidence $esTaskName
    if ($postEs.state -ne $preEs.state -or $postEs.last_result -ne $preEs.last_result -or
            $postEs.last_run_utc -ne $preEs.last_run_utc -or (Get-Sha256 $latestEsRun.FullName) -ne $preEsSha) {
        throw 'ES/NQ collector changed during the BTC-only recovery drill.'
    }
    $postGapCount = Get-GapCount
    if ($postGapCount -ne $preGapCount) { throw 'BTC unresolved gap count changed during recovery.' }
    $report.result = 'RECOVERY_VERIFIED'
    $report.fresh_post_restart_poll_observed = $true
    $report.recovery_seconds = [Math]::Round(([DateTimeOffset]::UtcNow - $startedAt).TotalSeconds, 3)
    $report.btc_post = Get-TaskEvidence $btcTaskName
    $report.btc_post_poll_utc = $postTime.ToString('o')
    $report.btc_post_manifest_sha256 = Get-Sha256 $manifestPath
    $report.btc_post_gap_count = $postGapCount
    $report.es_nq_post = $postEs
    $report.physical_recorder_restart_claimed = $true
} catch {
    $report.result = 'RECOVERY_FAILED'
    $report.failure_reason = $_.Exception.Message
    if ($stopIssued) {
        try { Start-ScheduledTask -TaskName $btcTaskName -TaskPath $taskPath -ErrorAction Stop }
        catch { $report.automatic_recovery_error = $_.Exception.Message }
    }
    $report.completed_at = [DateTimeOffset]::UtcNow.ToString('o')
    Write-Report $report
    throw
}
$report.completed_at = [DateTimeOffset]::UtcNow.ToString('o')
Write-Report $report
Write-Output "BTC_RECORDER_RECOVERY_VERIFIED:$OutputPath"
