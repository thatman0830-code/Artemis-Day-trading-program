#requires -Version 5.1
[CmdletBinding()]
param(
    [Parameter(DontShow = $true)]
    [string]$ConfigurationPath
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$python = Join-Path $repository '.venv\Scripts\python.exe'
if ([string]::IsNullOrWhiteSpace($ConfigurationPath)) {
    $ConfigurationPath = Join-Path $repository 'config\es_nq_forward_sessions.json'
}

try {
    if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
        throw 'Pinned repository Python is unavailable.'
    }
    if (-not (Test-Path -LiteralPath $ConfigurationPath -PathType Leaf)) {
        throw 'Finalized forward-session configuration is unavailable.'
    }

    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $python
    $start.WorkingDirectory = $repository
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    # Python's child-only import root is its working directory; no user/global PYTHONPATH is changed.
    # ProcessStartInfo.ArgumentList is unavailable in Windows PowerShell 5.1/.NET Framework.
    $escapedConfiguration = '"' + $ConfigurationPath.Replace('"', '\"') + '"'
    $escapedRepository = '"' + $repository.Replace('"', '\"') + '"'
    $start.Arguments = '-m futures_data.validate_forward_configuration --configuration ' + $escapedConfiguration + ' --repository ' + $escapedRepository

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $start
    [void]$process.Start()
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    if ($process.ExitCode -ne 0) {
        $category = if ($stderr -match '\(([A-Za-z][A-Za-z0-9_]*)\)') { $Matches[1] } else { 'ValidationError' }
        throw ("Offline forward configuration rejected ({0})." -f $category)
    }
    if ($stdout.Trim() -ne 'FORWARD_CONFIGURATION_VALIDATED_OFFLINE') {
        throw 'Offline validator returned an unexpected result.'
    }
    Write-Output 'FORWARD_CONFIGURATION_VALIDATED_OFFLINE'
}
catch {
    [Console]::Error.WriteLine(("BLOCKED: {0}" -f $_.Exception.Message))
    exit 2
}
