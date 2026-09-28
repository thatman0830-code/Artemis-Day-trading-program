#requires -Version 5.1
[CmdletBinding()]
param([ValidateRange(1,12)][int]$Hours = 2)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python)){throw 'Project virtual environment is unavailable.'}
if(-not [Environment]::GetEnvironmentVariable('DATABENTO_API_KEY','User')){throw 'DATABENTO_API_KEY is not configured for this user.'}
$deadline=[DateTimeOffset]::UtcNow.AddHours($Hours)
while([DateTimeOffset]::UtcNow -lt $deadline){
    $env:DATABENTO_CAPTURE_SECONDS='50'
    & $python (Join-Path $repository 'scripts\capture_databento_live_es_nq.py')
    if($LASTEXITCODE -ne 0){throw 'Databento live capture failed.'}
    Start-Sleep -Seconds 5
}
Write-Output "DATABENTO_LIVE_BAR_SESSION_COMPLETE:$Hours hours"
