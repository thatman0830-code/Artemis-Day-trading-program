#requires -Version 5.1
[CmdletBinding()]
param([switch]$CredentialFreeMock)
$ErrorActionPreference='Stop'
[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe'
$metadata=Join-Path $repository 'data\backtests\es_nq_metadata_dry_run.json'
$authDirectory='C:\Users\fjone\MassiveAuth\es-nq-probe'
$secretPath=Join-Path $authDirectory 'massive.key'
$owner=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$secure=$null;$pointer=[IntPtr]::Zero;$plain=$null;$pushed=$false;$mockRoot=$null
try {
    if(!(Test-Path -LiteralPath $python -PathType Leaf)){throw 'Repository Python runtime is missing.'}
    if(!(Test-Path -LiteralPath $metadata -PathType Leaf)){throw 'Validated metadata report is missing.'}
    New-Item -ItemType Directory -Path $authDirectory -Force|Out-Null
    & icacls.exe $authDirectory /inheritance:r /grant:r "${owner}:(OI)(CI)F"|Out-Null
    if($CredentialFreeMock){
        $plain='synthetic-offline-only'
        $mockRoot=Join-Path ([IO.Path]::GetTempPath()) ('massive-probe-mock-'+[guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path (Join-Path $mockRoot 'data\backtests') -Force|Out-Null
        Copy-Item -LiteralPath $metadata -Destination (Join-Path $mockRoot 'data\backtests\es_nq_metadata_dry_run.json')
        $runRepository=$mockRoot;$runMetadata=Join-Path $mockRoot 'data\backtests\es_nq_metadata_dry_run.json'
    }else{
        $secure=Read-Host 'Enter dedicated Massive Futures Basic API key for bounded ES/NQ probe' -AsSecureString
        $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
        $plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $runRepository=$repository;$runMetadata=$metadata
    }
    if([string]::IsNullOrWhiteSpace($plain)-or$plain.Length-lt 16){throw 'Credential format is invalid.'}
    $temporary=$secretPath+'.tmp';[IO.File]::WriteAllText($temporary,$plain,[Text.UTF8Encoding]::new($false))
    & icacls.exe $temporary /inheritance:r /grant:r "${owner}:F"|Out-Null
    Move-Item -LiteralPath $temporary -Destination $secretPath -Force
    Push-Location -LiteralPath $repository;$pushed=$true
    if($CredentialFreeMock){
        $output=Get-Content -LiteralPath $secretPath -Raw|& $python -m futures_data.aggregate_probe --repository $runRepository --metadata $runMetadata --credential-free-mock
    }else{
        $output=Get-Content -LiteralPath $secretPath -Raw|& $python -m futures_data.aggregate_probe --repository $runRepository --metadata $runMetadata
    }
    if($LASTEXITCODE-ne 0-or($output-join '')-ne'ES_NQ_PROBE_VALIDATED'){throw 'Bounded ES/NQ probe failed closed.'}
    Write-Host 'ES_NQ_PROBE_VALIDATED'
}
finally{
    if($pushed){Pop-Location}
    if($pointer-ne[IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
    $plain=$null;$secure=$null
    Remove-Item -LiteralPath ($secretPath+'.tmp') -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $secretPath -Force -ErrorAction SilentlyContinue
    if(Test-Path -LiteralPath $authDirectory){$remaining=Get-ChildItem -LiteralPath $authDirectory -Force -ErrorAction SilentlyContinue;if(-not$remaining){Remove-Item -LiteralPath $authDirectory -Force -ErrorAction SilentlyContinue}}
    if($CredentialFreeMock-and$mockRoot-and(Test-Path -LiteralPath $mockRoot)){Remove-Item -LiteralPath $mockRoot -Recurse -Force}
}

