#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$taskName='ES-NQ Delayed Daily Research Collector'
$taskPath='\'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
try {
    $task=Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
    $info=Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
    $audit=[ordered]@{
        task_name=$task.TaskName;task_path=$task.TaskPath;state=[string]$task.State
        user_id=$task.Principal.UserId;logon_type=[string]$task.Principal.LogonType;run_level=[string]$task.Principal.RunLevel
        actions=@($task.Actions|ForEach-Object{[ordered]@{execute=$_.Execute;arguments=$_.Arguments;working_directory=$_.WorkingDirectory}})
        triggers=@($task.Triggers|ForEach-Object{[ordered]@{enabled=$_.Enabled;start_boundary=$_.StartBoundary;days_interval=$_.DaysInterval;repetition_interval=[string]$_.Repetition.Interval;repetition_duration=[string]$_.Repetition.Duration}})
        next_run_time=$(if($info.NextRunTime){$info.NextRunTime.ToUniversalTime().ToString('o')}else{$null})
        start_when_available=$task.Settings.StartWhenAvailable;multiple_instances=[string]$task.Settings.MultipleInstances
        execution_time_limit=[string]$task.Settings.ExecutionTimeLimit;restart_count=$task.Settings.RestartCount;restart_interval=[string]$task.Settings.RestartInterval
        allow_demand_start=$task.Settings.AllowDemandStart;disallow_start_on_batteries=$task.Settings.DisallowStartIfOnBatteries
        stop_on_batteries=$task.Settings.StopIfGoingOnBatteries;run_only_if_network_available=$task.Settings.RunOnlyIfNetworkAvailable
    }
    $path=Join-Path $repository 'outputs\futures_forward\scheduled_task_audit.json'
    [IO.File]::WriteAllText($path,($audit|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
    Write-Output 'TASK_DEFINITION_AUDITED_READ_ONLY'
}
catch {[Console]::Error.WriteLine('BLOCKED: exact ES/NQ task definition was not visible to the current Windows context.');exit 2}
