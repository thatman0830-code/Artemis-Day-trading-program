#requires -Version 5.1
[CmdletBinding()]param()
$ErrorActionPreference='Stop'
$taskName='BTC Perpetual L2 Research Sampler';$taskPath='\'
$repository=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$runner=Join-Path $repository 'scripts\run_btc_perpetual_l2_sampler.ps1'
$user=[Security.Principal.WindowsIdentity]::GetCurrent().Name
if(Get-ScheduledTask -TaskName $taskName -TaskPath $taskPath -ErrorAction SilentlyContinue){throw 'Exact BTC L2 sampler task already exists.'}
$action=New-ScheduledTaskAction -Execute "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -Argument "-NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$runner`" -Execute" `
  -WorkingDirectory $repository
$trigger=New-ScheduledTaskTrigger -Once -At ([DateTime]::Now.AddMinutes(20)) -RepetitionInterval (New-TimeSpan -Minutes 20)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
$principal=New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
$task=New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
  -Description 'Credential-free bounded BTC L2 research sampling. No policy approval or trading authority.'
Register-ScheduledTask -TaskName $taskName -TaskPath $taskPath -InputObject $task|Out-Null
Disable-ScheduledTask -TaskName $taskName -TaskPath $taskPath|Out-Null
Write-Output 'BTC_PERPETUAL_L2_SAMPLER_TASK_INSTALLED_DISABLED_BY_OWNER_POLICY'
