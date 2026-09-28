#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$backup=Join-Path $repository 'scripts\create_obsidian_continuity_backup.ps1'
$vault='C:\Users\fjone\OneDrive\Documents\WindowsPowerShell\Brain'
$status=Join-Path $repository 'outputs\operational_health\continuity-backup-task-status.json'
try{
    if(-not(Test-Path -LiteralPath $vault -PathType Container)){throw 'Exact Obsidian vault is unavailable.'}
    $lines=@(& $backup -VaultPath $vault)
    if($LASTEXITCODE-ne 0){throw 'Obsidian continuity backup failed.'}
    [ordered]@{state='COMPLETE';observed_at=[DateTimeOffset]::UtcNow.ToString('o');result=($lines[-1]);trading_authority=$false}|ConvertTo-Json -Compress|Set-Content -LiteralPath $status -Encoding UTF8
    $lines
}catch{
    [ordered]@{state='FAILED';observed_at=[DateTimeOffset]::UtcNow.ToString('o');failure_type=$_.Exception.GetType().Name;failure_message=$_.Exception.Message;trading_authority=$false}|ConvertTo-Json -Compress|Set-Content -LiteralPath $status -Encoding UTF8
    throw
}
