#requires -Version 5.1
[CmdletBinding()]param(
  [string]$OutputRoot,
  [switch]$Execute
)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if(-not$OutputRoot){$OutputRoot=Join-Path $repository 'outputs\paper_launch\btc-perpetual-l2-evidence'}
if(-not(Test-Path -LiteralPath $OutputRoot -PathType Container)){
  [void](New-Item -ItemType Directory -Path $OutputRoot)
}
$python=Join-Path $repository '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Repository Python runtime is unavailable.'}
$arguments=@('-B','-m','execution.btc_perpetual_l2_acquisition_v1','--output-root',$OutputRoot)
if($Execute){$arguments+='--execute'}
& $python @arguments
if($LASTEXITCODE-ne 0){throw 'BTC perpetual L2 evidence acquisition failed closed.'}
