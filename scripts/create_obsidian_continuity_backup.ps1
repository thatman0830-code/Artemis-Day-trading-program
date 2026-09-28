#requires -Version 5.1
[CmdletBinding()]param(
    [Parameter(Mandatory=$true)][string]$VaultPath
)
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$vault=(Resolve-Path -LiteralPath $VaultPath).Path
$head=(& git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository rev-parse HEAD).Trim()
if($LASTEXITCODE-ne 0-or$head-notmatch'^[0-9a-f]{40,64}$'){throw 'Git checkpoint is unavailable.'}
$dirty=(& git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository status --porcelain --untracked-files=all)
if($LASTEXITCODE-ne 0-or$dirty){throw 'A clean repository checkpoint is required.'}
$forbidden=Get-ChildItem -LiteralPath (Join-Path $repository 'outputs') -File -Recurse -Force |
    Where-Object {$_.Name-match'(?i)(^\.env|credential|secret|private.?key|wallet|token)' -or $_.Extension-match'(?i)^\.(key|pem|p12|pfx)$'}
if($forbidden){throw 'Potentially sensitive runtime evidence cannot be backed up.'}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$root=Join-Path $vault '02_Projects\Trading Brain Continuity'
$final=Join-Path $root "$stamp-$($head.Substring(0,12))"
$staging=Join-Path $root ".staging-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $staging -Force|Out-Null
try{
    $bundle=Join-Path $staging 'repository.bundle'
    & git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository bundle create $bundle --all
    if($LASTEXITCODE-ne 0){throw 'Git bundle creation failed.'}
    & git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository bundle verify $bundle|Out-Null
    if($LASTEXITCODE-ne 0){throw 'Git bundle verification failed.'}
    # The complete outputs tree contains high-frequency recorder logs and tens of
    # thousands of duplicate news snapshots. Those are operational streams, not
    # continuity state, and caused the scheduled task to exceed its time limit.
    # Preserve the latest canonical evidence plus bounded session history.
    $evidenceSource=Join-Path $staging 'runtime-evidence'
    New-Item -ItemType Directory -Path $evidenceSource -Force|Out-Null
    function Add-EvidenceFile([string]$Path){
        if(-not(Test-Path -LiteralPath $Path -PathType Leaf)){return}
        $outputsRoot=Join-Path $repository 'outputs'
        $relative=$Path.Substring($outputsRoot.Length).TrimStart('\')
        $destination=Join-Path $evidenceSource $relative
        New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force|Out-Null
        Copy-Item -LiteralPath $Path -Destination $destination -Force
    }
    Get-ChildItem -LiteralPath (Join-Path $repository 'outputs\operational_health') -File -Filter '*.json'|ForEach-Object{Add-EvidenceFile $_.FullName}
    foreach($name in 'latest-readiness.json','latest-watchdog-status.json','owner-context-facts.json'){
        Add-EvidenceFile (Join-Path $repository "outputs\operational_health\watchdog\$name")
    }
    foreach($relative in @(
        'forex_factory_shadow_trial\latest.json','forex_factory_shadow_trial\daily-risk-map.json',
        'forex_factory_shadow_trial\policy-comparison.json',
        'forex_factory_shadow_trial\decision-diagnostics\scorecard.json',
        'provider_neutral_paper_trial\latest.json','provider_neutral_paper_trial\trades.jsonl',
        'ninjatrader_gap_recovery\latest.json','ninjatrader_gap_recovery\canonical-replay.json',
        'ninjatrader_micro_instrument_specs\latest.json','ninjatrader_micro_paper_policy\proposal.json',
        'ninjatrader_shadow_profile_comparison\latest.json',
        'ninjatrader_canonical_smoke_gate\latest.json',
        'ninjatrader_canonical_smoke_acceptance\latest.json')){
        Add-EvidenceFile (Join-Path (Join-Path $repository 'outputs') $relative)
    }
    Get-ChildItem -LiteralPath (Join-Path $repository 'outputs\paper_launch') -File -Filter '*.json' -ErrorAction SilentlyContinue|ForEach-Object{Add-EvidenceFile $_.FullName}
    Get-ChildItem -LiteralPath (Join-Path $repository 'outputs\paper_sessions') -Directory -ErrorAction SilentlyContinue|
        Sort-Object LastWriteTimeUtc -Descending|Select-Object -First 10|ForEach-Object{
            Get-ChildItem -LiteralPath $_.FullName -File -Filter '*.json'|ForEach-Object{Add-EvidenceFile $_.FullName}
        }
    foreach($market in 'ES','NQ'){
        $latest=Get-ChildItem -LiteralPath (Join-Path $repository "outputs\ninjatrader_canonical_smoke_history\$market\events") -File -Filter '*.json' -ErrorAction SilentlyContinue|Sort-Object Name|Select-Object -Last 1
        if($latest){Add-EvidenceFile $latest.FullName}
    }
    $evidence=Join-Path $staging 'runtime-evidence.zip'
    Compress-Archive -Path (Join-Path $evidenceSource '*') -DestinationPath $evidence -CompressionLevel Optimal
    Remove-Item -LiteralPath $evidenceSource -Recurse -Force
    $files=@($bundle,$evidence)|ForEach-Object {
        [pscustomobject]@{name=[IO.Path]::GetFileName($_);bytes=(Get-Item -LiteralPath $_).Length;sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
    $manifest=[ordered]@{schema_version='trading-brain-continuity-v1';created_at=[DateTimeOffset]::UtcNow.ToString('o');repository_checkpoint=$head;repository_clean=$true;files=$files;evidence_scope='CURATED_CANONICAL_AND_BOUNDED_RECENT';raw_recorder_data_included=$false;trading_authority=$false}
    $manifest|ConvertTo-Json -Depth 5 -Compress|Set-Content -LiteralPath (Join-Path $staging 'manifest.json') -Encoding UTF8
    $note=@"
# Trading Brain continuity checkpoint

- Created: $($manifest.created_at)
- Repository checkpoint: ``$head``
- Repository clean: true
- Runtime evidence archive: verified by SHA-256 in ``manifest.json``
- Trading authority: false

This capsule contains the complete committed Git history and a bounded set of current canonical operational evidence. High-frequency logs, duplicate news snapshots, and raw recorder archives are deliberately excluded; raw data requires the separate recorder snapshot workflow.

## Restore

1. Verify both artifact hashes against ``manifest.json``.
2. Clone ``repository.bundle`` into a new directory.
3. Extract ``runtime-evidence.zip`` beside the restored repository.
4. Run the full test suite and the operational-health audit before any paper session.
"@
    Set-Content -LiteralPath (Join-Path $staging 'README.md') -Value $note -Encoding UTF8
    $commits=@(& git -c "safe.directory=$($repository.Replace('\','/'))" -C $repository log -n 100 --date=iso-strict --pretty=format:'- `%H` - %ad - %s')
    if($LASTEXITCODE-ne 0){throw 'Git history export failed.'}
    $sessionLines=@()
    Get-ChildItem -LiteralPath (Join-Path $repository 'outputs\paper_sessions') -Directory -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending|Select-Object -First 50|ForEach-Object {
            $runtimePath=Join-Path $_.FullName 'runtime-result.json'
            if(Test-Path -LiteralPath $runtimePath -PathType Leaf){
                try{
                    $runtime=Get-Content -LiteralPath $runtimePath -Raw|ConvertFrom-Json
                    $attributionPath=Join-Path $_.FullName 'session-attribution-v2.json'
                    $attribution=if(Test-Path -LiteralPath $attributionPath){(Get-Content -LiteralPath $attributionPath -Raw|ConvertFrom-Json).payload}else{$null}
                    $strategyPath=Join-Path $_.FullName 'canonical-strategy-status.json'
                    $strategy=if(Test-Path -LiteralPath $strategyPath){Get-Content -LiteralPath $strategyPath -Raw|ConvertFrom-Json}else{$null}
                    $adapterPath=Join-Path $_.FullName 'adapter-checkpoint.json'
                    $performancePath=Join-Path $_.FullName 'performance-checkpoint.json'
                    $receipts=$null;$fills=$null;$position=$null;$equity=$null;$netResult=$null
                    if(Test-Path -LiteralPath $adapterPath){
                        $adapter=Get-Content -LiteralPath $adapterPath -Raw|ConvertFrom-Json
                        $receipts=@($adapter.payload.receipts).Count
                    }
                    if(Test-Path -LiteralPath $performancePath){
                        $performance=Get-Content -LiteralPath $performancePath -Raw|ConvertFrom-Json
                        $ledger=$performance.payload.ledger.fields
                        $fills=@($ledger.fill_bindings.'$tuple').Count
                        $snapshots=@($ledger.accounting.fields.snapshots.'$tuple')
                        if($snapshots.Count-gt 0){
                            $latest=$snapshots[-1].fields
                            $position=$latest.position.fields.signed_quantity.'$decimal'
                            $equity=$latest.equity.'$decimal'
                            $netResult=$latest.net_result.'$decimal'
                        }
                    }
                    $attributedOutcome=if($null-ne$attribution){$attribution.outcome}else{'NOT_RECORDED'}
                    $attributionReason=if($null-ne$attribution){$attribution.explanation}else{'Legacy session without canonical attribution'}
                    $terminationReason=if($null-ne$attribution){$attribution.termination_reason}else{$runtime.termination_reason}
                    $sessionLines+=('- **{0}** - `{1}` to `{2}`; state `{3}`; termination `{4}`; cycles {5}; commands {6}; receipts {7}; fills {8}; strategy outcome `{9}`; reason `{10}`; actionable `{11}`; qualification `{12}`; entry zone `{13}`; position `{14}`; equity `{15}`; net result `{16}`; attributed outcome `{17}`; attribution `{18}`; trading authority `{19}`' -f $_.Name,$runtime.started_at,$runtime.stopped_at,$runtime.state,$terminationReason,$runtime.cycles,$runtime.commands,$receipts,$fills,$strategy.result_outcome,$strategy.decision_reason,$strategy.actionable,$strategy.qualification_present,$strategy.entry_zone_present,$position,$equity,$netResult,$attributedOutcome,$attributionReason,$runtime.trading_authority)
                }catch{$sessionLines+="- **$($_.Name)** - evidence unreadable; investigate before reuse"}
            }
        }
    $economics=Get-Content -LiteralPath (Join-Path $repository 'outputs\paper_launch\btc-perpetual-paper-economics-policy.json') -Raw
    $risk=Get-Content -LiteralPath (Join-Path $repository 'outputs\paper_launch\btc-perpetual-paper-risk-policy.json') -Raw
    $journal=@"
# Trading Brain project journal

Generated from verified local artifacts at $($manifest.created_at). This is a continuity record, not trading authority.

## Current checkpoint

``$head`` - clean working tree

## Recent supervised paper sessions

$($sessionLines -join [Environment]::NewLine)

## ES/NQ canonical smoke evidence

$(@('ES','NQ')|ForEach-Object {
    $events=Join-Path $repository "outputs\ninjatrader_canonical_smoke_history\$_\events"
    $latest=Get-ChildItem -LiteralPath $events -File -Filter '*.json' -ErrorAction SilentlyContinue|Sort-Object Name|Select-Object -Last 1
    if($latest){
        try{
            $event=Get-Content -LiteralPath $latest.FullName -Raw|ConvertFrom-Json
            "- **$_** - reports $([int64]$event.sequence+1); latest ``$($event.latest_outcome)``; bars $($event.report.source_bar_count); deterministic repeat $($event.report.deterministic_repeat_verified); dataset ``$($event.dataset_fingerprint)``; chain head ``$($event.source_chain_head_sha256)``; trading authority ``$($event.report.trading_authority)``"
        }catch{"- **$_** - smoke history unreadable; investigate before reuse"}
    }else{"- **$_** - no retained canonical smoke report"}
})

## ES/NQ smoke maturity gate

$(try{$gate=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_canonical_smoke_gate\latest.json') -Raw|ConvertFrom-Json;"- Progress: **$($gate.progress_percent)%**; ready for supervised paper review: ``$($gate.ready_for_supervised_paper_review)``; reasons: ``$(@($gate.reasons)-join ',')``; trading authority: ``$($gate.trading_authority)``"}catch{'- Gate evidence unavailable or unreadable'})

## ES/NQ smoke acceptance

$(try{$acceptance=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_canonical_smoke_acceptance\latest.json') -Raw|ConvertFrom-Json;"- Attestation ``$($acceptance.attestation_id)``; design-review eligible: ``$($acceptance.supervised_paper_design_review_eligible)``; paper execution permitted: ``$($acceptance.supervised_paper_execution_permitted)``; remaining gates: ``$(@($acceptance.remaining_gates)-join ',')``; trading authority: ``$($acceptance.trading_authority)``"}catch{'- Acceptance attestation not yet available'})

## Verified MES/MNQ instrument specifications

$(try{$specs=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_micro_instrument_specs\latest.json') -Raw|ConvertFrom-Json;@($specs.specifications|ForEach-Object{"- **$($_.instrument)** - multiplier ``$($_.contract_multiplier)``; minimum tick ``$($_.minimum_tick)``; tick value ``$($_.tick_value) USD``; source [CME]($($_.primary_source_url)); trading authority ``$($_.trading_authority)``"})-join[Environment]::NewLine}catch{'- Instrument specification evidence unavailable'})

## Unapproved MES/MNQ paper policy proposal

$(try{$proposal=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_micro_paper_policy\proposal.json') -Raw|ConvertFrom-Json;@($proposal.profiles|ForEach-Object{"- **$($_.profile)** - contracts ``$($_.maximum_contracts_total)``; initial risk ``$($_.maximum_initial_risk_usd) USD``; session loss/drawdown ``$($_.maximum_session_loss_usd) USD``; fee ``$($_.modeled_fee_per_contract_per_side_usd) USD/side``; slippage ``$($_.modeled_slippage_ticks_per_fill) tick``; comparison only ``$($_.comparison_only)``; authority ``$($_.trading_authority)``"})-join[Environment]::NewLine}catch{'- Paper policy proposal unavailable'})

## MES/MNQ shadow profile comparison

$(try{$comparison=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_shadow_profile_comparison\latest.json') -Raw|ConvertFrom-Json;"- State ``$($comparison.selection_state)``; completed trades ``$($comparison.input_trade_count)``; candidate ``$($comparison.candidate_profile)``; minimum sample ``$($comparison.minimum_total_trades)`` total and ``$($comparison.minimum_trades_per_market)`` per market; trading authority ``$($comparison.trading_authority)``"}catch{'- Shadow comparison evidence unavailable'})

## Completed MES/MNQ shadow trade history

$(try{$tradeEvents=Get-ChildItem -LiteralPath (Join-Path $repository 'outputs\ninjatrader_completed_shadow_trades\events') -File -Filter '*.json' -ErrorAction Stop;"- Completed immutable trades: ``$(@($tradeEvents).Count)``; these are comparison facts only and grant no trading authority."}catch{'- Completed immutable trades: `0`'})

## MES/MNQ signal lifecycle health

$(try{$lifecycle=Get-Content -LiteralPath (Join-Path $repository 'outputs\operational_health\ninjatrader-signal-lifecycle-status.json') -Raw|ConvertFrom-Json;"- State ``$($lifecycle.state)``; qualified signals ``$($lifecycle.qualified_signal_count)``; evidence rejections ``$($lifecycle.evidence_rejection_count)``; retained completed trades ``$($lifecycle.retained_completed_trades)``; paper execution permitted ``$($lifecycle.paper_execution_permitted)``; trading authority ``$($lifecycle.trading_authority)``"}catch{'- Signal lifecycle health evidence unavailable or unreadable'})

## MES/MNQ gap-recovery export validation

$(try{$recovery=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_gap_recovery\latest.json') -Raw|ConvertFrom-Json;"- State ``$($recovery.state)``; report ``$($recovery.report_id)``; reason: $($recovery.reason); markets ``$(@($recovery.exports|ForEach-Object{"$($_.market):$($_.record_count) bars/$($_.missing_interval_bars_present) recovery bars"})-join ', ')``; paper execution permitted ``$($recovery.paper_execution_permitted)``; trading authority ``$($recovery.trading_authority)``"}catch{'- Gap-recovery export validation unavailable or unreadable'})

## MES/MNQ independent recovery replay

$(try{$replay=Get-Content -LiteralPath (Join-Path $repository 'outputs\ninjatrader_gap_recovery\canonical-replay.json') -Raw|ConvertFrom-Json;@($replay.reports|ForEach-Object{"- **$($_.market)** - bars ``$($_.source_bar_count)``; latest outcome ``$($_.latest_outcome)``; deterministic ``$($_.deterministic_repeat_verified)``; cross-source equivalence claimed ``$($_.cross_source_equivalence_claimed)``; trading authority ``$($_.trading_authority)``"})-join[Environment]::NewLine}catch{'- Independent recovery replay unavailable or unreadable'})

## MES/MNQ post-maintenance gate

$(try{$post=Get-Content -LiteralPath (Join-Path $repository 'outputs\operational_health\ninjatrader-post-maintenance-gate.json') -Raw|ConvertFrom-Json;"- State ``$($post.state)``; single recorder ``$($post.recorder_launcher_count)``; current day canonical eligible ``$($post.current_day_canonical_eligible)``; markets ``$(@($post.markets|ForEach-Object{"$($_.market): scheduled=$($_.scheduled_non_trading_minute_count), unresolved=$($_.unresolved_open_session_minute_count)"})-join ', ')``; trading authority ``$($post.trading_authority)``"}catch{'- Post-maintenance gate unavailable or unreadable'})

## MES/MNQ clean-day gate

$(try{$clean=Get-Content -LiteralPath (Join-Path $repository 'outputs\operational_health\ninjatrader-clean-day-gate.json') -Raw|ConvertFrom-Json;"- State ``$($clean.state)``; UTC day ``$($clean.day)``; ES/MNQ bars ``$($clean.es_bar_count)/$($clean.nq_bar_count)`` of ``$($clean.minimum_bars_per_market)``; canonical evaluation permitted ``$($clean.canonical_evaluation_permitted)``; reasons ``$(@($clean.reasons)-join ',')``; paper execution permitted ``$($clean.paper_execution_permitted)``; trading authority ``$($clean.trading_authority)``"}catch{'- Clean-day gate unavailable or unreadable'})

## September 14 canonical boundary

$(try{$boundary=Get-Content -LiteralPath (Join-Path $repository 'outputs\operational_health\ninjatrader-canonical-boundary-2026-09-14.json') -Raw|ConvertFrom-Json;"- State ``$($boundary.state)``; target UTC day ``$($boundary.target_day_utc)``; quarantined prior archives ``$(@($boundary.prior_archives|ForEach-Object{"$($_.market):$($_.archive_file)/gaps=$($_.inherited_unresolved_gap_count)"})-join ', ')``; paper execution permitted ``$($boundary.paper_execution_permitted)``; trading authority ``$($boundary.trading_authority)``"}catch{'- September 14 canonical boundary unavailable or unreadable'})

## Forex Factory five-day shadow trial

$(try{$news=Get-Content -LiteralPath (Join-Path $repository 'outputs\forex_factory_shadow_trial\latest.json') -Raw|ConvertFrom-Json;"- State ``$($news.state)``; trial days ``$(@($news.trial_days)-join ', ')``; USD events ``$($news.usd_event_count)``; high-impact USD events ``$($news.high_impact_usd_count)``; directional signal permitted ``$($news.directional_signal_permitted)``; order influence permitted ``$($news.order_influence_permitted)``; trading authority ``$($news.trading_authority)``"}catch{'- Forex Factory shadow-trial evidence unavailable or unreadable'})

$(try{$score=Get-Content -LiteralPath (Join-Path $repository 'outputs\forex_factory_shadow_trial\decision-diagnostics\scorecard.json') -Raw|ConvertFrom-Json;"- Decision association state ``$($score.state)``; decisions ``$($score.decision_count)``; automatic policy change permitted ``$($score.automatic_policy_change_permitted)``; trading authority ``$($score.trading_authority)``"}catch{'- News-to-decision scorecard unavailable or unreadable'})

$(try{$newsHealth=Get-Content -LiteralPath (Join-Path $repository 'outputs\operational_health\forex-factory-trial-health.json') -Raw|ConvertFrom-Json;"- Trial health ``$($newsHealth.state)``; source age ``$([math]::Round($newsHealth.source_age_seconds,1)) seconds``; diagnostic coverage ``$($newsHealth.coverage_percent)%``; source hash verified ``$($newsHealth.source_hash_verified)``; trading authority ``$($newsHealth.trading_authority)``"}catch{'- Forex Factory trial health unavailable or unreadable'})

## Reboot recovery checkpoint

$(try{$reboot=Get-Content -LiteralPath (Join-Path $repository 'outputs\operational_health\reboot-recovery-checkpoint.json') -Raw|ConvertFrom-Json;"- State ``$($reboot.state)``; NinjaTrader started ``$($reboot.ninjatrader_started)``; MES/MNQ fresh ``$($reboot.mes_mnq_fresh)``; synchronized ``$($reboot.mes_mnq_synchronized)``; reasons ``$(@($reboot.reasons)-join ',')``; trading authority ``$($reboot.trading_authority)``"}catch{'- Reboot recovery checkpoint unavailable or unreadable'})

## Approved BTC paper economics policy

``````json
$economics
``````

## Approved BTC paper risk policy

``````json
$risk
``````

## Recent engineering checkpoints

$($commits -join [Environment]::NewLine)
"@
    Set-Content -LiteralPath (Join-Path $staging 'PROJECT_JOURNAL.md') -Value $journal -Encoding UTF8
    if(Test-Path -LiteralPath $final){throw 'Continuity checkpoint already exists.'}
    Move-Item -LiteralPath $staging -Destination $final
    Copy-Item -LiteralPath (Join-Path $final 'README.md') -Destination (Join-Path $root 'LATEST.md') -Force
    Copy-Item -LiteralPath (Join-Path $final 'PROJECT_JOURNAL.md') -Destination (Join-Path $root 'PROJECT_JOURNAL.md') -Force
    Write-Output "OBSIDIAN_CONTINUITY_BACKUP_COMPLETE:$final"
}catch{
    if(Test-Path -LiteralPath $staging){Remove-Item -LiteralPath $staging -Recurse -Force}
    throw
}
