[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$StartUtc)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repository '.venv\Scripts\python.exe'
$credential = Join-Path $env:LOCALAPPDATA 'Hermes\Databento\es-nq-historical\credential.dpapi'
$output = Join-Path $repository 'outputs\futures_data\databento_historical_probe.json'
$secure = $null
$pointer = [IntPtr]::Zero
$plain = $null
$process = $null

try {
    if (!(Test-Path -LiteralPath $python -PathType Leaf) -or
        !(Test-Path -LiteralPath $credential -PathType Leaf)) {
        throw 'Probe runtime or enrolled credential is missing.'
    }
    $secure = (Get-Content -LiteralPath $credential -Raw) | ConvertTo-SecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $python
    $info.WorkingDirectory = $repository
    $info.Arguments = '-m futures_data.databento_historical_probe --start "' + $StartUtc + '" --output "' + $output + '"'
    $info.UseShellExecute = $false
    $info.RedirectStandardInput = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.CreateNoWindow = $true
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    if (!$process.Start()) { throw 'Unable to start bounded probe.' }
    $process.StandardInput.WriteLine($plain)
    $process.StandardInput.Close()
    $plain = $null
    $process.WaitForExit()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd().Trim()
    if ($process.ExitCode -ne 0) {
        $safeLine = @($stderr -split '\r?\n' | Where-Object {
            $_.StartsWith('DATABENTO_HISTORICAL_PROBE_FAILED_SANITIZED:')
        } | Select-Object -First 1)
        if ($safeLine.Count -eq 1) {
            throw $safeLine[0]
        }
        throw 'DATABENTO_HISTORICAL_PROBE_FAILED_SANITIZED:UNKNOWN'
    }
    $stdout
}
finally {
    if ($pointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
    $plain = $null
    $secure = $null
}
