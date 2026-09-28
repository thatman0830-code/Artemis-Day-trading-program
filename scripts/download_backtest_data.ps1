[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Symbol,
    [Parameter(Mandatory = $true)][string[]]$Timeframes,
    [Parameter(Mandatory = $true)][string]$Start,
    [Parameter(Mandatory = $true)][string]$End,
    [Parameter(Mandatory = $true)][string]$Output,
    [ValidateSet('testnet','mainnet')][string]$DataNetwork = 'testnet',
    [ValidateSet('REJECT','RECORD')][string]$GapPolicy = 'REJECT',
    [switch]$Resume,
    [switch]$Overwrite
)
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
$arguments = @('-m','backtesting','download','--symbol',$Symbol,'--timeframes') + $Timeframes + @('--start',$Start,'--end',$End,'--data-network',$DataNetwork,'--gap-policy',$GapPolicy,'--output',$Output)
if ($Resume) { $arguments += '--resume' }; if ($Overwrite) { $arguments += '--overwrite' }
Push-Location -LiteralPath $repo
try { & $python @arguments; $code=$LASTEXITCODE } finally { Pop-Location }
if ($code -eq 0) { Write-Host "Public historical dataset completed: $Output" } else { Write-Error "Download failed with exit code $code" }
exit $code
