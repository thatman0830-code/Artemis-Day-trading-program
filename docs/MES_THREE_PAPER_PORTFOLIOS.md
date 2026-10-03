# MES three-portfolio paper pilot

The scheduled `scripts/start_mes_paper_pilot.ps1` now launches `live-portfolios`.
One read-only MES feed and one calendar supply three independent paper engines.
No order can reach a broker or prop platform. The strategy, signal identifiers,
session, event, spread, and cost assumptions are identical across the books.
Only the versioned risk settings differ.

| Paper book | Initial balance | Initial floor | Max MES | Per-trade cap | Capacity fraction | Daily stop |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conservative | $100,000 | $97,000 | 1 | $100 | 5% | $150 |
| Moderate | $100,000 | $97,000 | 2 | $200 | 10% | $300 |
| Aggressive | $100,000 | $97,000 | 3 | $300 | 15% | $450 |

These are **provisional synthetic paper settings** in
`config/mes_paper_portfolios_v1.json`, not a configured Apex account. The
paper execution reserve is $200 per book. The
intraday floor tracks peak liquidation-side equity, including open P&L and
estimated entry/exit fees, and never moves down. Touching the floor latches a
paper breach, closes open simulated positions at the next executable quote,
and blocks further entries. The paper books retain independent state across
restarts. A config change refuses to reuse old state; it requires a separately
named paper experiment rather than silently resetting an account.

Live quotes drive protective paper stops/targets between completed bars. The
archived bar-only replay cannot reconstruct every intrabar quote or exact
peak-equity sequence, so it must not qualify a prop account under these
trailing rules. Fee, spread, slippage, and margin values in the pilot config
are still placeholders pending measured platform values.

Results are under `outputs/mes_pilot/autonomous_paper_portfolios/` with one
ledger and report per book. `portfolio-comparison.json` checks that candidate
and terminal setup IDs match across books, and shows each book's results and
skip reasons. It compares **sizing policies**, not three strategies. A zero-
trade session is not repaired by increasing contract limits; investigate the
recorded setup and decision reasons before proposing a versioned strategy
change. No portfolio is promoted from the reported source-engine win rate.

The shared emergency control is:

```powershell
.venv\Scripts\python.exe scripts\run_mes_paper_pilot.py portfolio-kill-switch on --reason operator
```

Clearing it requires an explicit `portfolio-kill-switch off`. A breached
paper floor stays latched even after the shared switch is cleared. The
original single-account `live` command remains available for comparison,
but the scheduled launcher uses the three-account command.
