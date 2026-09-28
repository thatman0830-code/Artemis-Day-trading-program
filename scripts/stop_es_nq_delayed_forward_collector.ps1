#requires -Version 5.1
[CmdletBinding()]param()
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path;$path=Join-Path $repository 'data\futures_forward.stop';if(!(Test-Path $path)){[IO.File]::WriteAllText($path,"OWNER_STOP_REQUESTED`n",[Text.UTF8Encoding]::new($false))};Write-Output 'STOP_REQUESTED_BEFORE_NEXT_PROVIDER_CALL'
