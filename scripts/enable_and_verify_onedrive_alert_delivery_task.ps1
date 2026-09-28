#requires -Version 5.1
[CmdletBinding()]param([ValidateRange(30,240)][int]$TimeoutSeconds=120)
$ErrorActionPreference='Stop'
$taskName='Owner Context OneDrive Alert Delivery';$taskPath='\';$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe';$audit=Join-Path $repository 'scripts\audit_onedrive_alert_delivery_task.ps1'
$alerts=Join-Path $repository 'outputs\operational_health\watchdog\alerts.jsonl';$receipts=Join-Path $repository 'outputs\operational_health\alert-delivery-receipts'
$oneDrive=$env:OneDrive;if([string]::IsNullOrWhiteSpace($oneDrive)){$oneDrive=[Environment]::GetEnvironmentVariable('OneDrive','User')}
if([string]::IsNullOrWhiteSpace($oneDrive)){throw 'OneDrive owner sync root is unavailable.'};$sink=Join-Path $oneDrive 'TradingSystem\AlertEvidence'
$facts=(& $audit|ConvertFrom-Json);if($facts.state-ne'Disabled'-or$facts.trading_authority-ne$false){throw 'OneDrive delivery task must pass audit while disabled.'}
$startedAt=[DateTime]::UtcNow
try{
 Enable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop|Out-Null
 Start-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
 $deadline=[DateTimeOffset]::UtcNow.AddSeconds($TimeoutSeconds)
 do{Start-Sleep -Seconds 3;$task=Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop;$info=Get-ScheduledTaskInfo -TaskName $taskName -TaskPath $taskPath -ErrorAction Stop
  if($info.LastRunTime.ToUniversalTime()-ge$startedAt-and[string]$task.State-ne'Running'){
   if([int]$info.LastTaskResult-ne 0){throw 'OneDrive delivery task returned a failure result.'}
   $lines=@(& $python -B -m monitoring.onedrive_delivery_verifier --alerts $alerts --sink $sink --receipts $receipts)
   if($LASTEXITCODE-ne 0){throw 'OneDrive delivery completeness verification failed.'};$verification=($lines-join[Environment]::NewLine)|ConvertFrom-Json
   if($verification.state-ne'DELIVERY_VERIFIED'-or$verification.verified_count-lt 1-or$verification.trading_authority-ne$false){throw 'OneDrive delivery verification rejected the result.'}
   Write-Output 'ONEDRIVE_ALERT_DELIVERY_TASK_ENABLED_AND_VERIFIED';exit 0
  }
 }while([DateTimeOffset]::UtcNow-lt$deadline)
 throw 'OneDrive delivery task did not complete before timeout.'
}catch{Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue|Out-Null;throw}
