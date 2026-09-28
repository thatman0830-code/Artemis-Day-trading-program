#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$taskName = 'Owner Context Research Health Watchdog'; $taskPath = '\'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$audit = Join-Path $repository 'scripts\audit_owner_context_health_watchdog_task.ps1'
$facts = (& $audit | ConvertFrom-Json)
if ($facts.trading_authority -ne $false -or $facts.action_verified -ne $true) {
    throw 'Watchdog task identity was not verified; removal rejected.'
}
Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue | Out-Null
Stop-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction Stop
Write-Output 'OWNER_CONTEXT_HEALTH_WATCHDOG_TASK_REMOVED_EVIDENCE_PRESERVED'
