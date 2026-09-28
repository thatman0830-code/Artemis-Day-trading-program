#requires -Version 5.1
$ErrorActionPreference='Stop';$name='Fixed 2R OOS Shadow Collector';$repository=(Resolve-Path(Join-Path $PSScriptRoot '..')).Path;$runner=Join-Path $repository 'scripts\run_fixed_2r_oos_shadow.ps1';$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
if(Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue){throw 'Exact task already exists.'}
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(7)) -RepetitionInterval(New-TimeSpan -Minutes 30) -RepetitionDuration(New-TimeSpan -Days 6)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit(New-TimeSpan -Minutes 25)
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Read-only pre-registered fixed-2R OOS shadow evaluation; no order or trading authority.'|Out-Null
'FIXED_2R_OOS_SHADOW_TASK_INSTALLED'
