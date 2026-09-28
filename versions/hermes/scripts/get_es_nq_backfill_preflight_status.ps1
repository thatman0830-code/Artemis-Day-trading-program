#requires -Version 5.1
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
foreach($root in 'es','nq'){$path=Join-Path $repository "data\backtests\${root}_backfill_preflight_1\reports\preflight.json";if(Test-Path $path){Get-Content $path -Raw}else{Write-Output ($root.ToUpper()+': NOT_CREATED')}}
