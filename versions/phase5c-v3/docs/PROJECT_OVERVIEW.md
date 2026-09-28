# Provider-Neutral ES/NQ Quantitative Trading Platform

## What this project is

This project is a research and paper-trading platform for systematic day-trading research on the E-mini S&P 500 (ES) and E-mini Nasdaq-100 (NQ) futures markets. It combines market-data collection, strategy research, deterministic backtesting, risk controls, paper-trial accounting, and operational monitoring in one owner-controlled Python system.

The goal is not to copy a public trader or depend on a hosted journal. The goal is to build an auditable software product whose assumptions, data, risk rules, and results can be inspected and improved over time.

## How it works

```text
Market data
    -> normalization and validation
    -> feature and regime research
    -> baseline and experimental comparison lanes
    -> three-profile paper simulator
    -> decision ledger and analytics
    -> review, validation, and controlled promotion gates
```

The system is provider-neutral. Databento is the primary ES/NQ data path under evaluation, while Rithmic Paper Trading is isolated as a possible alternative connectivity and quote-validation source. NinjaTrader is retained only as archived diagnostic evidence.

## Strategy research

The platform keeps strategy ideas separate from execution authority. The current research package contains six ES/NQ hypotheses:

- Opening-range continuation
- Failed opening-range breakout
- Trend pullback and resumption
- Auction rejection versus acceptance
- Compression expansion
- Multi-timeframe sweep to equilibrium

Each module is marked `research_only`. A research result cannot become an order simply because it looks promising. It must pass clean-data checks, realistic cost assumptions, walk-forward testing, Monte Carlo stress, and human review.

## Paper-trading design

The simulator uses three identical-data risk profiles:

- Conservative
- Moderate
- Aggressive

Each profile starts with a $50,000 research balance. The profiles are compared on the same signals and market data so that risk-profile differences are not confused with different trade selection. Results are non-authoritative until the required sample, data-quality, and validation gates pass.

## Safety and integrity controls

The platform is designed to fail closed:

- Live trading is disabled.
- Trading authority is disabled.
- Research modules cannot submit orders.
- Stale, missing, or unsynchronized market data blocks the simulator.
- Hard daily-loss, drawdown, exposure, leverage, and feed-latency limits are enforced as controls.
- Duplicate-order and reconciliation protections are part of the architecture.
- The decision ledger distinguishes `TAKEN`, `SKIPPED`, and `VETOED` decisions.
- Unknown strategy details remain unknown rather than being filled in by inference.

## Analytics and records

The local cockpit records:

- Data freshness, mapping, latency, and hash evidence
- Decision and signal lifecycle evidence
- Profile-by-profile paper results
- Plan adherence and execution-quality review fields
- Regime, session, symbol, and lane breakdowns
- Fail-closed TraderSync-style analytics
- BTC research-recorder health
- Forex Factory shadow-trial coverage
- Obsidian continuity backups

The analytics layer reports insufficient samples honestly. It does not manufacture win rates, profit factors, or what-if results when completed outcomes do not exist.

## Current phase

The software is in controlled research and paper-readiness validation. The research package has been hash-pinned and incorporated into a comparison-only catalog. The six-module comparison runner is installed, but the current ES/NQ live-data gate remains closed until a synchronized, hash-valid capture contains current samples for both markets.

That means the project is operationally safe, but it is not being represented as live trading and no real-money performance claim is being made.

## Roadmap

1. Qualify a fresh synchronized ES/NQ market-data capture.
2. Run the six research modules in comparison-only replay.
3. Complete the bounded three-profile paper-trading trial.
4. Review robustness, adherence, slippage, drawdown, and regime dependence.
5. Promote only a human-approved, validated profile to a separately controlled next phase.
6. Continue improving the platform as a sellable, provider-neutral software product.

## Plain-English summary

> I’m building an owner-controlled quantitative trading research platform for ES and NQ. It collects and validates market data, tests rule-based strategies, compares three risk profiles with simulated $50,000 accounts, records every decision, and blocks execution whenever the data or controls are not good enough. The current focus is proving the research and paper-trading pipeline before any discussion of live trading.

## Important disclaimer

This is a software research project, not a promise of trading profits or financial advice. Historical, simulated, or paper results do not guarantee future performance. No module is approved for live trading by this document.
