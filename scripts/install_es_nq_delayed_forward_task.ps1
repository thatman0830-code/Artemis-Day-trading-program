#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$taskName='ES-NQ Delayed Daily Research Collector';$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$runner=Join-Path $repository 'scripts\run_es_nq_delayed_forward_collector.ps1'
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name;$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -Daily -At '02:30';$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) -RestartCount 0 -StartWhenAvailable -Disable
$logon=Get-Credential -UserName $user -Message 'Enter the Windows owner-account password for unattended Task Scheduler logon';$password=[Net.NetworkCredential]::new('', $logon.Password).Password
try{Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -User $user -Password $password -RunLevel Limited -Description 'Research-data-only delayed ES/NQ collector. No trading or BTC control.'|Out-Null}
finally{$password=$null;$logon=$null}
Write-Output 'TASK_INSTALLED_DISABLED_BY_OWNER_POLICY';Disable-ScheduledTask -TaskName $taskName|Out-Null
