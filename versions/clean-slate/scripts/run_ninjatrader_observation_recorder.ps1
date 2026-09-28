#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
$quotes=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'HermesQuoteBridge'
$archive=Join-Path $repository 'data\ninjatrader_observations'
& $python -B -m execution.ninjatrader_observation_recorder_v1 --quote-root $quotes --archive-root $archive --interval 1
exit $LASTEXITCODE
