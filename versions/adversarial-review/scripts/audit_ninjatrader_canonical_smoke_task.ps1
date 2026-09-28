#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$name='NinjaTrader ES-NQ Canonical Smoke Evidence'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner=Join-Path $repository 'scripts\run_ninjatrader_canonical_smoke_task.ps1'
$task=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction Stop
$info=Get-ScheduledTaskInfo -TaskName $name -TaskPath '\';$action=@($task.Actions)[0];$trigger=@($task.Triggers)[0]
$exe="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments="-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$checks=[ordered]@{action_count=(@($task.Actions).Count-eq 1);trigger_count=(@($task.Triggers).Count-eq 1);limited=([string]$task.Principal.RunLevel-eq'Limited');executable=($action.Execute-eq$exe);arguments=($action.Arguments-eq$arguments);working_directory=($action.WorkingDirectory-eq$repository);instances=([string]$task.Settings.MultipleInstances-eq'IgnoreNew');limit=([string]$task.Settings.ExecutionTimeLimit-eq'PT2M');interval=([string]$trigger.Repetition.Interval-eq'PT5M');runner=(Test-Path -LiteralPath $runner -PathType Leaf)}
if($checks.Values-contains$false){throw "Canonical smoke task safety policy rejected the definition: $($checks|ConvertTo-Json -Compress)"}
[ordered]@{task_name=$task.TaskName;state=[string]$task.State;last_result=[int64]$info.LastTaskResult;next_run_time=$info.NextRunTime.ToUniversalTime().ToString('o');repetition_interval='PT5M';action_verified=$true;trading_authority=$false}|ConvertTo-Json -Compress
