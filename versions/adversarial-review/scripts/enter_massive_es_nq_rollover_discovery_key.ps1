#requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference='Stop';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$python=Join-Path $repository '.venv\Scripts\python.exe'
$plan=Join-Path $repository 'data\backtests\es_nq_rollover_discovery_plan_3\plan.json'
$authDirectory='C:\Users\fjone\MassiveAuth\es-nq-rollover-discovery';$secretPath=Join-Path $authDirectory 'massive.key';$owner=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$secure=$null;$pointer=[IntPtr]::Zero;$plain=$null;$pushed=$false
try{
 if(!(Test-Path $python)){throw 'Repository Python runtime is missing.'};if(!(Test-Path $plan)){throw 'Frozen Pass A plan is missing.'}
 New-Item -ItemType Directory -Path $authDirectory -Force|Out-Null;& icacls.exe $authDirectory /inheritance:r /grant:r "${owner}:(OI)(CI)F"|Out-Null
 $secure=Read-Host 'Enter dedicated Massive Futures Basic API key for one bounded Pass A rollover-discovery execution' -AsSecureString
 $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
 if([string]::IsNullOrWhiteSpace($plain)-or$plain.Length-lt 16){throw 'Credential format is invalid.'}
 $temporary=$secretPath+'.tmp';[IO.File]::WriteAllText($temporary,$plain,[Text.UTF8Encoding]::new($false));& icacls.exe $temporary /inheritance:r /grant:r "${owner}:F"|Out-Null;Move-Item $temporary $secretPath -Force
 Push-Location $repository;$pushed=$true;$output=Get-Content $secretPath -Raw|& $python -m futures_data.rollover_backfill --repository $repository --execute-pass-a
 if($LASTEXITCODE-ne 0){throw 'Pass A rollover discovery failed closed.'};Write-Output $output
}finally{
 if($pushed){Pop-Location};if($pointer-ne[IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)};$plain=$null;$secure=$null
 Remove-Item ($secretPath+'.tmp') -Force -ErrorAction SilentlyContinue;Remove-Item $secretPath -Force -ErrorAction SilentlyContinue
 if(Test-Path $authDirectory){$remaining=Get-ChildItem $authDirectory -Force -ErrorAction SilentlyContinue;if(-not$remaining){Remove-Item $authDirectory -Force -ErrorAction SilentlyContinue}}
}
