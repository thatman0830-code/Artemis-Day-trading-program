#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$taskName = 'BTC Public Candle Research Recorder'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repository 'scripts\run_btc_forward_recorder_task.ps1'
$task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
if ([string]$task.State -ne 'Disabled') { throw 'BTC task must be disabled before validation.' }
if (@($task.Actions).Count -ne 1 -or @($task.Triggers).Count -ne 1) { throw 'BTC task definition mismatch.' }
$action = @($task.Actions)[0]; $trigger = @($task.Triggers)[0]
$expectedExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$expectedArgs = "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$ownerLeaf = $owner.Split('\')[-1]
$storedLogonType = [string]$task.Principal.LogonType
$checks = @(
    ($task.Principal.UserId -eq $owner -or $task.Principal.UserId -eq $ownerLeaf),
    ($storedLogonType -eq 'Interactive' -or $storedLogonType -eq 'InteractiveToken'),
    [string]$task.Principal.RunLevel -eq 'Limited',
    $action.Execute -eq $expectedExe,
    $action.Arguments -eq $expectedArgs,
    $action.WorkingDirectory -eq $repository,
    $trigger.UserId -eq $owner,
    [string]$task.Settings.MultipleInstances -eq 'IgnoreNew',
    $task.Settings.StartWhenAvailable,
    $task.Settings.RestartCount -eq 3,
    [string]$task.Settings.ExecutionTimeLimit -eq 'PT0S',
    (Test-Path -LiteralPath (Join-Path $repository '.venv\Scripts\python.exe') -PathType Leaf),
    (Test-Path -LiteralPath $runner -PathType Leaf),
    (Test-Path -LiteralPath (Join-Path $repository 'data\backtests\btc_forward_archive_2\archive_manifest.json') -PathType Leaf)
)
if ($checks -contains $false) { throw 'BTC task safety policy rejected the installed definition.' }
Enable-ScheduledTask -TaskName $taskName -TaskPath '\' | Out-Null
Write-Output 'BTC_TASK_ENABLED_SAFE_AT_LOGON'
