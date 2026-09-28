[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Data,
    [Parameter(Mandatory = $true)][string]$Config,
    [Parameter(Mandatory = $true)][string]$Output,
    [switch]$Overwrite
)

$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$venvPython = Join-Path $repo '.venv\Scripts\python.exe'
$python = if (Test-Path -LiteralPath $venvPython) { $venvPython } else { 'python' }
$arguments = @('-m', 'backtesting', 'run', '--data', $Data, '--config', $Config, '--output', $Output)
if ($Overwrite) { $arguments += '--overwrite' }

Push-Location -LiteralPath $repo
try {
    & $python @arguments
    $code = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($code -eq 0) { Write-Host "Historical simulation completed: $Output" }
else { Write-Error "Historical simulation failed with exit code $code" }
exit $code
