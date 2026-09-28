#requires -Version 5.1
[CmdletBinding()]param()
Disable-ScheduledTask -TaskName 'ES-NQ Delayed Daily Research Collector' -ErrorAction Stop|Out-Null;Write-Output 'TASK_DISABLED'
