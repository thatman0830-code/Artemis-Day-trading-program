#requires -Version 5.1
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$python=Join-Path $repository '.venv\Scripts\python.exe';$bars=Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'HermesBarBridge';$archive=Join-Path $repository 'data\ninjatrader_closed_bars'
& $python -B -m execution.ninjatrader_closed_bar_recorder_v1 --bar-root $bars --archive-root $archive --interval 1;exit $LASTEXITCODE
