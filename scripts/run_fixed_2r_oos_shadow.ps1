#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$repository=(Resolve-Path(Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
$status=Join-Path $repository 'outputs\operational_health\fixed-2r-oos-shadow-task.json'
$temporary="$status.$([guid]::NewGuid().ToString('N')).tmp"
try{
    $result=@(& $python -B (Join-Path $repository 'scripts\collect_fixed_2r_oos_shadow.py') 2>&1)
    if($LASTEXITCODE-ne 0){throw "Fixed-2R OOS collector failed: $($result -join ' ')"}
    $payload=$result[-1]|ConvertFrom-Json
    if($payload.schema_version-ne'fixed-2r-oos-shadow-cycle-v1'-or
       $payload.paper_execution_permitted-ne$false-or$payload.trading_authority-ne$false){
        throw 'Fixed-2R OOS policy rejected the output.'
    }
    [ordered]@{state=$payload.state;observed_at=[DateTimeOffset]::UtcNow.ToString('o');cycle=$payload;trading_authority=$false}|ConvertTo-Json -Depth 5 -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $status -Force
}catch{
    [ordered]@{state='FAILED';observed_at=[DateTimeOffset]::UtcNow.ToString('o');failure_type=$_.Exception.GetType().Name;trading_authority=$false}|ConvertTo-Json -Compress|Set-Content -LiteralPath $temporary -Encoding UTF8
    Move-Item -LiteralPath $temporary -Destination $status -Force
    throw
}
Write-Output 'FIXED_2R_OOS_SHADOW_TASK_COMPLETE'
