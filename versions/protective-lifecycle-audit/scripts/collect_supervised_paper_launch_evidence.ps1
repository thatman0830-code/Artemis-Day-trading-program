#requires -Version 5.1
[CmdletBinding()]param([string]$OutputPath)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if(-not$OutputPath){$OutputPath=Join-Path $repository 'outputs\paper_launch\launch-evidence-latest.json'}
$checkpoint=(& git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository rev-parse HEAD).Trim();if($LASTEXITCODE-ne 0-or-not$checkpoint){throw 'Git checkpoint is unavailable.'}
$dirty=(& git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository status --porcelain --untracked-files=all);if($LASTEXITCODE-ne 0){throw 'Git status is unavailable.'}
$clean=if($dirty){'false'}else{'true'}
$btc=Get-ScheduledTask -TaskName 'BTC Public Candle Research Recorder' -TaskPath '\' -ErrorAction Stop
$es=Get-ScheduledTask -TaskName 'ES-NQ Delayed Daily Research Collector' -TaskPath '\' -ErrorAction Stop
$esInfo=Get-ScheduledTaskInfo -TaskName $es.TaskName -TaskPath '\' -ErrorAction Stop
$python=Join-Path $repository '.venv\Scripts\python.exe';if(-not(Test-Path $python -PathType Leaf)){throw 'Repository Python runtime is unavailable.'}
& $python -B -m execution.supervised_paper_launch_evidence_collector_v1 `
  --watchdog (Join-Path $repository 'outputs\operational_health\watchdog\latest-readiness.json') `
  --recovery-drill (Join-Path $repository 'outputs\operational_drills\btc-recorder-recovery-latest.json') `
  --stale-drill (Join-Path $repository 'outputs\operational_drills\stale-alert-latest.json') `
  --checkpoint $checkpoint --repository-clean $clean --btc-task-state ([string]$btc.State) `
  --es-nq-task-state ([string]$es.State) --es-nq-last-result ([int]$esInfo.LastTaskResult) `
  --es-nq-missed-runs ([int]$esInfo.NumberOfMissedRuns) --output $OutputPath
if($LASTEXITCODE-ne 0){throw 'Supervised paper launch-evidence collection failed closed.'}
