#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop';$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$python=Join-Path $repository '.venv\Scripts\python.exe'
$sessions=Join-Path $repository 'config\es_nq_forward_sessions.json';$credential='C:\Users\fjone\MassiveAuth\es-nq-forward\credential.dpapi';$secure=$null;$pointer=[IntPtr]::Zero;$plain=$null;$exitCode=0;$message=$null;$process=$null
try{
 if(!(Test-Path $python)-or!(Test-Path $sessions)-or!(Test-Path $credential)){throw 'Collector runtime, verified sessions, or enrolled credential is missing.'}
 $cipher=Get-Content $credential -Raw;$secure=$cipher|ConvertTo-SecureString;$pointer=[Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure);$plain=[Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
 $start=New-Object System.Diagnostics.ProcessStartInfo;$start.FileName=$python;$start.WorkingDirectory=$repository;$start.UseShellExecute=$false;$start.CreateNoWindow=$true
 $start.RedirectStandardInput=$true;$start.RedirectStandardOutput=$true;$start.RedirectStandardError=$true
 $start.Arguments='-m futures_data.forward_collector --repository "'+$repository+'" --sessions "'+$sessions+'" --run'
 $process=New-Object System.Diagnostics.Process;$process.StartInfo=$start;[void]$process.Start()
 $process.StandardInput.WriteLine($plain);$process.StandardInput.Close();$output=$process.StandardOutput.ReadToEnd();$diagnostic=$process.StandardError.ReadToEnd();$process.WaitForExit();$exitCode=$process.ExitCode
 if($exitCode-ne 0){$message='Delayed ES/NQ collector failed closed; see local sanitized diagnostic.'}
}catch{$exitCode=2;$message='Delayed ES/NQ collector wrapper failed closed.'}
finally{if($pointer-ne[IntPtr]::Zero){[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)};$plain=$null;$secure=$null;$cipher=$null;$diagnostic=$null}
if($exitCode-ne 0){[Console]::Error.WriteLine($message);exit $exitCode};Write-Output $output
