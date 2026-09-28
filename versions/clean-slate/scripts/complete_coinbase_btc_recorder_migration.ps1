#requires -Version 5.1
#requires -RunAsAdministrator
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$newTask = 'Coinbase BTC Public Shadow Recorder'
$oldTask = 'BTC Public Candle Research Recorder'
$manifest = Join-Path $repository 'data\backtests\coinbase_btc_usd_shadow_v2\archive_manifest.json'

if(-not (Get-ScheduledTask -TaskName $newTask -TaskPath '\' -ErrorAction SilentlyContinue)){
    & (Join-Path $PSScriptRoot 'install_coinbase_btc_shadow_recorder_task.ps1')
}
Start-ScheduledTask -TaskName $newTask -TaskPath '\'
$deadline = [DateTimeOffset]::UtcNow.AddSeconds(60)
do {
    Start-Sleep -Seconds 2
    $newTaskState = (Get-ScheduledTask -TaskName $newTask -TaskPath '\').State
    if(Test-Path -LiteralPath $manifest){
        $document = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
        $observed = [DateTimeOffset]$document.observed_at
        if($document.schema_version -eq 'coinbase-btc-usd-shadow-recorder-v1' -and
           $document.state -eq 'RECORDING' -and $document.promotion_state -eq 'SHADOW_ONLY' -and
           $document.credentials_required -eq $false -and $document.account_access -eq $false -and
           $document.order_endpoints_present -eq $false -and $document.trading_authority -eq $false -and
           $newTaskState -eq 'Running' -and
           ([DateTimeOffset]::UtcNow - $observed).TotalSeconds -le 45){ break }
    }
} while([DateTimeOffset]::UtcNow -lt $deadline)
if(-not $document -or $newTaskState -ne 'Running' -or
   ([DateTimeOffset]::UtcNow - $observed).TotalSeconds -gt 45){
    throw 'Coinbase shadow recorder did not produce fresh verified evidence; old recorder remains unchanged.'
}
$old = Get-ScheduledTask -TaskName $oldTask -TaskPath '\' -ErrorAction SilentlyContinue
if($old){
    if($old.State -eq 'Running'){Stop-ScheduledTask -TaskName $oldTask -TaskPath '\'}
    Disable-ScheduledTask -TaskName $oldTask -TaskPath '\' -ErrorAction Stop | Out-Null
}
[ordered]@{
    state='MIGRATION_SHADOW_RUNNING'; coinbase_task='Running'; hyperliquid_task='Disabled'
    canonical_promotion=$false; paper_execution_permitted=$false; trading_authority=$false
}|ConvertTo-Json -Compress
