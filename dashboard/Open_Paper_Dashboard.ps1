param(
    [string]$RunnerRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$Python = '',
    [ValidateRange(1, 65535)]
    [int]$Port = 8765
)

$ErrorActionPreference = 'Stop'
$runnerPath = (Resolve-Path -LiteralPath $RunnerRoot).ProviderPath
if (-not (Test-Path -LiteralPath $runnerPath -PathType Container)) {
    throw 'RunnerRoot must name the runner checkout directory.'
}
$dashboardUrl = "http://127.0.0.1:$Port/"
$healthUrl = "${dashboardUrl}api/state"
$scriptPath = Join-Path $PSScriptRoot 'paper_dashboard.py'

if (-not $Python) {
    $Python = Join-Path $runnerPath '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        $Python = (Get-Command python -ErrorAction Stop).Source
    }
}
$pythonPath = (Resolve-Path -LiteralPath $Python).ProviderPath

function Test-Dashboard {
    try {
        $state = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    } catch {
        return $false
    }
    if (-not $state.root -or -not $state.books) {
        throw "Port $Port is serving another application; choose a different -Port."
    }
    $servedRoot = [System.IO.Path]::GetFullPath([string]$state.root).TrimEnd('\')
    if ($servedRoot -ine $runnerPath.TrimEnd('\')) {
        throw "Port $Port is displaying a different runner. Choose a different -Port or stop that dashboard."
    }
    return $true
}

function ConvertTo-QuotedArgument([string]$Value) {
    # Windows paths cannot contain quotes; double trailing backslashes before the closing quote.
    return '"' + ($Value -replace '(\\+)$', '$1$1') + '"'
}

if (-not (Test-Dashboard)) {
    $arguments = @(
        '-B', (ConvertTo-QuotedArgument $scriptPath),
        '--root', (ConvertTo-QuotedArgument $runnerPath), '--port', $Port
    )
    $errorLog = Join-Path $env:TEMP "artemis-dashboard-$Port-error.log"
    Start-Process -FilePath $pythonPath -ArgumentList $arguments `
        -WorkingDirectory $PSScriptRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $env:TEMP "artemis-dashboard-$Port.log") `
        -RedirectStandardError $errorLog | Out-Null

    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-Dashboard) {
            $ready = $true
            break
        }
    }
    if (-not $ready) {
        throw "The dashboard did not start. Check $errorLog"
    }
}

Start-Process $dashboardUrl
