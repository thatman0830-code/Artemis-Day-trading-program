#requires -Version 5.1
[CmdletBinding()]param()
Unregister-ScheduledTask -TaskName 'ES-NQ Delayed Daily Research Collector' -Confirm:$false -ErrorAction SilentlyContinue;Write-Output 'TASK_REMOVED_DATA_AND_AUDIT_EVIDENCE_PRESERVED'
