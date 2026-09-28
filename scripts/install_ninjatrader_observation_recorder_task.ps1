#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$name='NinjaTrader MES-NQ Research Recorder';$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner=Join-Path $repository 'scripts\run_ninjatrader_observation_recorder.ps1';$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
if(Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue){throw 'Exact NinjaTrader recorder task already exists.'}
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -AtLogOn -User $user
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero)
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Read-only append-only MES/MNQ observation recorder; no trading authority.'|Out-Null
Start-ScheduledTask -TaskName $name -TaskPath '\';Write-Output 'NINJATRADER_OBSERVATION_RECORDER_INSTALLED_AND_STARTED'
