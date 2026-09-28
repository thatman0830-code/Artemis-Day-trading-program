#requires -Version 5.1
[CmdletBinding()]param(
 [ValidateSet('ESU6','NQU6')][string]$Ticker='ESU6',
 [string]$MinuteUtc='2026-09-02T23:25:00Z'
)
$ErrorActionPreference='Stop';$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python=Join-Path $repository '.venv\Scripts\python.exe';$credential='C:\Users\fjone\MassiveAuth\es-nq-forward\credential.dpapi'
$secure=$null;$pointer=[IntPtr]::Zero;$plain=$null
try{
 if(!(Test-Path -LiteralPath $python)-or!(Test-Path -LiteralPath $credential)){throw 'Recheck runtime or enrolled credential is missing.'}
 $cipher=Get-Content -LiteralPath $credential -Raw;$secure=$cipher|ConvertTo-SecureString
 $pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
 Push-Location $repository
 try{
  $plain|& $python -B -m futures_data.gap_minute_recheck --repository $repository --ticker $Ticker --minute $MinuteUtc
  if($LASTEXITCODE-ne 0){throw 'ES/NQ minute recheck failed closed.'}
 }finally{Pop-Location}
}finally{
 if($pointer-ne[IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)}
 $plain=$null;$secure=$null;$cipher=$null
}
