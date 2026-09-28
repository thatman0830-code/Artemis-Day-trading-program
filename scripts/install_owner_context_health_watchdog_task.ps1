#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$taskName = 'Owner Context Research Health Watchdog'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner = Join-Path $repository 'scripts\run_owner_context_health_watchdog.ps1'
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
if (Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue) {
    throw 'Exact owner-context health watchdog task already exists.'
}
$action = New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
    -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`"" `
    -WorkingDirectory $repository
$trigger = New-ScheduledTaskTrigger -Once -At ([DateTime]::Now.AddMinutes(5)) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 4)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description 'Read-only research recorder health evaluation and local alert evidence. No trading authority.'
Register-ScheduledTask -TaskName $taskName -TaskPath '\' -InputObject $task | Out-Null
Disable-ScheduledTask -TaskName $taskName -TaskPath '\' | Out-Null
Write-Output 'OWNER_CONTEXT_HEALTH_WATCHDOG_TASK_INSTALLED_DISABLED_BY_OWNER_POLICY'
