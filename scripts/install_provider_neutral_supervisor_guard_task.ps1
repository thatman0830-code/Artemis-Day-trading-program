#requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$taskName='Provider-Neutral Supervisor Guard'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner=Join-Path $repository 'scripts\guard_provider_neutral_supervisor.ps1'
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
if(-not(Test-Path $runner -PathType Leaf)){throw 'Supervisor guard script is missing.'}
$existing=Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
if($existing){throw 'Exact provider-neutral supervisor guard task already exists.'}
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -Once -At ([DateTime]::Now.AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task=New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Provider-neutral paper supervisor continuity guard. No live or trading authority.'
Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject $task | Out-Null
Write-Output 'PROVIDER_NEUTRAL_SUPERVISOR_GUARD_TASK_INSTALLED'
