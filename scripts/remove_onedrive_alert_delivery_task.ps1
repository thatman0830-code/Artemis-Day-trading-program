#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$taskName='Owner Context OneDrive Alert Delivery';$taskPath='\'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$audit=Join-Path $repository 'scripts\audit_onedrive_alert_delivery_task.ps1'
$facts=(& $audit|ConvertFrom-Json);if($facts.action_verified-ne$true-or$facts.trading_authority-ne$false){throw 'OneDrive delivery task identity was not verified; removal rejected.'}
Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue|Out-Null
Stop-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -TaskPath $taskPath -Confirm:$false -ErrorAction Stop
Write-Output 'ONEDRIVE_ALERT_DELIVERY_TASK_REMOVED_EVIDENCE_PRESERVED'
