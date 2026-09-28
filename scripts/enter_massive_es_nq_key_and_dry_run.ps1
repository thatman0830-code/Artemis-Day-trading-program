#requires -Version 5.1
[CmdletBinding()]
param([switch]$CredentialFreeMock)
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$repository = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $repository '.venv\Scripts\python.exe'
$authDirectory = 'C:\Users\fjone\MassiveAuth\es-nq-dry-run'
$secretPath = Join-Path $authDirectory 'massive.key'
$reportPath = Join-Path $repository 'data\backtests\es_nq_metadata_dry_run.json'
$diagnosticPath = [IO.Path]::ChangeExtension($reportPath, 'diagnostic.json')
$owner = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$secure = $null; $pointer = [IntPtr]::Zero; $plain = $null
$locationPushed = $false
try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Repository Python runtime is missing.' }
    New-Item -ItemType Directory -Path $authDirectory -Force | Out-Null
    & icacls.exe $authDirectory /inheritance:r /grant:r "${owner}:(OI)(CI)F" | Out-Null
    if ($CredentialFreeMock) {
        $plain = 'synthetic-offline-only'
        $reportPath = Join-Path ([IO.Path]::GetTempPath()) 'massive-es-nq-helper-mock-report.json'
        $diagnosticPath = [IO.Path]::ChangeExtension($reportPath, 'diagnostic.json')
    } else {
        $secure = Read-Host 'Enter dedicated Massive Futures Basic API key' -AsSecureString
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    if ([string]::IsNullOrWhiteSpace($plain) -or $plain.Length -lt 16) { throw 'Credential format is invalid.' }
    $temporary = $secretPath + '.tmp'
    [IO.File]::WriteAllText($temporary, $plain, [Text.UTF8Encoding]::new($false))
    & icacls.exe $temporary /inheritance:r /grant:r "${owner}:F" | Out-Null
    Move-Item -LiteralPath $temporary -Destination $secretPath -Force
    Push-Location -LiteralPath $repository
    $locationPushed = $true
    if ($CredentialFreeMock) {
        $output = Get-Content -LiteralPath $secretPath -Raw | & $python -m futures_data.metadata_dry_run --repository $repository --output $reportPath --credential-free-mock
    } else {
        $output = Get-Content -LiteralPath $secretPath -Raw | & $python -m futures_data.metadata_dry_run --repository $repository --output $reportPath
    }
    if ($LASTEXITCODE -ne 0 -or ($output -join '') -ne 'DRY_RUN_VALIDATED') { throw 'Metadata-only dry run failed closed.' }
    Write-Host 'DRY_RUN_VALIDATED'
}
finally {
    if ($locationPushed) { Pop-Location; $locationPushed = $false }
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $plain = $null; $secure = $null
    Remove-Item -LiteralPath ($secretPath + '.tmp') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretPath -Force -ErrorAction SilentlyContinue
    if ($CredentialFreeMock) { Remove-Item -LiteralPath $reportPath -Force -ErrorAction SilentlyContinue }
    if ($CredentialFreeMock) { Remove-Item -LiteralPath $diagnosticPath -Force -ErrorAction SilentlyContinue }
    if (Test-Path -LiteralPath $authDirectory) {
        $remaining = Get-ChildItem -LiteralPath $authDirectory -Force -ErrorAction SilentlyContinue
        if (-not $remaining) { Remove-Item -LiteralPath $authDirectory -Force -ErrorAction SilentlyContinue }
    }
}
