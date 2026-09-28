#requires -Version 5.1
[CmdletBinding()]
param([string]$OutputPath)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if(-not $OutputPath){$OutputPath=Join-Path $repository 'outputs\paper_launch\provider-neutral-launch-evidence-latest.json'}
$cockpit=Join-Path $repository 'outputs\provider_neutral_paper_trial\cockpit-latest.json'
$health=Join-Path $repository 'outputs\provider_neutral_paper_trial\pipeline-supervisor-health.json'
$authority=Join-Path $repository 'config\provider_neutral_paper_authority.json'
foreach($path in @($cockpit,$health,$authority)){if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw "Required provider-neutral evidence is missing: $path"}}
$now=[DateTimeOffset]::UtcNow
$c=Get-Content $cockpit -Raw|ConvertFrom-Json
$h=Get-Content $health -Raw|ConvertFrom-Json
$a=Get-Content $authority -Raw|ConvertFrom-Json
$observed=[DateTimeOffset]$c.observed_at
$age=($now-$observed).TotalSeconds
if($age -lt 0 -or $age -gt 300){throw "Provider-neutral cockpit is stale: $([math]::Round($age,1)) seconds."}
if($h.state -ne 'HEALTHY' -or [int]$h.consecutive_failures -ne 0){throw 'Provider-neutral supervisor is not healthy.'}
if($c.authority.live_trading_permitted -ne $false -or $c.authority.trading_authority -ne $false -or $c.authority.paper_execution_permitted -ne $true){throw 'Paper-only authority invariant failed.'}
if(@($c.portfolios).Count -ne 3 -or @($c.portfolios|Where-Object { "$($_.starting_equity_usd)" -ne '50000'}).Count -gt 0){throw 'Three $50,000 portfolios are not verified.'}
if([int]$c.coverage.covered_days -lt 5 -or @($c.coverage.missing_or_unqualified_days).Count -ne 0){throw 'Five-session coverage gate is not verified.'}
$btc=Get-ScheduledTask -TaskName 'BTC Public Candle Research Recorder' -TaskPath '\' -ErrorAction Stop
if([string]$btc.State -ne 'Running'){throw 'BTC recorder task is not running.'}
$doc=[ordered]@{schema_version='provider-neutral-paper-launch-evidence-v1';observed_at=$now.ToString('o');cockpit_age_seconds=[math]::Round($age,1);supervisor_state=[string]$h.state;symbols=@($c.pipeline.symbols);bars_consumed=[int]$c.pipeline.bars_consumed;covered_days=[int]$c.coverage.covered_days;portfolio_count=@($c.portfolios).Count;paper_execution_permitted=$true;live_trading_permitted=$false;trading_authority=$false;btc_recorder_state=[string]$btc.State;signal_status=[string]$c.baseline.signal_status;candidate_count=[int]$c.adaptive.candidate_count;ready_for_supervised_paper=$true}
$parent=Split-Path -Parent $OutputPath;New-Item -ItemType Directory -Path $parent -Force|Out-Null
$tmp="$OutputPath.tmp-$([Guid]::NewGuid().ToString('N'))";[IO.File]::WriteAllText($tmp,($doc|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false));Move-Item -LiteralPath $tmp -Destination $OutputPath -Force
Write-Output 'PROVIDER_NEUTRAL_PAPER_LAUNCH_EVIDENCE_READY'
