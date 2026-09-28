#requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$ConfirmSupervision,
    [switch]$ConfirmStopControl
)

$ErrorActionPreference = 'Stop'
if (-not $ConfirmSupervision -or -not $ConfirmStopControl) {
    throw 'Fresh supervision and stop-control confirmation are required.'
}

$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Repository Python runtime is unavailable.'
}

$token = [guid]::NewGuid().ToString('N')
$launchRoot = Join-Path $repository 'outputs\paper_launch'
$publicRoot = Join-Path $launchRoot 'btc-perpetual-public-evidence'
$launchEvidence = Join-Path $launchRoot "launch-evidence-canonical-$token.json"
$healthFacts = Join-Path $launchRoot "btc-paper-cycle-health-canonical-$token.json"
$paperBundle = Join-Path $launchRoot "btc-perpetual-paper-specification-bundle-$token.json"
$sessionRoot = Join-Path $repository "outputs\paper_sessions\canonical-$token"
$runtimeResult = Join-Path $sessionRoot 'runtime-result.json'
$economicsPolicy = Join-Path $launchRoot 'btc-perpetual-paper-economics-policy.json'
$riskPolicy = Join-Path $launchRoot 'btc-perpetual-paper-risk-policy.json'
$vault = 'C:\Users\fjone\OneDrive\Documents\WindowsPowerShell\Brain'
if (-not (Test-Path -LiteralPath $vault -PathType Container)) {
    throw 'Exact Obsidian vault is unavailable; session evidence cannot be backed up.'
}
New-Item -ItemType Directory -Path $sessionRoot -Force | Out-Null

# The launcher performs slow watchdog/strategy/health work first, then acquires and
# binds one public snapshot immediately before assembly.
& $python -B -m execution.supervised_btc_paper_launcher_v1 `
    --mode execute --repository $repository --session-root $sessionRoot `
    --launch-evidence $launchEvidence --economics-policy $economicsPolicy `
    --risk-policy $riskPolicy --public-evidence-root $publicRoot `
    --public-evidence-receipt (Join-Path $publicRoot 'pending.receipt.json') `
    --health-facts $healthFacts `
    --health-collector (Join-Path $PSScriptRoot 'collect_btc_paper_cycle_health.ps1') `
    --launch-evidence-collector (Join-Path $PSScriptRoot 'collect_supervised_paper_launch_evidence.ps1') `
    --paper-specification-bundle $paperBundle --refresh-public-evidence --strategy-mode canonical `
    --confirm-supervision --confirm-stop-control --output $runtimeResult
$sessionExit = $LASTEXITCODE

& $python -B -m execution.paper_session_attribution_v1 `
    --session-root $sessionRoot --attempt-exit-code $sessionExit
if ($LASTEXITCODE -ne 0) {
    throw 'Paper attempt ended but its immutable attribution could not be recorded.'
}
& $python -B -m execution.paper_attribution_cohort_v1 `
    --sessions-root (Join-Path $repository 'outputs\paper_sessions') `
    --output-root (Join-Path $repository 'outputs\paper_evaluation') `
    --minimum-finalized-trades 200
if ($LASTEXITCODE -ne 0) {
    throw 'Paper attempt attribution was recorded but cohort evaluation failed closed.'
}

& (Join-Path $PSScriptRoot 'run_obsidian_continuity_backup.ps1')
if ($LASTEXITCODE -ne 0) {
    throw 'Paper attempt ended but its immediate Obsidian backup failed.'
}
if ($sessionExit -ne 0) {
    throw 'Supervised BTC paper session failed closed; diagnostic evidence was backed up.'
}

Write-Output "SUPERVISED_BTC_PAPER_SESSION_COMPLETE:$sessionRoot"
