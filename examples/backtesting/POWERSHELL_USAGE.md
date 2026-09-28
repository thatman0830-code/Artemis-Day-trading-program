# Offline backtest example

From the repository root in PowerShell:

```powershell
.\scripts\run_backtest.ps1 `
  -Data .\examples\backtesting\dataset_manifest.json `
  -Config .\examples\backtesting\backtest_config.json `
  -Output .\outputs\synthetic-example
```

Add `-Overwrite` only when intentionally replacing that exact output directory.
Use `python -m backtesting validate ...` or `inspect ...` for validation and
manifest inspection. This synthetic fixture intentionally requests no setups;
it demonstrates reproducibility and file contracts, not profitability.

## Phase 7B canonical examples

The checked-in canonical fixtures contain complete 1M prior-day warm-up and
the required 1M/5M streams. They use no prebuilt strategy facts:

```powershell
python -m backtesting validate `
  --data .\examples\backtesting\canonical_trade\dataset_manifest.json `
  --config .\examples\backtesting\canonical_trade\backtest_config.json

.\scripts\run_backtest.ps1 `
  -Data .\examples\backtesting\canonical_trade\dataset_manifest.json `
  -Config .\examples\backtesting\canonical_trade\backtest_config.json `
  -Output .\outputs\phase7b-canonical-trade `
  -Overwrite
```

Replace `canonical_trade` with `canonical_zero` for the genuine zero-setup
case. `create_phase7b_fixtures.py` deterministically regenerates both local
fixtures. These examples are historical paper simulations only; the profitable
synthetic path is a contract test, not evidence of future performance.
