#requires -Version 5.1
[CmdletBinding()]param(
    [Parameter(Mandatory=$true)][string]$BackupPath
)
$ErrorActionPreference='Stop'
$backup=(Resolve-Path -LiteralPath $BackupPath).Path
$manifestPath=Join-Path $backup 'manifest.json'
if(-not(Test-Path -LiteralPath $manifestPath -PathType Leaf)){throw 'Continuity manifest is missing.'}
$manifest=Get-Content -LiteralPath $manifestPath -Raw|ConvertFrom-Json
if($manifest.schema_version-ne'trading-brain-continuity-v1'-or$manifest.repository_clean-ne$true-or$manifest.trading_authority-ne$false){throw 'Continuity manifest policy is invalid.'}
foreach($item in $manifest.files){
    $path=Join-Path $backup $item.name
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'Continuity artifact is missing.'}
    $file=Get-Item -LiteralPath $path
    $hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    if($file.Length-ne$item.bytes-or$hash-ne$item.sha256){throw 'Continuity artifact integrity failed.'}
}
$temporaryRoot=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$restore=Join-Path $temporaryRoot "trading-brain-restore-$([Guid]::NewGuid().ToString('N'))"
if(-not([IO.Path]::GetFullPath($restore).StartsWith($temporaryRoot,[StringComparison]::OrdinalIgnoreCase))){throw 'Restore path escaped the temporary root.'}
New-Item -ItemType Directory -Path $restore|Out-Null
try{
    $repository=Join-Path $restore 'repository'
    & git clone --quiet (Join-Path $backup 'repository.bundle') $repository
    if($LASTEXITCODE-ne 0){throw 'Repository bundle restore failed.'}
    $head=(& git -C $repository rev-parse HEAD).Trim()
    if($head-ne$manifest.repository_checkpoint){throw 'Restored checkpoint does not match manifest.'}
    $evidence=Join-Path $restore 'evidence'
    Expand-Archive -LiteralPath (Join-Path $backup 'runtime-evidence.zip') -DestinationPath $evidence
    $count=@(Get-ChildItem -LiteralPath $evidence -File -Recurse).Count
    if($count-lt 1){throw 'Restored runtime evidence is empty.'}
    [ordered]@{state='RESTORE_VERIFIED';repository_checkpoint=$head;evidence_file_count=$count;temporary_restore_removed=$true;trading_authority=$false}|ConvertTo-Json -Compress
}finally{
    if(Test-Path -LiteralPath $restore){Remove-Item -LiteralPath $restore -Recurse -Force}
}
