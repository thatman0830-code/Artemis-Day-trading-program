[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[A-Z0-9]+$')][string]$Symbol,
    [Parameter(Mandatory = $true)][string[]]$Timeframes,
    [ValidateSet('testnet', 'mainnet')][string]$DataNetwork = 'testnet',
    [Parameter(Mandatory = $true)][string]$Archive,
    [Parameter(Mandatory = $true)][string]$LogDirectory,
    [double]$PollSeconds = 15,
    [ValidateRange(0, 20)][int]$MaximumRestarts = 5,
    [ValidateRange(1, 300)][int]$RestartBaseSeconds = 5,
    [ValidateRange(1, 900)][int]$RestartMaximumSeconds = 120,
    [string]$SingleInstanceName,
    [switch]$ResolvePathsOnly
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
function Resolve-RepositoryPath([string]$Value) {
    if ([IO.Path]::IsPathRooted($Value)) {
        return [IO.Path]::GetFullPath($Value)
    }
    return [IO.Path]::GetFullPath((Join-Path $repo $Value))
}
$archivePath = Resolve-RepositoryPath $Archive
$logPath = Resolve-RepositoryPath $LogDirectory
if ($ResolvePathsOnly) {
    [ordered]@{ archive = $archivePath; log_directory = $logPath } |
        ConvertTo-Json -Compress
    exit 0
}
$instanceMutex = $null
if ($SingleInstanceName) {
    $createdNew = $false
    $instanceMutex = [Threading.Mutex]::new($true, $SingleInstanceName, [ref]$createdNew)
    if (-not $createdNew) {
        $instanceMutex.Dispose()
        Write-Output 'SUPERVISOR_ALREADY_RUNNING'
        exit 0
    }
}
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
$eventLog = Join-Path $logPath 'recorder-events.jsonl'
$alertLog = Join-Path $logPath 'recorder-alerts.jsonl'
$supervisorLog = Join-Path $logPath 'supervisor.jsonl'

function Write-SupervisorEvent([string]$Event, [hashtable]$Details) {
    $record = [ordered]@{
        timestamp = [DateTimeOffset]::UtcNow.ToString('o')
        event = $Event
        symbol = $Symbol
        archive = $archivePath
        details = $Details
    }
    ($record | ConvertTo-Json -Compress -Depth 4) | Add-Content -LiteralPath $supervisorLog -Encoding utf8
}

$arguments = @('-m','backtesting','record','--symbol',$Symbol,'--timeframes') +
    $Timeframes + @('--data-network',$DataNetwork,'--output',$archivePath,
    '--poll-seconds',[string]$PollSeconds,'--log-file',$eventLog,
    '--alert-file',$alertLog)
try {
    $restart = 0
    Write-SupervisorEvent 'supervisor_started' @{ maximum_restarts = $MaximumRestarts; trading = $false; single_instance = [bool]$SingleInstanceName }
    while ($true) {
        $startedAt = [DateTimeOffset]::UtcNow
        & $python @arguments
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            Write-SupervisorEvent 'recorder_stopped_cleanly' @{ exit_code = 0; restarts = $restart }
            exit 0
        }
        $healthyRuntimeSeconds = ([DateTimeOffset]::UtcNow - $startedAt).TotalSeconds
        if ($healthyRuntimeSeconds -ge 300 -and $restart -gt 0) {
            Write-SupervisorEvent 'restart_budget_recovered' @{ previous_restart_count = $restart; healthy_runtime_seconds = [Math]::Round($healthyRuntimeSeconds, 1) }
            $restart = 0
        }
        Write-SupervisorEvent 'recorder_exited_unexpectedly' @{ exit_code = $code; restart = $restart }
        if ($restart -ge $MaximumRestarts) {
            Write-SupervisorEvent 'restart_budget_exhausted' @{ exit_code = $code; restarts = $restart }
            exit $code
        }
        $delay = [Math]::Min($RestartBaseSeconds * [Math]::Pow(2, $restart), $RestartMaximumSeconds)
        $restart += 1
        Write-SupervisorEvent 'restart_scheduled' @{ delay_seconds = $delay; restart = $restart }
        Start-Sleep -Seconds $delay
    }
} finally {
    if ($instanceMutex) { $instanceMutex.ReleaseMutex(); $instanceMutex.Dispose() }
}
