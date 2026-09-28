[CmdletBinding()]
param(
    [Parameter(Mandatory)] [ValidateSet('audit', 'smoke')] [string] $Mode,
    [Parameter(Mandatory)] [string] $InferenceHost,
    [Parameter(Mandatory)] [string] $InferenceBaseUrl,
    [Parameter(Mandatory)] [string] $InferenceModel,
    [string] $Workspace = 'C:\Users\fjone\HermesWorkspaces\hyperliquid-trading-bot-recorder-audit',
    [string] $Prompt = 'hermes_worker/FIRST_TASK.md',
    [int] $MaximumMinutes = 30,
    [int] $MaximumDiskMiB = 1024,
    [int] $MaximumFailures = 1,
    [int] $MaximumTurns = 20
)

$ErrorActionPreference = 'Stop'
$expectedImage = 'sha256:dc5be3921388b07817ee93292841e0025ecda1b5c28471fd9d6515da902c214e'
$image = 'hermes-worker-hardened:0.20.5-fcbd1076'
$workerName = 'hermes-isolated-worker'
$proxyName = 'hermes-egress-proxy'
$networkName = 'hermes-internal-egress'
$resolvedWorkspace = (Resolve-Path -LiteralPath $Workspace).Path
$approvedWorkspace = 'C:\Users\fjone\HermesWorkspaces\hyperliquid-trading-bot-recorder-audit'
if ($resolvedWorkspace -ne $approvedWorkspace) { throw 'Workspace is not the approved sanitized clone.' }
if ((docker image inspect $image --format '{{.Id}}') -ne $expectedImage) { throw 'Pinned image identity mismatch.' }
if ((git -c "safe.directory=$resolvedWorkspace" -C $resolvedWorkspace branch --show-current) -notlike 'hermes/*') { throw 'Workspace is not on a hermes/* branch.' }
if (git -c "safe.directory=$resolvedWorkspace" -C $resolvedWorkspace remote) { throw 'Sanitized clone must have no Git remotes.' }
if (git -c "safe.directory=$resolvedWorkspace" -C $resolvedWorkspace status --porcelain) { throw 'Sanitized clone must be clean before launch.' }
if (-not $InferenceBaseUrl.StartsWith("https://$InferenceHost", [StringComparison]::OrdinalIgnoreCase)) { throw 'Inference URL/host mismatch.' }
if ($MaximumMinutes -lt 1 -or $MaximumMinutes -gt 360) { throw 'Invalid runtime budget.' }
if ($MaximumTurns -lt 1 -or $MaximumTurns -gt 80) { throw 'Invalid turn budget.' }

$hostStart = (Get-Date).ToUniversalTime().ToString('o')
$baselineBytes = (Get-ChildItem -LiteralPath $resolvedWorkspace -Recurse -File | Measure-Object Length -Sum).Sum
$reportDir = Join-Path $resolvedWorkspace 'hermes_worker\reports'
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$proxyLog = Join-Path $reportDir "$stamp-egress.jsonl"
$watchdogLog = Join-Path $reportDir "$stamp-watchdog.jsonl"

function Stop-Worker {
    docker stop --time 5 $workerName 2>$null | Out-Null
    docker rm --force $workerName 2>$null | Out-Null
    docker stop --time 5 $proxyName 2>$null | Out-Null
    docker rm --force $proxyName 2>$null | Out-Null
    docker network rm $networkName 2>$null | Out-Null
}

Stop-Worker
try {
    docker network create --internal $networkName | Out-Null
    docker run --detach --name $proxyName --restart no --read-only --network $networkName `
        --cap-drop ALL --security-opt no-new-privileges:true --user 10000:10000 `
        --cpus 0.5 --memory 256m --memory-swap 256m --pids-limit 32 `
        --tmpfs /tmp:rw,noexec,nosuid,nodev,size=32m `
        --env "HERMES_EGRESS_ALLOWLIST=$InferenceHost" `
        --entrypoint python $image /opt/worker/egress_proxy.py | Out-Null
    docker network connect bridge $proxyName

    $promptPath = (Resolve-Path -LiteralPath (Join-Path $resolvedWorkspace $Prompt)).Path
    if (-not $promptPath.StartsWith($resolvedWorkspace, [StringComparison]::OrdinalIgnoreCase)) { throw 'Prompt escapes workspace.' }
    $containerPrompt = '/workspace/' + $promptPath.Substring($resolvedWorkspace.Length).TrimStart('\').Replace('\','/')
    $args = @(
        'run','--detach','--interactive','--name',$workerName,'--restart','no','--network',$networkName,
        '--read-only','--cpus','2','--memory','4g','--memory-swap','4g','--pids-limit','128',
        '--cap-drop','ALL','--security-opt','no-new-privileges:true','--user','10000:10000',
        '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=256m','--tmpfs','/home/hermes:rw,noexec,nosuid,nodev,size=256m',
        '--mount',"type=bind,source=$resolvedWorkspace,target=/workspace",
        '--env',"HERMES_HOST_TIME_UTC=$hostStart",'--env','GIT_CONFIG_COUNT=1',
        '--env','GIT_CONFIG_KEY_0=safe.directory','--env','GIT_CONFIG_VALUE_0=/workspace',
        '--env',"HERMES_INFERENCE_HOST=$InferenceHost",'--env',"HERMES_INFERENCE_BASE_URL=$InferenceBaseUrl",
        '--env',"HERMES_INFERENCE_MODEL=$InferenceModel",'--env',"HERMES_MAX_TURNS=$MaximumTurns",
        '--env','HTTPS_PROXY=http://hermes-egress-proxy:3128','--env','HTTP_PROXY=http://hermes-egress-proxy:3128',
        '--env','NO_PROXY=localhost,127.0.0.1', '--env','HERMES_CREDENTIAL_STDIN=1',
        $image, $(if ($Mode -eq 'audit') {'audit'} else {'task'}), $(if ($Mode -eq 'smoke') {$containerPrompt} else {$null})
    ) | Where-Object { $_ -ne $null }

    $credential = if ($Mode -eq 'smoke') { Read-Host 'Dedicated capped inference credential' -AsSecureString } else { $null }
    docker @args | Out-Null
    $attachProcess = $null
    if ($Mode -eq 'smoke') {
        $attachInfo = [Diagnostics.ProcessStartInfo]::new()
        $attachInfo.FileName = 'docker'
        $attachInfo.ArgumentList.Add('attach')
        $attachInfo.ArgumentList.Add('--sig-proxy=false')
        $attachInfo.ArgumentList.Add($workerName)
        $attachInfo.UseShellExecute = $false
        $attachInfo.RedirectStandardInput = $true
        $attachProcess = [Diagnostics.Process]::new()
        $attachProcess.StartInfo = $attachInfo
        if (-not $attachProcess.Start()) { throw 'Unable to attach credential stdin.' }
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($credential)
        try {
            $attachProcess.StandardInput.WriteLine([Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr))
            $attachProcess.StandardInput.Close()
        } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
    }

    $deadline = (Get-Date).AddMinutes($MaximumMinutes)
    $failures = 0
    while ((docker inspect $workerName --format '{{.State.Running}}' 2>$null) -eq 'true') {
        if ((Get-Date) -ge $deadline) { throw 'Runtime budget exceeded.' }
        $bytes = (Get-ChildItem -LiteralPath $resolvedWorkspace -Recurse -File | Measure-Object Length -Sum).Sum
        if (($bytes - $baselineBytes) -gt ($MaximumDiskMiB * 1MB)) { throw 'Filesystem budget exceeded.' }
        $pids = [int](docker inspect $workerName --format '{{.State.Pid}}')
        if ($pids -le 0) { $failures++ }
        if ($failures -gt $MaximumFailures) { throw 'Failure budget exceeded.' }
        [pscustomobject]@{time_utc=(Get-Date).ToUniversalTime().ToString('o');event='HEARTBEAT';bytes_delta=($bytes-$baselineBytes)} |
            ConvertTo-Json -Compress | Add-Content -LiteralPath $watchdogLog -Encoding utf8
        Start-Sleep -Seconds 2
    }
    if ($attachProcess) { $attachProcess.WaitForExit(5000) | Out-Null }
    docker logs $proxyName 2>&1 | Set-Content -LiteralPath $proxyLog -Encoding utf8
    $exitCode = [int](docker inspect $workerName --format '{{.State.ExitCode}}')
    if ($exitCode -ne 0) { throw "Worker exited with code $exitCode." }
} finally {
    Stop-Worker
}
