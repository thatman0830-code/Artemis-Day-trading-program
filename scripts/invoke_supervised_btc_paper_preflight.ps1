param(
    [string]$RepositoryRoot,
    [switch]$ConfirmSupervision,
    [switch]$ConfirmStopControl
)
$ErrorActionPreference='Stop'
if(-not$RepositoryRoot){$RepositoryRoot=(Resolve-Path(Join-Path $PSScriptRoot '..')).Path}
$repository=(Resolve-Path -LiteralPath $RepositoryRoot).Path
if(-not$ConfirmSupervision -or -not$ConfirmStopControl){
    throw 'Explicit -ConfirmSupervision and -ConfirmStopControl are required.'
}
$python=Join-Path $repository '.venv\Scripts\python.exe'
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Repository Python runtime is missing.'}
$launchRoot=Join-Path $repository 'outputs\paper_launch'
$economics=Join-Path $launchRoot 'btc-perpetual-paper-economics-policy.json'
$risk=Join-Path $launchRoot 'btc-perpetual-paper-risk-policy.json'
$publicRoot=Join-Path $launchRoot 'btc-perpetual-public-evidence'
$bundle=Join-Path $launchRoot 'btc-perpetual-paper-specification-bundle.json'
foreach($required in @($economics,$risk,$bundle)){
    if(-not(Test-Path -LiteralPath $required -PathType Leaf)){throw "Required preflight artifact is missing: $required"}
}
function Select-UniqueNewestJson([System.IO.FileInfo[]]$Files,[string]$TimeField,[string]$Label){
    $parsed=@($Files|ForEach-Object{
        try{$doc=Get-Content -LiteralPath $_.FullName -Raw|ConvertFrom-Json
            $stamp=[DateTimeOffset]::Parse([string]$doc.$TimeField)
            [pscustomobject]@{Path=$_.FullName;Stamp=$stamp}}
        catch{}
    }|Sort-Object Stamp -Descending)
    if($parsed.Count-eq 0){throw "No valid $Label artifact was found."}
    if($parsed.Count-gt 1 -and $parsed[0].Stamp-eq$parsed[1].Stamp){throw "Newest $Label artifact is ambiguous."}
    return $parsed[0].Path
}
$launch=Select-UniqueNewestJson @(Get-ChildItem -LiteralPath $launchRoot -Filter 'launch-evidence-*.json' -File) 'collected_at' 'launch evidence'
$public=Select-UniqueNewestJson @(Get-ChildItem -LiteralPath $publicRoot -Filter '*.receipt.json' -File) 'captured_at' 'public evidence'
$archives=@(Get-ChildItem -LiteralPath (Join-Path $repository 'data\backtests') -Directory -Filter 'btc_forward_archive*'|ForEach-Object{
    $manifest=Join-Path $_.FullName 'archive_manifest.json'
    if(Test-Path -LiteralPath $manifest -PathType Leaf){
        try{$doc=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json
            [pscustomobject]@{Path=$_.FullName;Stamp=[DateTimeOffset]::Parse([string]$doc.updated_at)}}catch{}
    }}|Sort-Object Stamp -Descending)
if($archives.Count-eq 0){throw 'No valid BTC forward archive was found.'}
if($archives.Count-gt 1 -and $archives[0].Stamp-eq$archives[1].Stamp){throw 'Newest BTC forward archive is ambiguous.'}
$checkpoint=(& git -c "safe.directory=$repository" -C $repository rev-parse HEAD).Trim()
if($LASTEXITCODE-ne 0){throw 'Unable to resolve repository checkpoint.'}
$sessionId=[Guid]::NewGuid().ToString('N')
$sessionRoot=Join-Path $repository "outputs\paper_sessions\preflight-$sessionId"
if(Test-Path -LiteralPath $sessionRoot){throw 'Fresh preflight session path unexpectedly exists.'}
& $python -B -m execution.supervised_btc_paper_preflight_v1 `
    --repository $repository --expected-checkpoint $checkpoint --session-id $sessionId `
    --session-root $sessionRoot --archive-root $archives[0].Path --evidence $launch `
    --economics-policy $economics --risk-policy $risk --public-evidence-root $publicRoot `
    --public-evidence-receipt $public --paper-specification-bundle $bundle `
    --confirm-supervision --confirm-stop-control
exit $LASTEXITCODE
