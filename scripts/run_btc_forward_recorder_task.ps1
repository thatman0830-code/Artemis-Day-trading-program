#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'supervise_backtest_recorder.ps1') `
    -Symbol BTC -Timeframes @('1m','5m','15m','1h','4h') -DataNetwork mainnet `
    -Archive (Join-Path $repository 'data\backtests\btc_forward_archive_2') `
    -LogDirectory (Join-Path $repository 'outputs\recorder_health\btc_forward_archive_2') `
    -PollSeconds 15 -MaximumRestarts 5 `
    -SingleInstanceName 'Local\HyperliquidTradingBot-BTC-Forward-Recorder'
exit $LASTEXITCODE
