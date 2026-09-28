#requires -Version 5.1
[CmdletBinding()]
param(
    [switch] $Execute,
    [ValidateRange(91, 180)] [int] $StaleHoldSeconds = 95,
    [ValidateRange(60, 600)] [int] $RecoveryTimeoutSeconds = 180,
    [string] $OutputPath
)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$btcName = 'BTC Public Candle Research Recorder'
$esName = 'ES-NQ Delayed Daily Research Collector'
$watchdogName = 'Owner Context Research Health Watchdog'
$deliveryName = 'Owner Context OneDrive Alert Delivery'
$taskPath = '\'
$events = Join-Path $repository 'outputs\recorder_health\btc_forward_archive_2\recorder-events.jsonl'
$manifest = Join-Path $repository 'data\backtests\btc_forward_archive_2\archive_manifest.json'
$watchdogOutput = Join-Path $repository 'outputs\operational_health\watchdog'
$alerts = Join-Path $watchdogOutput 'alerts.jsonl'
$watchdogRunner = Join-Path $repository 'scripts\run_owner_context_health_watchdog.ps1'
$deliveryRunner = Join-Path $repository 'scripts\run_onedrive_alert_delivery.ps1'
if (-not $OutputPath) { $OutputPath = Join-Path $repository 'outputs\operational_drills\stale-alert-latest.json' }
elseif (-not [IO.Path]::IsPathRooted($OutputPath)) { $OutputPath = Join-Path $repository $OutputPath }
$OutputPath = [IO.Path]::GetFullPath($OutputPath)
if (-not $OutputPath.StartsWith($repository + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) { throw 'Drill evidence must remain inside the repository.' }

function Get-TaskFact([string] $Name) {
    $task = Get-ScheduledTask -TaskName $Name -TaskPath $taskPath -ErrorAction Stop
    $info = Get-ScheduledTaskInfo -TaskName $Name -TaskPath $taskPath -ErrorAction Stop
    [ordered]@{ state=[string]$task.State; last_result=[int]$info.LastTaskResult
        last_run_utc=$(if($info.LastRunTime.Year-gt 1900){$info.LastRunTime.ToUniversalTime().ToString('o')}else{$null})
        next_run_utc=$(if($info.NextRunTime.Year-gt 1900){$info.NextRunTime.ToUniversalTime().ToString('o')}else{$null})
        missed_runs=[int]$info.NumberOfMissedRuns }
}
function Get-Poll {
    if (-not (Test-Path -LiteralPath $events -PathType Leaf)) { return $null }
    Get-Content -LiteralPath $events -Tail 100 | ForEach-Object { $_ | ConvertFrom-Json } |
        Where-Object {$_.event-eq'poll_complete'-and$_.state-eq'RECORDING'-and$_.symbol-eq'BTC'} |
        Select-Object -Last 1
}
function Get-Gaps {
    $value=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json
    if($value.state-ne'RECORDING'-or-not$value.streams){throw 'BTC manifest is not recording.'}
    $count=0;foreach($stream in $value.streams.PSObject.Properties){$count += [int]$stream.Value.gap_count};$count
}
function Get-Alerts { @((Get-Content -LiteralPath $alerts -ErrorAction Stop)|ForEach-Object{$_|ConvertFrom-Json}) }
function Get-Sha([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Get-DeliveryPath($Event,$Sink){
    $sinkManifest=Get-Content -LiteralPath (Join-Path $Sink 'sink-manifest.json') -Raw|ConvertFrom-Json
    $raw=[Text.Encoding]::ASCII.GetBytes("$($sinkManifest.sink_id):$($Event.event_id)")
    $hash=[Security.Cryptography.SHA256]::Create().ComputeHash($raw)
    $id=([BitConverter]::ToString($hash)).Replace('-','').ToLowerInvariant()
    Join-Path $Sink "inbox\$id.json"
}
function Write-Report($Value){
    $parent=Split-Path -Parent $OutputPath;New-Item -ItemType Directory -Path $parent -Force|Out-Null
    $core=[ordered]@{};foreach($key in $Value.Keys){$core[$key]=$Value[$key]}
    $raw=$core|ConvertTo-Json -Depth 8 -Compress
    $hash=[Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($raw))
    $core.report_id=([BitConverter]::ToString($hash)).Replace('-','').ToLowerInvariant()
    $temp="$OutputPath.tmp-$([Guid]::NewGuid().ToString('N'))"
    try{[IO.File]::WriteAllText($temp,($core|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false));Move-Item $temp $OutputPath -Force}
    finally{if(Test-Path $temp){Remove-Item $temp -Force}}
}

$btc=Get-ScheduledTask -TaskName $btcName -TaskPath $taskPath -ErrorAction Stop
$es=Get-ScheduledTask -TaskName $esName -TaskPath $taskPath -ErrorAction Stop
$watchdog=Get-ScheduledTask -TaskName $watchdogName -TaskPath $taskPath -ErrorAction Stop
$delivery=Get-ScheduledTask -TaskName $deliveryName -TaskPath $taskPath -ErrorAction Stop
if([string]$btc.State-ne'Running'-or[string]$es.State-ne'Ready'-or
   [string]$watchdog.State-ne'Ready'-or[string]$delivery.State-ne'Ready'){throw 'Required task state preflight failed.'}
foreach($task in @($btc,$es,$watchdog,$delivery)){
    if(@($task.Actions).Count-ne 1-or[string]$task.Settings.MultipleInstances-ne'IgnoreNew'){throw 'Task identity boundary failed.'}
}
$esPre=Get-TaskFact $esName
if($esPre.last_result-ne 0-or$esPre.missed_runs-ne 0){throw 'ES/NQ preflight failed.'}
$poll=Get-Poll;if(-not$poll){throw 'BTC healthy poll is missing.'}
$pollTime=([DateTimeOffset]$poll.timestamp).ToUniversalTime()
if(([DateTimeOffset]::UtcNow-$pollTime).TotalSeconds-gt 90){throw 'BTC is stale before drill.'}
$gapPre=Get-Gaps;if($gapPre-ne 0){throw 'BTC has unresolved gaps before drill.'}
$alertPre=(Get-Alerts).Count
$oneDrive=$env:OneDrive;if(-not$oneDrive){$oneDrive=[Environment]::GetEnvironmentVariable('OneDrive','User')}
if(-not$oneDrive){throw 'Owner OneDrive root is unavailable.'}
$sink=Join-Path $oneDrive 'TradingSystem\AlertEvidence'
if(-not(Test-Path (Join-Path $sink 'sink-manifest.json'))){throw 'Alert sink manifest is missing.'}
$report=[ordered]@{schema_version='controlled-stale-alert-drill-v1';mode=$(if($Execute){'EXECUTE'}else{'PREFLIGHT_ONLY'})
    started_at=[DateTimeOffset]::UtcNow.ToString('o');completed_at=$null;result='PREFLIGHT_VERIFIED'
    btc_pre_poll_utc=$pollTime.ToString('o');btc_pre_gap_count=$gapPre;es_nq_pre=$esPre
    stale_observed=$false;unhealthy_alert_delivered=$false;recovery_observed=$false
    healthy_alert_delivered=$false;es_nq_collector_operated=$false;trading_authority=$false}
if(-not$Execute){$report.completed_at=[DateTimeOffset]::UtcNow.ToString('o');Write-Report $report;Write-Output "STALE_ALERT_PREFLIGHT_VERIFIED:$OutputPath";exit 0}

$stopped=$false
try{
    Stop-ScheduledTask -TaskName $btcName -TaskPath $taskPath -ErrorAction Stop;$stopped=$true
    Start-Sleep -Seconds $StaleHoldSeconds
    & $watchdogRunner;if($LASTEXITCODE-ne 0){throw 'Stale watchdog evaluation failed.'}
    $status=Get-Content (Join-Path $watchdogOutput 'latest-watchdog-status.json') -Raw|ConvertFrom-Json
    $all=Get-Alerts;$new=@($all|Select-Object -Skip $alertPre);$unhealthy=$new|Select-Object -Last 1
    $reasonText=$unhealthy.reasons|ConvertTo-Json -Compress
    if($status.state-ne'UNHEALTHY'-or$unhealthy.state-ne'UNHEALTHY'-or
       $reasonText-notmatch'btc-recorder'-or$reasonText-notmatch'(STALE_HEARTBEAT|TASK_NOT_RUNNING)'){
        throw 'Expected BTC unhealthy stale transition was not observed.'
    }
    $report.stale_observed=$true;$report.unhealthy_event_id=$unhealthy.event_id
    & $deliveryRunner;if($LASTEXITCODE-ne 0){throw 'Unhealthy alert delivery failed.'}
    $unhealthyPath=Get-DeliveryPath $unhealthy $sink
    if(-not(Test-Path -LiteralPath $unhealthyPath -PathType Leaf)){throw 'Unhealthy alert is absent from OneDrive inbox.'}
    $report.unhealthy_alert_delivered=$true;$report.unhealthy_envelope_sha256=Get-Sha $unhealthyPath
    Start-ScheduledTask -TaskName $btcName -TaskPath $taskPath -ErrorAction Stop
    $deadline=[DateTimeOffset]::UtcNow.AddSeconds($RecoveryTimeoutSeconds);$post=$null
    do{Start-Sleep -Seconds 2;$post=Get-Poll;$postTime=if($post){([DateTimeOffset]$post.timestamp).ToUniversalTime()}else{$null}
       $state=[string](Get-ScheduledTask -TaskName $btcName -TaskPath $taskPath).State}
    while(($state-ne'Running'-or-not$postTime-or$postTime-le$pollTime)-and[DateTimeOffset]::UtcNow-lt$deadline)
    if($state-ne'Running'-or-not$postTime-or$postTime-le$pollTime){throw 'BTC did not recover before deadline.'}
    & $watchdogRunner;if($LASTEXITCODE-ne 0){throw 'Recovery watchdog evaluation failed.'}
    $recovered=Get-Content (Join-Path $watchdogOutput 'latest-watchdog-status.json') -Raw|ConvertFrom-Json
    $recoveryAlert=(Get-Alerts)|Select-Object -Last 1
    if($recovered.state-ne'HEALTHY'-or$recoveryAlert.state-ne'HEALTHY'){throw 'Healthy recovery transition was not observed.'}
    & $deliveryRunner;if($LASTEXITCODE-ne 0){throw 'Recovery alert delivery failed.'}
    $recoveryPath=Get-DeliveryPath $recoveryAlert $sink
    if(-not(Test-Path $recoveryPath)){throw 'Recovery alert is absent from OneDrive inbox.'}
    $esPost=Get-TaskFact $esName
    if(($esPost|ConvertTo-Json -Compress)-ne($esPre|ConvertTo-Json -Compress)){throw 'ES/NQ changed during BTC stale drill.'}
    $gapPost=Get-Gaps;if($gapPost-ne$gapPre){throw 'BTC gap count changed during stale drill.'}
    $report.result='STALE_ALERT_AND_RECOVERY_VERIFIED';$report.recovery_observed=$true
    $report.healthy_alert_delivered=$true;$report.healthy_event_id=$recoveryAlert.event_id
    $report.healthy_envelope_sha256=Get-Sha $recoveryPath;$report.btc_post_poll_utc=$postTime.ToString('o')
    $report.btc_post_gap_count=$gapPost;$report.es_nq_post=$esPost
}catch{
    $report.result='DRILL_FAILED';$report.failure_reason=$_.Exception.Message
    if($stopped){try{Start-ScheduledTask -TaskName $btcName -TaskPath $taskPath -ErrorAction Stop}catch{$report.recovery_error=$_.Exception.Message}}
    $report.completed_at=[DateTimeOffset]::UtcNow.ToString('o');Write-Report $report;throw
}
$report.completed_at=[DateTimeOffset]::UtcNow.ToString('o');Write-Report $report
Write-Output "STALE_ALERT_AND_RECOVERY_VERIFIED:$OutputPath"
