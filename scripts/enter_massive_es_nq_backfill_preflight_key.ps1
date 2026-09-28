#requires -Version 5.1
[CmdletBinding()]
param([switch]$CredentialFreeMock)
$ErrorActionPreference='Stop';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$python=Join-Path $repository '.venv\Scripts\python.exe'
$authDirectory='C:\Users\fjone\MassiveAuth\es-nq-backfill-preflight';$secretPath=Join-Path $authDirectory 'massive.key';$owner=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$secure=$null;$pointer=[IntPtr]::Zero;$plain=$null;$pushed=$false;$mockRoot=$null
try{
 if(!(Test-Path $python)){throw 'Repository Python runtime is missing.'}
 New-Item -ItemType Directory -Path $authDirectory -Force|Out-Null;& icacls.exe $authDirectory /inheritance:r /grant:r "${owner}:(OI)(CI)F"|Out-Null
 if($CredentialFreeMock){
  $plain='synthetic-offline-only';$mockRoot=Join-Path ([IO.Path]::GetTempPath()) ('massive-backfill-preflight-mock-'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path (Join-Path $mockRoot 'data\backtests') -Force|Out-Null
  Copy-Item (Join-Path $repository 'data\backtests\es_probe_staging_2') (Join-Path $mockRoot 'data\backtests\es_probe_staging_2') -Recurse
  Copy-Item (Join-Path $repository 'data\backtests\nq_probe_staging_2') (Join-Path $mockRoot 'data\backtests\nq_probe_staging_2') -Recurse
  $runRepository=$mockRoot
 }else{
  $secure=Read-Host 'Enter dedicated Massive Futures Basic API key for one metadata-only ES/NQ backfill preflight' -AsSecureString
  $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer);$runRepository=$repository
 }
 if([string]::IsNullOrWhiteSpace($plain)-or$plain.Length-lt 16){throw 'Credential format is invalid.'}
 $temporary=$secretPath+'.tmp';[IO.File]::WriteAllText($temporary,$plain,[Text.UTF8Encoding]::new($false));& icacls.exe $temporary /inheritance:r /grant:r "${owner}:F"|Out-Null;Move-Item $temporary $secretPath -Force
 Push-Location $repository;$pushed=$true
 if($CredentialFreeMock){$output=Get-Content $secretPath -Raw|& $python -m futures_data.backfill_preflight --repository $runRepository --credential-free-mock}else{$output=Get-Content $secretPath -Raw|& $python -m futures_data.backfill_preflight --repository $runRepository}
 if($LASTEXITCODE-ne 0-or($output-join '')-ne'READY_FOR_ES_NQ_BACKFILL_PREFLIGHT'){throw 'Metadata-only backfill preflight failed closed.'}
 Write-Host 'READY_FOR_ES_NQ_BACKFILL_PREFLIGHT'
}finally{
 if($pushed){Pop-Location};if($pointer-ne[IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)};$plain=$null;$secure=$null
 Remove-Item ($secretPath+'.tmp') -Force -ErrorAction SilentlyContinue;Remove-Item $secretPath -Force -ErrorAction SilentlyContinue
 if(Test-Path $authDirectory){$remaining=Get-ChildItem $authDirectory -Force -ErrorAction SilentlyContinue;if(-not$remaining){Remove-Item $authDirectory -Force -ErrorAction SilentlyContinue}}
 if($CredentialFreeMock-and$mockRoot-and(Test-Path $mockRoot)){Remove-Item $mockRoot -Recurse -Force}
}
