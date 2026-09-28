#requires -Version 5.1
[CmdletBinding()]param(
  [Parameter(Mandatory=$true)][string]$InputPath,
  [Parameter(Mandatory=$true)][string]$EvidenceRoot,
  [Parameter(Mandatory=$true)][string]$BundlePath,
  [Parameter(Mandatory=$true)][string]$AsOfUtc
)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Repository Python runtime is unavailable.'}
& $python -B -m execution.btc_perpetual_specification_intake_v1 compile `
  --input $InputPath --repository-root $EvidenceRoot --bundle $BundlePath --as-of $AsOfUtc
if($LASTEXITCODE-ne 0){throw 'BTC perpetual specification intake compilation failed closed.'}
