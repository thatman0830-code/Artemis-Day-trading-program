# Forward Collector Credential Enrollment

The enrollment helper uses a hidden `SecureString` prompt and Windows DPAPI through `ConvertFrom-SecureString`. Ciphertext is stored at `C:\Users\fjone\MassiveAuth\es-nq-forward\credential.dpapi` with inheritance removed and access restricted to the current owner. The plaintext is never a command argument, normal environment variable, repository file, log, report, or Task Scheduler property.

At runtime, the same Windows account decrypts the DPAPI value in memory and pipes it to Python standard input. The BSTR is zeroed afterward. Residual risk remains: code executing as the owner, compromise of the owner profile, or compromise of the running PowerShell/Python processes could access the decrypted key. DPAPI does not protect against a fully compromised owner session. The dedicated key should remain read-only, narrowly entitled, revocable, and separately rate/usage limited.

Enrollment command—not executed:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\enroll_massive_es_nq_forward_credential.ps1"
```

Enrollment does not install or start the task. The verified forward-session manifest must also exist before a run can proceed.
