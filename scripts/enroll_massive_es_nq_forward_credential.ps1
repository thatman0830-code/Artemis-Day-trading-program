#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$directory='C:\Users\fjone\MassiveAuth\es-nq-forward';$path=Join-Path $directory 'credential.dpapi';$owner=[Security.Principal.WindowsIdentity]::GetCurrent().Name
$secure=$null
try{
 if(Test-Path $path){throw 'Forward-collector credential is already enrolled.'}
 New-Item -ItemType Directory -Path $directory -Force|Out-Null;& icacls.exe $directory /inheritance:r /grant:r "${owner}:(OI)(CI)F"|Out-Null
 $secure=Read-Host 'Enter dedicated Massive research-data key for owner-bound DPAPI enrollment' -AsSecureString
 $cipher=$secure|ConvertFrom-SecureString;$temporary=$path+'.tmp';[IO.File]::WriteAllText($temporary,$cipher,[Text.UTF8Encoding]::new($false));& icacls.exe $temporary /inheritance:r /grant:r "${owner}:F"|Out-Null
 Move-Item $temporary $path;Write-Output 'FORWARD_CREDENTIAL_ENROLLED_OWNER_DPAPI'
}finally{$secure=$null;Remove-Item ($path+'.tmp') -Force -ErrorAction SilentlyContinue}
