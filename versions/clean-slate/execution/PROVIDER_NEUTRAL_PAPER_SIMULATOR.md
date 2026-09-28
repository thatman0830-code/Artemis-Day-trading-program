# Provider-neutral ES/NQ paper simulator

The owned simulator is the paper-trading boundary for the three research profiles.
It starts each profile at USD 50,000, accepts completed non-authoritative trade
facts from a pluggable market-data/strategy adapter, and evaluates a fixed 15
active-session window. It writes an immutable JSON snapshot and a trade journal
under `outputs/provider_neutral_paper_trial/`.

The current publisher initializes the trial with zero sessions and no live feed.
Databento historical/replay data is the default research input; a live feed may
be added later without changing the ledger or profile rules. Hyperliquid remains
the separate BTC market-data lane. NinjaTrader is not an active dependency.

The snapshot is included in the Obsidian continuity backup. Every artifact is
comparison-only: no order submission, paper execution authority, live trading,
or trading authority is present. A profile is not selected from fewer than the
configured 15 sessions; the review compares net P/L, win rate, drawdown, fees,
and slippage using identical signal facts.
