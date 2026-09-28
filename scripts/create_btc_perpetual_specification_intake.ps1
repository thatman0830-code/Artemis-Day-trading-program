#requires -Version 5.1
[CmdletBinding()]param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Repository Python runtime is unavailable.'}
& $python -B -m execution.btc_perpetual_specification_intake_v1 template --output $OutputPath
if($LASTEXITCODE-ne 0){throw 'BTC perpetual specification intake template creation failed closed.'}
