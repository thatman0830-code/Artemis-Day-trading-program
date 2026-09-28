#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$name='NinjaTrader ES-NQ Canonical Smoke Evidence'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner=Join-Path $repository 'scripts\run_ninjatrader_canonical_smoke_task.ps1'
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
if(Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue){throw 'Exact canonical smoke task already exists.'}
$exe="$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments="-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`""
$action=New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -Once -At ([DateTime]::Now.AddMinutes(1)) -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Periodic deterministic ES/NQ canonical smoke evidence; advisory only, no trading authority.'|Out-Null
Start-ScheduledTask -TaskName $name -TaskPath '\'
Write-Output 'NINJATRADER_CANONICAL_SMOKE_TASK_INSTALLED_AND_STARTED'
