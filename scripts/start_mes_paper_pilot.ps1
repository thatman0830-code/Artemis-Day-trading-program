#requires -Version 5.1
<#
.SYNOPSIS
  Start three bounded MES PAPER_AUTO portfolios on one read-only feed.
.DESCRIPTION
  Paper only. No order route exists; LIVE_AUTO is refused by the code.
  Requires: .venv (Python 3.11+), DATABENTO_API_KEY (user env var) with live
  GLBX.MDP3 access for MES, and a fresh Forex Factory calendar snapshot.
  Without a fresh calendar the session runs but abstains from new entries
  (logged as CALENDAR_UNAVAILABLE_OPERATIONAL_LIMITATION).
#>
[CmdletBinding()]
param([switch]$SkipCalendarFetch)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Project virtual environment (.venv) is missing.' }
if (-not [Environment]::GetEnvironmentVariable('DATABENTO_API_KEY', 'User')) { throw 'DATABENTO_API_KEY is not configured for this user.' }
$env:DATABENTO_API_KEY = [Environment]::GetEnvironmentVariable('DATABENTO_API_KEY', 'User')
Push-Location $repo
try {
    if (-not $SkipCalendarFetch) {
        & $python scripts\import_mes_pilot_calendar.py --fetch
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Calendar fetch failed; new entries will abstain for this session.' }
    }
    & $python scripts\run_mes_paper_pilot.py live-portfolios
    if ($LASTEXITCODE -ne 0) { throw 'Paper session exited with an error.' }
}
finally {
    Pop-Location
    Remove-Item Env:\DATABENTO_API_KEY -ErrorAction SilentlyContinue
}
