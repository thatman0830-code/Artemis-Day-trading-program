#requires -Version 5.1
[CmdletBinding()]param([Parameter(DontShow=$true)][string]$PolicyOnlyFactsPath)
$ErrorActionPreference='Stop'
$taskName='ES-NQ Delayed Daily Research Collector';$taskPath='\';$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe';$credential='C:\Users\fjone\MassiveAuth\es-nq-forward\credential.dpapi';$factsPath=Join-Path $env:TEMP ('es-nq-enable-'+[Guid]::NewGuid().ToString('N')+'.json')
function Invoke-LocalEnablePolicy([string]$path){
 $policy=New-Object System.Diagnostics.ProcessStartInfo;$policy.FileName=$python;$policy.WorkingDirectory=$repository;$policy.UseShellExecute=$false;$policy.CreateNoWindow=$true
 $policy.RedirectStandardOutput=$true;$policy.RedirectStandardError=$true;$policy.Arguments='-m futures_data.task_enable_policy --facts "'+$path+'"'
 $policyProcess=New-Object System.Diagnostics.Process;$policyProcess.StartInfo=$policy;[void]$policyProcess.Start();$policyOutput=$policyProcess.StandardOutput.ReadToEnd();$policyError=$policyProcess.StandardError.ReadToEnd();$policyProcess.WaitForExit()
 $policyError=$null;$policyOutput=$null;return $policyProcess.ExitCode
}
try {
 if($PolicyOnlyFactsPath){if(!(Test-Path -LiteralPath $PolicyOnlyFactsPath -PathType Leaf)){throw 'Offline policy fixture is unavailable.'};if((Invoke-LocalEnablePolicy $PolicyOnlyFactsPath)-ne 0){throw 'Local enable policy rejected the task.'};Write-Output 'TASK_ENABLE_POLICY_VALIDATED_OFFLINE';exit 0}
 $task=Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop;$info=Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
 if(@($task.Actions).Count-ne 1-or @($task.Triggers).Count-ne 1){throw 'Installed task definition mismatch.'}
 $owner=[Security.Principal.WindowsIdentity]::GetCurrent().Name;$ownerLeaf=$owner.Split('\')[-1]
 $acl=$(if(Test-Path -LiteralPath $credential -PathType Leaf){Get-Acl -LiteralPath $credential}else{$null})
 $unexpected=@($(if($acl){$acl.Access|Where-Object{$_.AccessControlType-eq'Allow'-and $_.IdentityReference.Value-ne$owner}}))
 $credentialScoped=$null-ne$acl-and$unexpected.Count-eq 0-and @($acl.Access|Where-Object{$_.AccessControlType-eq'Allow'-and $_.IdentityReference.Value-eq$owner}).Count-gt 0
 $latest=Get-ChildItem (Join-Path $repository 'outputs\futures_forward') -Filter 'run-*.json'|Sort-Object LastWriteTimeUtc -Descending|Select-Object -First 1
 $health=$(if($latest){(Get-Content -LiteralPath $latest.FullName -Raw|ConvertFrom-Json).state}else{'NO_RUN'})
 $validation=New-Object System.Diagnostics.ProcessStartInfo;$validation.FileName=$python;$validation.WorkingDirectory=$repository;$validation.UseShellExecute=$false;$validation.CreateNoWindow=$true
 $validation.RedirectStandardOutput=$true;$validation.RedirectStandardError=$true;$validation.Arguments='-m futures_data.validate_forward_configuration --configuration "'+(Join-Path $repository 'config\es_nq_forward_sessions.json')+'" --repository "'+$repository+'"'
 $validationProcess=New-Object System.Diagnostics.Process;$validationProcess.StartInfo=$validation;[void]$validationProcess.Start();$validationOutput=$validationProcess.StandardOutput.ReadToEnd();$validationError=$validationProcess.StandardError.ReadToEnd();$validationProcess.WaitForExit()
 if($validationProcess.ExitCode-ne 0-or$validationOutput.Trim()-ne'FORWARD_CONFIGURATION_VALIDATED_OFFLINE'){throw 'Finalized configuration integrity rejected.'};$validationError=$null
 $action=@($task.Actions)[0];$trigger=@($task.Triggers)[0]
 $facts=[ordered]@{task_name=$task.TaskName;task_path=$task.TaskPath;state=[string]$task.State;user_id=$task.Principal.UserId;owner_matches=($task.Principal.UserId-eq$owner-or$task.Principal.UserId-eq$ownerLeaf)
  logon_type=[string]$task.Principal.LogonType;run_level=[string]$task.Principal.RunLevel;execute=$action.Execute;arguments=$action.Arguments;working_directory=$action.WorkingDirectory
  days_interval=$trigger.DaysInterval;next_run_time=$info.NextRunTime.ToUniversalTime().ToString('o');start_when_available=$task.Settings.StartWhenAvailable
  multiple_instances=[string]$task.Settings.MultipleInstances;execution_time_limit=[string]$task.Settings.ExecutionTimeLimit;restart_count=$task.Settings.RestartCount
  disallow_start_on_batteries=$task.Settings.DisallowStartIfOnBatteries;stop_on_batteries=$task.Settings.StopIfGoingOnBatteries;run_only_if_network_available=$task.Settings.RunOnlyIfNetworkAvailable
  health=$health;lock_present=(Test-Path (Join-Path $repository 'data\futures_forward.lock'));stop_requested=(Test-Path (Join-Path $repository 'data\futures_forward.stop'))
  credential_present=(Test-Path -LiteralPath $credential -PathType Leaf);credential_owner_scoped=$credentialScoped;configuration_valid=$true}
 [IO.File]::WriteAllText($factsPath,($facts|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
 if((Invoke-LocalEnablePolicy $factsPath)-ne 0){throw 'Local enable policy rejected the task.'}
 $before=$info.LastRunTime;Enable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop|Out-Null
 $afterTask=Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath;$afterInfo=Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath
 if($afterTask.State-eq'Running'-or$afterInfo.LastRunTime-ne$before){Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath|Out-Null;throw 'Task started unexpectedly and was disabled.'}
 Write-Output 'TASK_ENABLED_HEALTHY'
}
catch {[Console]::Error.WriteLine(('BLOCKED: '+$_.Exception.Message));exit 2}
finally {Remove-Item -LiteralPath $factsPath -Force -ErrorAction SilentlyContinue}
