#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$taskName = 'Owner Context Research Health Watchdog'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repository 'scripts\run_owner_context_health_watchdog.ps1'
$task = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction Stop
$info = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath '\' -ErrorAction Stop
if (@($task.Actions).Count -ne 1 -or @($task.Triggers).Count -ne 1) {
    throw 'Watchdog task definition must contain exactly one action and one trigger.'
}
$action = @($task.Actions)[0]; $trigger = @($task.Triggers)[0]
$expectedExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$expectedArgs = "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().Name; $ownerLeaf = $owner.Split('\')[-1]
$checks = @(
    ($task.Principal.UserId -eq $owner -or $task.Principal.UserId -eq $ownerLeaf),
    ([string]$task.Principal.LogonType -in @('Interactive','InteractiveToken')),
    ([string]$task.Principal.RunLevel -eq 'Limited'),
    ($action.Execute -eq $expectedExe), ($action.Arguments -eq $expectedArgs),
    ($action.WorkingDirectory -eq $repository),
    ([string]$task.Settings.MultipleInstances -eq 'IgnoreNew'),
    ([string]$task.Settings.ExecutionTimeLimit -eq 'PT4M'),
    ([string]$trigger.Repetition.Interval -eq 'PT5M'),
    ($task.Settings.StartWhenAvailable),
    (Test-Path -LiteralPath $runner -PathType Leaf),
    (Test-Path -LiteralPath (Join-Path $repository '.venv\Scripts\python.exe') -PathType Leaf)
)
if ($checks -contains $false) { throw 'Watchdog task safety policy rejected the installed definition.' }
[ordered]@{
    task_name=$task.TaskName; task_path=$task.TaskPath; state=[string]$task.State
    last_result=[int]$info.LastTaskResult; next_run_time=$info.NextRunTime.ToUniversalTime().ToString('o')
    owner_matches=$true; logon_type=[string]$task.Principal.LogonType
    run_level=[string]$task.Principal.RunLevel; multiple_instances=[string]$task.Settings.MultipleInstances
    execution_time_limit=[string]$task.Settings.ExecutionTimeLimit
    repetition_interval=[string]$trigger.Repetition.Interval; action_verified=$true
    trading_authority=$false
} | ConvertTo-Json -Compress
