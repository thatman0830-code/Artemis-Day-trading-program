#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
$alerts = Join-Path $repository 'outputs\operational_health\watchdog\alerts.jsonl'
$receipts = Join-Path $repository 'outputs\operational_health\alert-delivery-receipts'
$oneDrive = $env:OneDrive
if ([string]::IsNullOrWhiteSpace($oneDrive)) {
    $oneDrive = [Environment]::GetEnvironmentVariable('OneDrive','User')
}
if ([string]::IsNullOrWhiteSpace($oneDrive)) { throw 'OneDrive owner sync root is unavailable.' }
$sink = Join-Path $oneDrive 'TradingSystem\AlertEvidence'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository Python runtime is missing.' }
if (-not (Test-Path -LiteralPath $alerts -PathType Leaf)) { throw 'Watchdog alert spool is missing.' }
if (-not (Test-Path -LiteralPath (Join-Path $sink 'sink-manifest.json') -PathType Leaf)) {
    throw 'OneDrive alert sink manifest is missing.'
}
& $python -B -m monitoring.off_host_alert_delivery deliver --alerts $alerts --sink $sink --receipts $receipts
if ($LASTEXITCODE -ne 0) { throw 'OneDrive alert delivery failed.' }
