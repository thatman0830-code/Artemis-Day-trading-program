#requires -Version 5.1
[CmdletBinding()]param(
  [Parameter(Mandatory=$true)][string]$BlankIntake,
  [Parameter(Mandatory=$true)][string]$EvidenceRoot,
  [Parameter(Mandatory=$true)][string]$Receipt,
  [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Repository Python runtime is unavailable.'}
& $python -B -m execution.btc_perpetual_intake_public_draft_v1 --blank-intake $BlankIntake `
  --evidence-root $EvidenceRoot --receipt $Receipt --output $OutputPath
if($LASTEXITCODE-ne 0){throw 'BTC perpetual public-evidence intake mapping failed closed.'}
