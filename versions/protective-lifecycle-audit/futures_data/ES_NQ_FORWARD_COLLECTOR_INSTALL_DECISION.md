# ES/NQ Forward Collector Owner Installation Decision

Implementation and offline tests are complete; installation remains an owner decision. No command below has been executed.

The focused archive/collector suite passes 12 tests, and the complete offline `futures_data` suite passes 135 tests. No provider request, task registration, credential enrollment, forward-data write, recorder start, or BTC control occurred.

The missing configuration was an implementation defect: the consumer and installer were completed while the documented evidence-to-configuration producer was not implemented or invoked. That producer now creates `config/es_nq_forward_sessions.json`, its checksum manifest, and a bootstrap audit solely from retained verified evidence. The current bootstrap contains immutable archived history through 2026-08-26 and an honest zero-pending queue. Unknown future schedule or contract state still fails closed.

Do not install the task unless the following offline validator succeeds. It verifies the configuration identity, checksum manifest, evidence hashes, coverage boundary, archived-history isolation, exact session/contract identities, and pending count. It does not read the credential or use the network.

Enrollment:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\enroll_massive_es_nq_forward_credential.ps1"
```

Validate the finalized collector configuration offline (from any current directory):

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\validate_es_nq_forward_configuration.ps1"
```

This helper resolves the repository from its own location, uses only the repository virtual environment, makes no network request, and never reads the enrolled credential. Installation must not proceed unless it prints exactly `FORWARD_CONFIGURATION_VALIDATED_OFFLINE`.

Install the owner-only task in disabled state:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\install_es_nq_delayed_forward_task.ps1"
```

Status:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\get_es_nq_delayed_forward_status.ps1"
```

Manual bounded catch-up:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\run_es_nq_delayed_forward_catchup.ps1"
```

Graceful stop before the next provider call:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\stop_es_nq_delayed_forward_collector.ps1"
```

Disable:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\disable_es_nq_delayed_forward_task.ps1"
```

Uninstall the task while preserving all data and evidence:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\uninstall_es_nq_delayed_forward_task.ps1"
```

The owner must explicitly enable the reviewed disabled task later. Neither installation nor enrollment authorizes trading.

Enable only after reviewing status, the finalized session manifest, and credential enrollment:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\enable_es_nq_delayed_forward_task.ps1"
```
