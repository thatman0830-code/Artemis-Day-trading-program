#requires -Version 5.1
[CmdletBinding()]
param([Parameter(Mandatory)] [string] $OutputPath)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$OutputPath = if ([IO.Path]::IsPathRooted($OutputPath)) {
    [IO.Path]::GetFullPath($OutputPath)
} else {
    [IO.Path]::GetFullPath((Join-Path $repository $OutputPath))
}
$outputParent = Split-Path -Parent $OutputPath
if ($outputParent) { New-Item -ItemType Directory -Path $outputParent -Force | Out-Null }
$collectedAt = [DateTime]::UtcNow

function Get-Sha256([string] $Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    $stream=[IO.File]::OpenRead($Path)
    $algorithm=[Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant()
    } finally {
        $algorithm.Dispose();$stream.Dispose()
    }
}
function Get-WindowsTimeEvidence([string] $RawOutputPath) {
    $tool = Join-Path $env:SystemRoot 'System32\w32tm.exe'
    $lines = @(& $tool /query /status /verbose 2>&1)
    if ($LASTEXITCODE -ne 0 -or -not $lines) { throw 'Windows Time status query failed.' }
    $raw = ($lines -join [Environment]::NewLine) + [Environment]::NewLine
    [IO.File]::WriteAllText($RawOutputPath, $raw, [Text.UTF8Encoding]::new($false))
    $source = [regex]::Match($raw, '(?im)^Source:\s*(.+?)\s*$')
    $leap = [regex]::Match($raw, '(?im)^Leap Indicator:\s*(\d+)')
    $stratum = [regex]::Match($raw, '(?im)^Stratum:\s*(\d+)')
    $phase = [regex]::Match($raw, '(?im)^Phase Offset:\s*([+-]?[0-9]+(?:\.[0-9]+)?)s?\s*$')
    $last = [regex]::Match($raw, '(?im)^Last Successful Sync Time:\s*(.+?)\s*$')
    if (-not ($source.Success -and $leap.Success -and $stratum.Success -and $phase.Success -and $last.Success)) {
        throw 'Windows Time status fields are incomplete or unsupported.'
    }
    $sourceText=$source.Groups[1].Value.Trim();$leapValue=[int]$leap.Groups[1].Value;$stratumValue=[int]$stratum.Groups[1].Value
    $phaseValue=[Math]::Abs([double]::Parse($phase.Groups[1].Value,[Globalization.CultureInfo]::InvariantCulture))
    $invalidSource = $sourceText -match '(?i)local cmos clock|free-running'
    if ($invalidSource -or ($leapValue -ne 0) -or ($stratumValue -lt 1) -or ($stratumValue -gt 15)) {
        throw 'Windows Time status is not synchronized to an eligible source.'
    }
    $lastSync=[DateTime]::MinValue
    if (-not [DateTime]::TryParse($last.Groups[1].Value,[Globalization.CultureInfo]::CurrentCulture,
            [Globalization.DateTimeStyles]::AssumeLocal,[ref]$lastSync)) {
        throw 'Windows Time has no parseable successful synchronization timestamp.'
    }
    $lastSync=$lastSync.ToUniversalTime();$invalidAge=([DateTime]::UtcNow-$lastSync).TotalHours -gt 24;$futureSync=$lastSync -gt [DateTime]::UtcNow.AddMinutes(1)
    if ($invalidAge -or $futureSync) { throw 'Windows Time synchronization timestamp is stale or future-dated.' }
    return [ordered]@{clock_skew_seconds=[int][Math]::Ceiling($phaseValue);raw_sha256=(Get-Sha256 $RawOutputPath)}
}
function Get-RestartSeconds($Settings) {
    $raw = [string]$Settings.RestartInterval
    if ([string]::IsNullOrWhiteSpace($raw)) { return 0 }
    try { return [int][Math]::Round(([Xml.XmlConvert]::ToTimeSpan($raw)).TotalSeconds) }
    catch { throw "Unsupported scheduled-task restart interval: $raw" }
}
function Get-ActionScript([string] $Arguments) {
    $match = [regex]::Match($Arguments, '(?i)(?:^|\s)-File\s+(?:"([^"]+)"|(\S+))')
    if (-not $match.Success) { return '' }
    return $(if ($match.Groups[1].Success) { $match.Groups[1].Value } else { $match.Groups[2].Value })
}
function Get-ScriptInstanceCount([string] $ScriptPath) {
    try {
        return @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
                Where-Object { $_.CommandLine -and $_.CommandLine.IndexOf($ScriptPath, [StringComparison]::OrdinalIgnoreCase) -ge 0 }
        ).Count
    } catch { return 0 }
}
function Get-TaskFacts([string] $Name) {
    $task = Get-ScheduledTask -TaskName $Name -TaskPath '\' -ErrorAction SilentlyContinue
    if (-not $task) { throw "Owner-context scheduled task is not visible: $Name" }
    $info = Get-ScheduledTaskInfo -TaskName $Name -TaskPath '\' -ErrorAction Stop
    $actions = @($task.Actions)
    if ($actions.Count -ne 1) { throw "Expected exactly one action for task: $Name" }
    $action = $actions[0]
    $script = Get-ActionScript ([string]$action.Arguments)
    if ([string]::IsNullOrWhiteSpace($script)) { throw "Task action has no unambiguous -File script: $Name" }
    return [ordered]@{
        installed = $true; name = [string]$task.TaskName; path = [string]$task.TaskPath
        executable = [string]$action.Execute; script = $script; state = [string]$task.State
        # Task Scheduler result codes are unsigned 32-bit values. Values with
        # the high bit set overflow PowerShell's signed Int32 conversion.
        last_result = [int64]$info.LastTaskResult; multiple_instances = [string]$task.Settings.MultipleInstances
        restart_policy_count = [int]$task.Settings.RestartCount
        restart_interval_seconds = Get-RestartSeconds $task.Settings
        instance_count = Get-ScriptInstanceCount $script
    }
}
function Test-BtcIntegrity([string] $ManifestPath) {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) { return $false }
    for ($attempt=0; $attempt -lt 5; $attempt++) {
        try {
            $before = Get-Sha256 $ManifestPath
            $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
            $checksums = if($manifest.archive_checksums){$manifest.archive_checksums}else{$manifest.checksums}
            if ($manifest.state -ne 'RECORDING' -or -not $checksums -or
                $manifest.trading_authority -ne $false) { return $false }
            $matches = $true
            foreach ($property in $checksums.PSObject.Properties) {
                $target = Join-Path (Split-Path $ManifestPath) $property.Name
                if ((Get-Sha256 $target) -ne ([string]$property.Value).ToLowerInvariant()) { $matches=$false;break }
            }
            $after = Get-Sha256 $ManifestPath
            if ($matches -and $before -eq $after) { return $true }
        } catch {
            # An active atomic rotation may briefly invalidate a snapshot; retry.
        }
        Start-Sleep -Milliseconds 100
    }
    return $false
}

$btcTask = Get-TaskFacts 'BTC Public Candle Research Recorder'
$esTask = Get-TaskFacts 'NinjaTrader MES-NQ Closed Bar Recorder'
$btcManifest = Join-Path $repository 'data\backtests\btc_forward_archive_2\archive_manifest.json'
$btcManifestObject = if (Test-Path -LiteralPath $btcManifest) { Get-Content $btcManifest -Raw | ConvertFrom-Json } else { $null }
$btcGaps = 0
if ($btcManifestObject -and $btcManifestObject.streams) {
    foreach ($stream in $btcManifestObject.streams.PSObject.Properties) { $btcGaps += [int]$stream.Value.gap_count }
}
$bridgeRoot = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'HermesBarBridge'
$closedBarRoot = Join-Path $repository 'data\ninjatrader_closed_bars'
$drive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$((Get-Item $repository).PSDrive.Name):'" -ErrorAction Stop
$freeBytes = [int64]$drive.FreeSpace
# No external time assertion is inferred. Absence deliberately fails the clock-skew gate.
$clockRawPath = "$OutputPath.clock-status.txt"
$clockEvidence = Get-WindowsTimeEvidence $clockRawPath
$clockSkew = $clockEvidence.clock_skew_seconds
$python = Join-Path $repository '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository Python runtime is missing.' }
Push-Location $repository
try { $esAuditLines = @(& $python -m monitoring.ninjatrader_recorder_health --archive-root $closedBarRoot --bridge-root $bridgeRoot 2>&1) }
finally { Pop-Location }
if ($LASTEXITCODE -ne 0 -or -not $esAuditLines) { throw 'NinjaTrader MES/NQ recorder health audit failed.' }
$esAuditRaw = $esAuditLines -join [Environment]::NewLine
try { $esAudit = $esAuditRaw | ConvertFrom-Json } catch { throw 'ES/NQ archive integrity output is malformed.' }
if ($esAudit.state -ne 'HEALTHY' -or $esAudit.trading_authority -ne $false) { throw 'NinjaTrader MES/NQ recorder health is not verified.' }
$esAuditPath = "$OutputPath.es-nq-integrity.json"
[IO.File]::WriteAllText($esAuditPath, $esAuditRaw + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))

$btcHashes = @((Get-Sha256 $btcManifest), $clockEvidence.raw_sha256)
if($btcManifestObject -and $btcManifestObject.archive_checksums){
    $btcHashes += @($btcManifestObject.archive_checksums.PSObject.Properties | ForEach-Object {$_.Value})
}
$btcHashes = @($btcHashes | Where-Object { $_ })
$esHashes = @($esAudit.source_file_sha256) + @($clockEvidence.raw_sha256, (Get-Sha256 $esAuditPath)) | Where-Object { $_ }
if (-not $btcHashes -or -not $esHashes) { throw 'Required recorder evidence files are missing.' }
# Timestamp the completed snapshot after every source has been observed. Capturing
# this before a multi-second audit can make its heartbeat follow collection time.
$collectedAt = [DateTime]::UtcNow
$facts = [ordered]@{
    schema_version = 'owner-context-health-facts-v1'; collected_at = $collectedAt.ToString('o')
    visibility_scope = 'OWNER_CONTEXT'; trading_authority = $false
    components = @(
        [ordered]@{
            component='btc-recorder'; collected_at=$collectedAt.ToString('o'); source_file_sha256=@($btcHashes)
            task_installed=$btcTask.installed; task_name=$btcTask.name; task_path=$btcTask.path
            executable_path=$btcTask.executable; script_path=$btcTask.script; task_state=$btcTask.state
            last_result=$btcTask.last_result; single_instance_policy=$btcTask.multiple_instances
            instance_count=$btcTask.instance_count; restart_count=0; restart_budget_exhausted=$false
            restart_policy_count=$btcTask.restart_policy_count; restart_interval_seconds=$btcTask.restart_interval_seconds
            latest_heartbeat_at=$(if($btcManifestObject){([DateTimeOffset]$btcManifestObject.updated_at).UtcDateTime.ToString('o')}else{$null})
            unresolved_gap_count=$btcGaps; archive_integrity_verified=(Test-BtcIntegrity $btcManifest)
            free_bytes=$freeBytes; clock_skew_seconds=$clockSkew; incident_facts=@(); trading_authority=$false
        },
        [ordered]@{
            component='es-nq-recorder'; collected_at=$collectedAt.ToString('o'); source_file_sha256=@($esHashes)
            task_installed=$esTask.installed; task_name=$esTask.name; task_path=$esTask.path
            executable_path=$esTask.executable; script_path=$esTask.script; task_state=$esTask.state
            last_result=$esTask.last_result; single_instance_policy=$esTask.multiple_instances
            instance_count=$esTask.instance_count; restart_count=0; restart_budget_exhausted=$false
            restart_policy_count=$esTask.restart_policy_count; restart_interval_seconds=$esTask.restart_interval_seconds
            latest_heartbeat_at=$collectedAt.ToString('o')
            # The recorder run state describes collection execution, not archive completeness.
            # Preserve the independent verifier's exact gap count so a HEALTHY run cannot
            # mask missing eligible aggregate minutes.
            unresolved_gap_count=[int]$esAudit.unresolved_gap_count
            archive_integrity_verified=$true
            free_bytes=$freeBytes; clock_skew_seconds=$clockSkew; incident_facts=@(); trading_authority=$false
        }
    )
}
$temp = "$OutputPath.tmp-$([Guid]::NewGuid().ToString('N'))"
$backup = "$OutputPath.backup-$([Guid]::NewGuid().ToString('N'))"
try {
    [IO.File]::WriteAllText($temp, ($facts | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $OutputPath -PathType Leaf) {
        [IO.File]::Replace($temp, $OutputPath, $backup)
    } else {
        Move-Item -LiteralPath $temp -Destination $OutputPath
    }
} finally {
    if ([IO.File]::Exists($temp)) {
        [IO.File]::Delete($temp)
    }
    if ([IO.File]::Exists($backup)) {
        [IO.File]::Delete($backup)
    }
}
Write-Output "OWNER_CONTEXT_FACTS_WRITTEN:$OutputPath"
