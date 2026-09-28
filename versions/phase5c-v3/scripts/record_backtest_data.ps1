[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Symbol,
    [Parameter(Mandatory = $true)][string[]]$Timeframes,
    [ValidateSet('testnet', 'mainnet')][string]$DataNetwork = 'testnet',
    [Parameter(Mandatory = $true)][string]$Archive,
    [double]$PollSeconds = 15,
    [string]$LogFile,
    [string]$AlertFile
)

$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
$arguments = @('-m','backtesting','record','--symbol',$Symbol,'--timeframes') +
    $Timeframes + @('--data-network',$DataNetwork,'--output',$Archive,
    '--poll-seconds',[string]$PollSeconds)
if ($LogFile) { $arguments += @('--log-file',$LogFile) }
if ($AlertFile) { $arguments += @('--alert-file',$AlertFile) }

Push-Location -LiteralPath $repo
try {
    & $python @arguments
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -eq 0) { Write-Host "Historical recorder stopped cleanly: $Archive" }
else { Write-Error "Historical recorder failed with exit code $code" }
exit $code
