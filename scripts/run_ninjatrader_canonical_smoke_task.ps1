#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
$recorder=Join-Path $repository 'scripts\record_ninjatrader_canonical_smoke.py'
$status=Join-Path $repository 'outputs\operational_health\ninjatrader-canonical-smoke-task-status.json'
$statusDirectory=Split-Path -Parent $status
New-Item -ItemType Directory -Path $statusDirectory -Force|Out-Null
$temporary="$status.$([Guid]::NewGuid().ToString('N')).tmp"
try{
    $cleanGateResult=@(& $python -B (Join-Path $repository 'scripts\evaluate_ninjatrader_clean_day_gate.py') 2>&1)
    if($LASTEXITCODE-ne 0){throw "Clean-day gate failed: $($cleanGateResult -join ' ')"}
    $cleanGate=$cleanGateResult[-1]|ConvertFrom-Json
    if($cleanGate.schema_version-ne'ninjatrader-clean-day-gate-v1'-or
       $cleanGate.paper_execution_permitted-ne$false-or$cleanGate.trading_authority-ne$false){
        throw 'Clean-day gate policy rejected the output.'
    }
    if($cleanGate.state-ne'READY'){
        [ordered]@{state=$cleanGate.state;observed_at=[DateTimeOffset]::UtcNow.ToString('o');clean_day_gate=$cleanGate;trading_authority=$false}|ConvertTo-Json -Depth 7 -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8
        Move-Item -LiteralPath $temporary -Destination $status -Force
        Write-Output "NINJATRADER_CANONICAL_SMOKE_TASK_$($cleanGate.state)"
        exit 0
    }
    $result=@(& $python -B $recorder 2>&1)
    if($LASTEXITCODE-ne 0){throw "Canonical smoke recorder failed: $($result -join ' ')"}
    $payload=$result[-1]|ConvertFrom-Json
    if($payload.schema_version-ne'ninjatrader-canonical-smoke-record-result-v1'-or
       $payload.trading_authority-ne$false-or@($payload.reports).Count-ne 2-or
       @($payload.reports|Where-Object {$_.trading_authority-ne$false-or$_.deterministic_repeat_verified-ne$true}).Count-ne 0){
        throw 'Canonical smoke result policy rejected the output.'
    }
    [ordered]@{state='COMPLETE';observed_at=[DateTimeOffset]::UtcNow.ToString('o');reports=$payload.reports;trading_authority=$false}|ConvertTo-Json -Depth 5 -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $status -Force
    $ErrorActionPreference='Continue'
    $gate=@(& $python -B (Join-Path $repository 'scripts\evaluate_ninjatrader_smoke_gate.py') 2>&1)
    $gateExitCode=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    if($gateExitCode-ne 0){throw "Canonical smoke maturity gate failed: $($gate -join ' ')"}
    $ErrorActionPreference='Continue'
    $lifecycle=@(& $python -B (Join-Path $repository 'scripts\record_ninjatrader_completed_signal_lifecycles.py') 2>&1)
    $lifecycleExitCode=$LASTEXITCODE
    $ErrorActionPreference='Stop'
    if($lifecycleExitCode-ne 0){throw "Canonical signal lifecycle recorder failed: $($lifecycle -join ' ')"}
    $lifecyclePayload=$lifecycle[-1]|ConvertFrom-Json
    if($lifecyclePayload.schema_version-ne'ninjatrader-completed-lifecycle-cycle-v1'-or
       $lifecyclePayload.state-ne'COMPLETE'-or
       $lifecyclePayload.evidence_rejection_count-ne 0-or
       $lifecyclePayload.paper_execution_permitted-ne$false-or
       $lifecyclePayload.trading_authority-ne$false){
        throw 'Canonical signal lifecycle policy rejected the output.'
    }
    $ledgers=@(& $python -B (Join-Path $repository 'scripts\publish_ninjatrader_three_profile_shadow_ledgers.py') 2>&1)
    if($LASTEXITCODE-ne 0){throw "Three-profile shadow ledger publisher failed: $($ledgers -join ' ')"}
    $ledgerPayload=$ledgers[-1]|ConvertFrom-Json
    if($ledgerPayload.schema_version-ne'ninjatrader-three-profile-shadow-ledger-publication-v1'-or
       $ledgerPayload.ledger_count-ne 3-or$ledgerPayload.paper_execution_permitted-ne$false-or
       $ledgerPayload.trading_authority-ne$false){
        throw 'Three-profile shadow ledger policy rejected the output.'
    }
    [ordered]@{state='COMPLETE';observed_at=[DateTimeOffset]::UtcNow.ToString('o');reports=$payload.reports;lifecycle=$lifecyclePayload;shadow_ledgers=$ledgerPayload;trading_authority=$false}|ConvertTo-Json -Depth 7 -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $status -Force
}catch{
    [ordered]@{state='FAILED';observed_at=[DateTimeOffset]::UtcNow.ToString('o');failure_type=$_.Exception.GetType().Name;trading_authority=$false}|ConvertTo-Json -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $status -Force
    throw
}
if(Test-Path -LiteralPath $temporary){Move-Item -LiteralPath $temporary -Destination $status -Force}
Write-Output 'NINJATRADER_CANONICAL_SMOKE_TASK_COMPLETE'
