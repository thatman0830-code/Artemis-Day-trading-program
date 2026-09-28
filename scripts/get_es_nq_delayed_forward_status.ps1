#requires -Version 5.1
[CmdletBinding()]param()
$task=Get-ScheduledTask -TaskName 'ES-NQ Delayed Daily Research Collector' -ErrorAction SilentlyContinue;$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$latest=Get-ChildItem (Join-Path $repository 'outputs\futures_forward') -Filter 'run-*.json' -ErrorAction SilentlyContinue|Sort-Object LastWriteTimeUtc -Descending|Select-Object -First 1;$health=$(if($latest){(Get-Content $latest.FullName -Raw|ConvertFrom-Json).state}else{'NO_RUN'})
[pscustomobject]@{TaskState=$(if($task){$task.State}else{'NOT_INSTALLED'});Health=$health;LockPresent=(Test-Path (Join-Path $repository 'data\futures_forward.lock'));StopRequested=(Test-Path (Join-Path $repository 'data\futures_forward.stop'));DataPath=(Join-Path $repository 'data\futures_forward')}|Format-List
