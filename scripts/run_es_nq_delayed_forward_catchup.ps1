#requires -Version 5.1
[CmdletBinding()]param()
& (Join-Path $PSScriptRoot 'run_es_nq_delayed_forward_collector.ps1');exit $LASTEXITCODE
