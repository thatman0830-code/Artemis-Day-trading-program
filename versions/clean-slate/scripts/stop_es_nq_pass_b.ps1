#requires -Version 5.1
[CmdletBinding()]
param()
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$path=Join-Path $repository 'data\backtests\es_nq_pass_b.stop'
if(!(Test-Path $path)){[IO.File]::WriteAllText($path,"OWNER_STOP_REQUESTED`n",[Text.UTF8Encoding]::new($false))}
Write-Output "Pass B stop requested. The worker will stop before the next provider request."
