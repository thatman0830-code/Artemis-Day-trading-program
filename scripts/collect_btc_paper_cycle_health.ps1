#requires -Version 5.1
[CmdletBinding()]param([Parameter(Mandatory)][string]$OutputPath)
$ErrorActionPreference='Stop'
function Get-Sha256Hex([string]$Path){
 $stream=[IO.File]::OpenRead($Path);$algorithm=[Security.Cryptography.SHA256]::Create()
 try{return([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()}
 finally{$algorithm.Dispose();$stream.Dispose()}
}
$repository=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$OutputPath=if([IO.Path]::IsPathRooted($OutputPath)){[IO.Path]::GetFullPath($OutputPath)}else{[IO.Path]::GetFullPath((Join-Path $repository $OutputPath))}
$parent=Split-Path -Parent $OutputPath
if($parent){New-Item -ItemType Directory -Path $parent -Force|Out-Null}
$taskName='BTC Public Candle Research Recorder'
$runner=(Resolve-Path -LiteralPath (Join-Path $repository 'scripts\run_btc_forward_recorder_task.ps1')).Path
$task=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
$actions=@($task.Actions)
if($actions.Count-ne 1-or[string]$task.State-ne'Running'-or[string]$task.Settings.MultipleInstances-ne'IgnoreNew'){
    throw 'BTC task state or single-instance policy is ineligible.'
}
$scriptMatch=[regex]::Match([string]$actions[0].Arguments,'(?i)(?:^|\s)-File\s+(?:"([^"]+)"|(\S+))')
$taskScript=if($scriptMatch.Groups[1].Success){$scriptMatch.Groups[1].Value}else{$scriptMatch.Groups[2].Value}
if(-not$scriptMatch.Success-or-not([IO.Path]::GetFullPath($taskScript)-eq$runner)){throw 'BTC task action identity mismatch.'}
$instances=@(Get-CimInstance Win32_Process -ErrorAction Stop|Where-Object{$_.CommandLine-and$_.CommandLine.IndexOf($runner,[StringComparison]::OrdinalIgnoreCase)-ge 0}).Count
if($instances-ne 1){throw 'Exactly one BTC recorder supervisor process is required.'}
$eventPath=Join-Path $repository 'outputs\recorder_health\btc_forward_archive_2\recorder-events.jsonl'
if(-not[IO.File]::Exists($eventPath)){throw 'BTC recorder event log is unavailable.'}
$share=[IO.FileShare]::ReadWrite-bor[IO.FileShare]::Delete
$stream=[IO.File]::Open($eventPath,[IO.FileMode]::Open,[IO.FileAccess]::Read,$share)
try{
 $count=[Math]::Min([int64]262144,$stream.Length)
 $offset=$stream.Length-$count
 [void]$stream.Seek($offset,[IO.SeekOrigin]::Begin)
 $bytes=[byte[]]::new([int]$count)
 $read=$stream.Read($bytes,0,$bytes.Length)
 $text=[Text.UTF8Encoding]::new($false,$true).GetString($bytes,0,$read)
 $lines=@($text-split"`r?`n")
 if($offset-gt 0-and$lines.Count-gt 0){$lines=@($lines|Select-Object -Skip 1)}
 $latest=$lines|Select-Object -Last 100|Where-Object{$_}|ForEach-Object{$_|ConvertFrom-Json}|Where-Object{$_.event-eq'poll_complete'-and$_.state-eq'RECORDING'-and$_.symbol-eq'BTC'}|Select-Object -Last 1
}finally{$stream.Dispose()}
if(-not$latest){throw 'BTC recorder has no completed healthy poll.'}
$manifestPath=Join-Path $repository 'data\backtests\btc_forward_archive_2\archive_manifest.json'
$manifestBytes=[IO.File]::ReadAllBytes($manifestPath)
$manifest=([Text.UTF8Encoding]::new($false,$true).GetString($manifestBytes))|ConvertFrom-Json
$gapCount=0
if($manifest.state-ne'RECORDING'-or$manifest.symbol-ne'BTC'-or-not$manifest.streams){throw 'BTC archive manifest is ineligible.'}
foreach($stream in $manifest.streams.PSObject.Properties){$gapCount+=[int]$stream.Value.gap_count}
if($gapCount-ne 0){throw 'BTC archive has unresolved gaps.'}
$manifestSnapshotPath="$OutputPath.archive-manifest.json"
$manifestTemporary="$manifestSnapshotPath.tmp-$([Guid]::NewGuid().ToString('N'))"
try{[IO.File]::WriteAllBytes($manifestTemporary,$manifestBytes);Move-Item -LiteralPath $manifestTemporary -Destination $manifestSnapshotPath -Force}
finally{if([IO.File]::Exists($manifestTemporary)){[IO.File]::Delete($manifestTemporary)}}
$rawPath="$OutputPath.clock-status.txt"
$started=[DateTimeOffset]::UtcNow
$lines=@(& (Join-Path $env:SystemRoot 'System32\w32tm.exe') /query /status /verbose 2>&1)
$completed=[DateTimeOffset]::UtcNow
if($LASTEXITCODE-ne 0-or-not$lines){throw 'Windows Time query failed.'}
$raw=($lines-join[Environment]::NewLine)+[Environment]::NewLine
[IO.File]::WriteAllText($rawPath,$raw,[Text.UTF8Encoding]::new($false))
$document=[ordered]@{
 schema_version='btc-paper-cycle-health-facts-v1';collected_at=[DateTimeOffset]::UtcNow.ToString('o')
 task_name=$taskName;task_path='\';task_state=[string]$task.State;single_instance_policy='IgnoreNew'
 instance_count=$instances;script_path=$runner;latest_heartbeat_at=([DateTimeOffset]$latest.timestamp).ToUniversalTime().ToString('o')
 unresolved_gap_count=$gapCount;manifest_sha256=Get-Sha256Hex $manifestSnapshotPath
 clock_query_started_at=$started.ToString('o');clock_query_completed_at=$completed.ToString('o')
 clock_raw_sha256=Get-Sha256Hex $rawPath
 trading_authority=$false
}
$temporary="$OutputPath.tmp-$([Guid]::NewGuid().ToString('N'))"
try{[IO.File]::WriteAllText($temporary,($document|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false));Move-Item -LiteralPath $temporary -Destination $OutputPath -Force}
finally{if([IO.File]::Exists($temporary)){[IO.File]::Delete($temporary)}}
Write-Output "BTC_PAPER_CYCLE_HEALTH_WRITTEN:$OutputPath"
