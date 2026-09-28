#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference = 'Stop'
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
$collector = Join-Path $repository 'scripts\collect_owner_context_health_facts.ps1'
$output = Join-Path $repository 'outputs\operational_health\watchdog'
$facts = Join-Path $output 'owner-context-facts.json'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository Python runtime is missing.' }
try {
    & $collector -OutputPath $facts
    if ($LASTEXITCODE -ne 0) { throw 'Owner-context fact collection failed.' }
} catch {
    & $python -B -m monitoring.owner_context_health_watchdog --repository $repository `
        --output-dir $output --record-failure HEALTH_COLLECTION_FAILED
    exit 1
}
try {
    & $python -B -m monitoring.owner_context_health_watchdog --repository $repository `
        --output-dir $output --facts $facts
    if ($LASTEXITCODE -ne 0) { throw 'Owner-context health evaluation failed.' }
} catch {
    & $python -B -m monitoring.owner_context_health_watchdog --repository $repository `
        --output-dir $output --record-failure HEALTH_EVALUATION_FAILED
    exit 1
}
Write-Output 'OWNER_CONTEXT_HEALTH_WATCHDOG_COMPLETE'
