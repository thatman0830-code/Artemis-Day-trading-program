param(
    [ValidateRange(1, 65535)][int]$Port = 8765,
    [string]$SessionRoot = "outputs\paper_session"
)

$ErrorActionPreference = "Stop"
$repository = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $repository ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository virtual-environment Python is missing."
}

Set-Location -LiteralPath $repository
& $python -B -m monitoring.paper_dashboard_v1 `
    --host 127.0.0.1 `
    --port $Port `
    --session-root $SessionRoot
exit $LASTEXITCODE
