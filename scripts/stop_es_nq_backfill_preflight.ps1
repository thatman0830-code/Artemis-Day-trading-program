#requires -Version 5.1
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$path=Join-Path $repository 'data\backtests\es_nq_backfill_preflight.stop'
[IO.File]::WriteAllText($path,"OWNER_STOP_REQUESTED`n",[Text.UTF8Encoding]::new($false));Write-Host 'ES/NQ metadata preflight stop requested.'
