#requires -Version 5.1
[CmdletBinding()]param([ValidateRange(30,300)][int]$TimeoutSeconds = 120)
$ErrorActionPreference = 'Stop'
$taskName = 'Owner Context Research Health Watchdog'; $taskPath = '\'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$audit = Join-Path $repository 'scripts\audit_owner_context_health_watchdog_task.ps1'
$statusPath = Join-Path $repository 'outputs\operational_health\watchdog\latest-watchdog-status.json'
$facts = (& $audit | ConvertFrom-Json)
if ($facts.state -ne 'Disabled' -or $facts.trading_authority -ne $false) {
    throw 'Watchdog task must pass audit while disabled before enablement.'
}
$startedAt = [DateTime]::UtcNow
try {
    Enable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop | Out-Null
    Start-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
    $deadline = [DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        Start-Sleep -Seconds 3
        $task = Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
        $info = Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
        $status = if (Test-Path -LiteralPath $statusPath -PathType Leaf) {
            Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
        } else { $null }
        if ($status -and $status.trading_authority -eq $false -and
                $status.ready_for_unattended_operation -eq $true -and $status.state -eq 'HEALTHY' -and
                ([DateTime]$status.observed_at).ToUniversalTime() -ge $startedAt -and
                [string]$task.State -ne 'Disabled' -and [int]$info.LastTaskResult -eq 0) {
            Write-Output 'OWNER_CONTEXT_HEALTH_WATCHDOG_ENABLED_AND_HEALTHY'
            exit 0
        }
    } while ([DateTimeOffset]::UtcNow -lt $deadline)
    throw 'Watchdog did not produce a fresh healthy status before timeout.'
} catch {
    Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue | Out-Null
    throw
}
