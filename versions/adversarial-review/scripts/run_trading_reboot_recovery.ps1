#requires -Version 5.1
[CmdletBinding()]param([ValidateRange(5,120)][int]$StartupGraceSeconds=20,[ValidateRange(30,300)][int]$FreshnessSeconds=120)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path(Join-Path $PSScriptRoot '..')).Path
$status=Join-Path $repository 'outputs\operational_health\reboot-recovery-checkpoint.json'
$temporary="$status.$([guid]::NewGuid().ToString('N')).tmp"
New-Item -ItemType Directory -Force -Path(Split-Path $status)|Out-Null
$started=@();$ninjaStarted=$false;$reasons=@()
$documentRoots=@([Environment]::GetFolderPath('MyDocuments'))
if($env:OneDrive){$documentRoots=@((Join-Path $env:OneDrive 'Documents'))+$documentRoots}
$documentRoots+=Join-Path $env:USERPROFILE 'OneDrive\Documents'
$barRoot=$documentRoots|Where-Object{Test-Path -LiteralPath(Join-Path $_ 'HermesBarBridge') -PathType Container}|Select-Object -First 1
Start-Sleep -Seconds $StartupGraceSeconds
try{
    $ninja=Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue
    if(-not$ninja){
        $executable='C:\Program Files\NinjaTrader 8\bin\NinjaTrader.exe'
        if(Test-Path -LiteralPath $executable -PathType Leaf){Start-Process -FilePath $executable;$ninjaStarted=$true}else{$reasons+='NINJATRADER_EXECUTABLE_MISSING'}
    }
    foreach($name in @('BTC Public Candle Research Recorder','NinjaTrader MES-NQ Closed Bar Recorder','Forex Factory Five-Day Shadow Trial','Trading Brain Obsidian Continuity Backup','NinjaTrader ES-NQ Canonical Smoke Evidence')){
        $task=Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue
        if($task-and[string]$task.State-ne'Disabled'-and[string]$task.State-ne'Running'){Start-ScheduledTask -TaskName $name -TaskPath '\';$started+=$name}
    }
    $deadline=[DateTimeOffset]::UtcNow.AddSeconds($FreshnessSeconds)
    do{
        Start-Sleep -Seconds 5
        $bars=@()
        foreach($file in @('MES.bar.json','MNQ.bar.json')){
            $path=if($barRoot){Join-Path $barRoot "HermesBarBridge\$file"}else{''}
            if(Test-Path -LiteralPath $path -PathType Leaf){$bars+=Get-Content -LiteralPath $path -Raw|ConvertFrom-Json}
        }
        $fresh=$bars.Count-eq 2-and@($bars|Where-Object{([DateTimeOffset]::UtcNow-[DateTimeOffset]$_.close_time_utc).TotalSeconds-gt$FreshnessSeconds}).Count-eq 0
        $synchronized=$bars.Count-eq 2-and$bars[0].close_time_utc-eq$bars[1].close_time_utc
    }until(($fresh-and$synchronized)-or[DateTimeOffset]::UtcNow-ge$deadline)
    if(-not(Get-Process -Name NinjaTrader -ErrorAction SilentlyContinue)){$reasons+='NINJATRADER_NOT_RUNNING'}
    if(-not$fresh){$reasons+='MES_MNQ_NOT_FRESH'}
    if(-not$synchronized){$reasons+='MES_MNQ_NOT_SYNCHRONIZED'}
    $state=if($reasons.Count-eq 0){'RECOVERED'}else{'USER_ACTION_REQUIRED'}
    $document=[ordered]@{schema_version='trading-reboot-recovery-v1';state=$state;observed_at=[DateTimeOffset]::UtcNow.ToString('o');ninjatrader_started=$ninjaStarted;tasks_started=$started;mes_mnq_fresh=[bool]$fresh;mes_mnq_synchronized=[bool]$synchronized;reasons=$reasons;paper_execution_permitted=$false;trading_authority=$false}
    $document|ConvertTo-Json -Depth 4 -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8;Move-Item -LiteralPath $temporary -Destination $status -Force
    if($state-eq'USER_ACTION_REQUIRED'){try{& "$env:SystemRoot\System32\msg.exe" $env:USERNAME 'Trading data needs attention: open NinjaTrader Simulation and the MES/MNQ one-minute chart workspace.' 2>$null}catch{}}
    $document|ConvertTo-Json -Depth 4 -Compress
}catch{
    [ordered]@{schema_version='trading-reboot-recovery-v1';state='RECOVERY_FAILED';observed_at=[DateTimeOffset]::UtcNow.ToString('o');failure_type=$_.Exception.GetType().Name;paper_execution_permitted=$false;trading_authority=$false}|ConvertTo-Json -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8;Move-Item -LiteralPath $temporary -Destination $status -Force;throw
}
