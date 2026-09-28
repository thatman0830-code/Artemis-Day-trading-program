[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$directory = Join-Path $env:LOCALAPPDATA 'Hermes\Databento\es-nq-historical'
$path = Join-Path $directory 'credential.dpapi'
$temporary = $path + '.tmp'
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().Name

try {
    if (Test-Path -LiteralPath $path -PathType Leaf) {
        throw 'Databento historical credential is already enrolled. Revoke or rotate it explicitly before replacement.'
    }
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    & icacls.exe $directory /inheritance:r /grant:r "${owner}:(OI)(CI)F" | Out-Null

    $secure = Read-Host 'Enter dedicated Databento historical-recovery API key' -AsSecureString
    if ($null -eq $secure -or $secure.Length -ne 32) {
        throw 'Databento credential format rejected.'
    }
    $cipher = $secure | ConvertFrom-SecureString
    [IO.File]::WriteAllText($temporary, $cipher, [Text.UTF8Encoding]::new($false))
    & icacls.exe $temporary /inheritance:r /grant:r "${owner}:F" | Out-Null
    Move-Item -LiteralPath $temporary -Destination $path
    Write-Output 'DATABENTO_HISTORICAL_CREDENTIAL_ENROLLED_OWNER_DPAPI'
}
finally {
    if (Test-Path -LiteralPath $temporary -PathType Leaf) {
        Remove-Item -LiteralPath $temporary -Force
    }
    $secure = $null
    $cipher = $null
}
