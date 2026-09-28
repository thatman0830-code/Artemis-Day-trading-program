#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$taskName = 'Owner Context OneDrive Alert Delivery'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repository 'scripts\run_onedrive_alert_delivery.ps1'
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if (Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue) {
    throw 'Exact OneDrive alert-delivery task already exists.'
}
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $repository
$trigger = New-ScheduledTaskTrigger -Once -At ([DateTime]::Now.AddMinutes(5)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'Sanitized watchdog alert delivery to the owner OneDrive sink. No trading authority.'
Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject $task | Out-Null
Disable-ScheduledTask -TaskName $taskName -TaskPath '\' | Out-Null
Write-Output 'ONEDRIVE_ALERT_DELIVERY_TASK_INSTALLED_DISABLED_BY_OWNER_POLICY'
