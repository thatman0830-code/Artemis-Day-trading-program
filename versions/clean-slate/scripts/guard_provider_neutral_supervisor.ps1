#requires -Version 5.1
[CmdletBinding()]
param(
    [ValidateRange(60,3600)][int]$MaxCockpitAgeSeconds = 300,
    [ValidateRange(1,12)][int]$Hours = 12,
    [switch]$ForceRestart
)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$trial=Join-Path $repository 'outputs\provider_neutral_paper_trial'
$cockpit=Join-Path $trial 'cockpit-latest.json'
$health=Join-Path $trial 'pipeline-supervisor-health.json'
$runner=Join-Path $repository 'scripts\run_provider_neutral_pipeline_supervisor.ps1'
$python=Join-Path $repository '.venv\Scripts\python.exe'
$replay=Join-Path $repository 'scripts\validate_provider_neutral_replay.py'
if(-not(Test-Path $runner -PathType Leaf)){throw 'Provider-neutral supervisor runner is missing.'}
if(-not(Test-Path $replay -PathType Leaf)){throw 'Provider-neutral replay validator is missing.'}
$now=[DateTimeOffset]::UtcNow
$fresh=$false
if((Test-Path $cockpit -PathType Leaf)-and(Test-Path $health -PathType Leaf)){
    try{$c=Get-Content $cockpit -Raw|ConvertFrom-Json;$h=Get-Content $health -Raw|ConvertFrom-Json;$age=($now-[DateTimeOffset]$c.observed_at).TotalSeconds;$fresh=($age -ge 0 -and $age -le $MaxCockpitAgeSeconds -and $h.state -eq 'HEALTHY' -and [int]$h.consecutive_failures -eq 0 -and $c.authority.live_trading_permitted -eq $false -and $c.trading_authority -eq $false)}catch{$fresh=$false}
}
$processes=@(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue|Where-Object{$_.Name -eq 'pwsh.exe' -and $_.CommandLine -and $_.CommandLine.IndexOf('run_provider_neutral_pipeline_supervisor.ps1',[StringComparison]::OrdinalIgnoreCase)-ge 0})
if($fresh -and -not$ForceRestart){Write-Output 'PROVIDER_NEUTRAL_SUPERVISOR_HEALTHY_NO_ACTION';exit 0}
if($processes.Count -gt 0){foreach($proc in $processes){Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue}}
if(Test-Path $cockpit -PathType Leaf){$incidentDir=Join-Path $trial 'incidents';New-Item -ItemType Directory -Path $incidentDir -Force|Out-Null;$stamp=$now.ToString('yyyyMMddTHHmmssZ');Copy-Item $cockpit (Join-Path $incidentDir "cockpit-stale-$stamp.json") -Force}
$log=Join-Path $trial 'pipeline-supervisor.log';$err=Join-Path $trial 'pipeline-supervisor.err.log';$arg="-NoProfile -ExecutionPolicy Bypass -File `"$runner`" -Hours $Hours";$started=Start-Process -FilePath 'pwsh.exe' -ArgumentList $arg -WorkingDirectory $repository -WindowStyle Hidden -RedirectStandardOutput $log -RedirectStandardError $err -PassThru
$deadline=$now.AddSeconds(120)
do{Start-Sleep -Seconds 3;if(Test-Path $health -PathType Leaf){try{$h=Get-Content $health -Raw|ConvertFrom-Json;$c=Get-Content $cockpit -Raw|ConvertFrom-Json;$age=([DateTimeOffset]::UtcNow-[DateTimeOffset]$c.observed_at).TotalSeconds;if($h.state -eq 'HEALTHY' -and [int]$h.consecutive_failures -eq 0 -and $age -ge 0 -and $age -le $MaxCockpitAgeSeconds -and $c.authority.live_trading_permitted -eq $false -and $c.trading_authority -eq $false){& $python $replay;if($LASTEXITCODE -eq 0){Write-Output "PROVIDER_NEUTRAL_SUPERVISOR_RESTARTED:$($started.Id)";exit 0}}}catch{}}}while([DateTimeOffset]::UtcNow -lt $deadline)
throw 'Provider-neutral supervisor did not publish fresh healthy paper-only evidence before timeout.'
