# Artemis Paper Trading Dashboard

Artemis is a local, read-only view of the conservative, moderate, and aggressive MES paper portfolios. It reads saved output from an existing runner checkout. Opening it does **not** start the trading runner or place orders.

## Open on Windows

From the repository root, run:

```powershell
.\dashboard\Open_Paper_Dashboard.ps1
```

The launcher starts a hidden local dashboard process if needed, then opens your browser. It uses the repository root and its `.venv\Scripts\python.exe` by default, falling back to `python` on your PATH. You can point it at a separate runner checkout and Python installation:

```powershell
.\dashboard\Open_Paper_Dashboard.ps1 -RunnerRoot 'D:\Trading\Artemis Runner' -Python 'D:\Trading\Artemis Runner\.venv\Scripts\python.exe' -Port 8766
```

Use the runner's Python environment so its evidence modules and dependencies can load. A port already showing a different runner is rejected rather than silently displaying the wrong account data.

For a desktop shortcut, create a Windows shortcut whose target starts `powershell.exe -NoProfile -File` followed by the quoted full path to `dashboard\Open_Paper_Dashboard.ps1`. Add `-RunnerRoot` and `-Python` if your runner is elsewhere. This repository does not install a shortcut automatically.

## Run in a terminal

```powershell
python -B .\dashboard\paper_dashboard.py --port 8765
```

Then open <http://127.0.0.1:8765/>. The repository root is the default data source regardless of your current directory. Override it with `--root 'D:\Trading\Artemis Runner'`. Stop a terminal-launched server with Ctrl+C. A hidden launcher process stays running after its browser tab closes; end the specific dashboard Python process in Task Manager when no longer needed. Launcher logs are in the Windows Temp folder, named `artemis-dashboard-<port>.log` and `artemis-dashboard-<port>-error.log`.

## What the display means

- Data comes from `outputs/mes_pilot/autonomous_paper_portfolios` plus the runner's configuration and evidence-correction registry. A fresh clone has no local trading results; no results are bundled here.
- Saved files refresh every seven seconds. The dashboard does not claim a fresh market quote or estimate unrealized profit when the runner has not saved a mark.
- The 70% win rate and 75% higher objective are targets, not achieved performance. Equity charts use completed trades recorded in the local ledger.
- Raw sessions and qualified sessions are distinguished using the runner's evidence rules and corrections. If those modules are unavailable, qualified counts are not shown. Diagnostics and synthetic tests are not forward paper evidence.
- The server accepts read-only requests on loopback only. It has no order controls and does not write the runner's files. Keep results, credentials, and market data local; publishing the code on GitHub does not publish or host the running dashboard.
