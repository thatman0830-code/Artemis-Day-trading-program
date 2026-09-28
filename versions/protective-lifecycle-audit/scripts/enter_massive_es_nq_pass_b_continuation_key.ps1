#requires -Version 5.1
[CmdletBinding()]
param()
$ErrorActionPreference='Stop';[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$python=Join-Path $repository '.venv\Scripts\python.exe'
$plan=Join-Path $repository 'data\backtests\es_nq_pass_b_continuation_plan_1\plan.json';$authDirectory='C:\Users\fjone\MassiveAuth\es-nq-pass-b-continuation';$secretPath=Join-Path $authDirectory 'massive.key';$owner=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$secure=$null;$pointer=[IntPtr]::Zero;$plain=$null;$pushed=$false;$childExit=0;$failureMessage=$null;$output=$null
try{
 if(!(Test-Path $python)-or!(Test-Path $plan)){throw 'Continuation runtime or content-addressed plan is missing.'}
 New-Item -ItemType Directory -Path $authDirectory -Force|Out-Null;& icacls.exe $authDirectory /inheritance:r /grant:r "${owner}:(OI)(CI)F"|Out-Null
 $secure=Read-Host 'Enter dedicated Massive Futures Basic API key for one owner-authorized storage-adjusted Pass B continuation' -AsSecureString
 $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
 if([string]::IsNullOrWhiteSpace($plain)-or$plain.Length-lt 16){throw 'Credential format is invalid.'}
 $temporary=$secretPath+'.tmp';[IO.File]::WriteAllText($temporary,$plain,[Text.UTF8Encoding]::new($false));& icacls.exe $temporary /inheritance:r /grant:r "${owner}:F"|Out-Null;Move-Item $temporary $secretPath -Force
 Push-Location $repository;$pushed=$true;$output=Get-Content $secretPath -Raw|& $python -m futures_data.pass_b_continuation --repository $repository --execute 2>$null
 $childExit=$LASTEXITCODE
 if($childExit-ne 0){$failureMessage='Pass B continuation failed closed; see local sanitized diagnostic.'}
}catch{
 $childExit=2;$failureMessage='Pass B continuation wrapper failed closed.'
}finally{
 if($pushed){Pop-Location};if($pointer-ne[IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)};$plain=$null;$secure=$null
 Remove-Item ($secretPath+'.tmp') -Force -ErrorAction SilentlyContinue;Remove-Item $secretPath -Force -ErrorAction SilentlyContinue
 if(Test-Path $authDirectory){$remaining=Get-ChildItem $authDirectory -Force -ErrorAction SilentlyContinue;if(-not$remaining){Remove-Item $authDirectory -Force -ErrorAction SilentlyContinue}}
}
if($childExit-ne 0){[Console]::Error.WriteLine($failureMessage);exit $childExit}
Write-Output $output
