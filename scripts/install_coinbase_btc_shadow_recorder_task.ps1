#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$name = 'Coinbase BTC Public Shadow Recorder'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repository 'scripts\run_coinbase_btc_shadow_recorder.ps1'
if(Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue){
    throw 'Exact Coinbase BTC shadow recorder task already exists.'
}
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $repository
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal `
    -Description 'Credential-free Coinbase BTC-USD public research recorder. Shadow-only; no account or order authority.' `
    -ErrorAction Stop | Out-Null
Write-Output 'COINBASE_BTC_SHADOW_TASK_INSTALLED'
