#requires -Version 5.1
[CmdletBinding()]param([int]$MaxCycles = 0)
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
$archive = Join-Path $repository 'data\backtests\coinbase_btc_usd_shadow_v2'
$mutex = [Threading.Mutex]::new($false, 'Local\TradingBot-Coinbase-BTC-Shadow-Recorder')
$owned = $false
try {
    $owned = $mutex.WaitOne(0)
    if(-not $owned){ throw 'Coinbase BTC shadow recorder is already running.' }
$arguments = @('-B','-m','backtesting.coinbase_btc_shadow_recorder_v1','--archive',$archive,
    '--timeframes','1m','5m','15m','1h','4h','--interval','15')
if($MaxCycles -gt 0){$arguments += @('--max-cycles', [string]$MaxCycles)}
& $python @arguments
$result = $LASTEXITCODE
} finally {
    if($owned){$mutex.ReleaseMutex()}
    $mutex.Dispose()
}
exit $result
