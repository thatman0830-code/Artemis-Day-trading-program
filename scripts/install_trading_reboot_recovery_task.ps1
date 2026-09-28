#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$name='Trading Data Reboot Recovery';$repository=(Resolve-Path(Join-Path $PSScriptRoot '..')).Path;$runner=Join-Path $repository 'scripts\run_trading_reboot_recovery.ps1';$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
if(Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue){throw 'Exact reboot-recovery task already exists.'}
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval(New-TimeSpan -Minutes 1)-ExecutionTimeLimit(New-TimeSpan -Minutes 6)
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Owner-logon recovery for public research recorders and NinjaTrader chart evidence. No order or trading authority.'|Out-Null
Start-ScheduledTask -TaskName $name -TaskPath '\'
'TRADING_REBOOT_RECOVERY_INSTALLED_AND_STARTED'
