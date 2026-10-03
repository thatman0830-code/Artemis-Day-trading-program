# Artemis — current implementation handoff

Updated October 2, 2026. This file describes the active paper implementation in this branch. The original [master PDF and Claude Code XML](docs/implementation_handoff/README.md) remain design inputs; read them together with this current state and the versioned configuration before making changes.

## Active implementation

- `scripts/start_mes_paper_pilot.ps1` launches `live-portfolios` through `scripts/run_mes_paper_pilot.py`.
- One read-only MES market-data feed supplies three synthetic $100,000 books. They compare **risk sizing policies on one strategy**, not independent strategies.
- The initial floor is $97,000 per book and trails intraday liquidation-side equity. The reserve is $200. Contract caps are 1/2/3 MES; per-trade budgets are $100/$200/$300 and daily stops are $150/$300/$450. See [the complete settings](docs/MES_THREE_PAPER_PORTFOLIOS.md).
- Live order routing is disabled. Prop execution remains manual. Paper evidence must precede any separately approved promotion.
- The 70–75% win-rate goal, the separately reported source-engine benchmark, and this bot's measured results must remain distinct.

The production portfolio baseline and the complete context repair are included here. The repair was reviewed in the scheduled runner as `13ae1ad` and integrated into the GitHub history as `039c7b5`. The separate research checkout's static-floor strategy variants are not part of this implementation and must not silently replace the scheduled runner.

## October 2 repair and evidence

The repair bridges archived context to native MES history and intraday replay, excludes incomplete timeframe candles, and blocks new entries when required context is incomplete. Context replay cannot retrospectively execute orders or reset persisted risk. Reports count unique eligible trading dates and apply durable, append-only evidence corrections. The dashboard shows raw versus qualified sessions and the precise setup rejection reasons.

See [repair details and known limits](docs/MES_CONTEXT_READINESS_REPAIR_2026-10-02.md). At this update:

- **Observed original session:** zero trades in each book. Missing context disqualifies the October 2 session from forward evidence; the original ledgers remain unchanged. Raw sessions: 1. Qualified sessions: 0.
- **Diagnostic replay:** complete context restores displacement for the recorded C1 opportunity, but efficiency is 0.306 against a 0.35 minimum. It still produces no trade. No threshold was loosened.
- **Synthetic test:** one shared signal exercises 1/2/3 MES paper fills, restart reconciliation, exits, fees and P&L. These fills are not performance evidence.
- **Provider check:** the existing account retrieved 6,900 MES minute bars at a quoted cost of $0.00 and observed replay completion. This is an adapter check, not a completed forward session or a promise about another account's entitlements.
- **Tests:** 335 MES tests passed in the scheduled runner. In this GitHub-compatible checkout, 329 passed and 6 were skipped because the local data/evidence artifacts are not distributed with the source. The full legacy repository suite was not rerun for this publication.

## Dashboard and local operation

The [Artemis dashboard](dashboard/PAPER_DASHBOARD_README.md) is a local, read-only view of the runner's configuration and output files. It does not launch trading, submit orders, or change risk settings. Point it at the actual runner root; a fresh clone has no recorded account results.

Publishing these files does not change the existing Windows scheduled task or its working folder. At the last local check, that task was enabled and Ready for Monday October 5 at 08:50 ET / 05:50 Arizona. A fresh installation must configure its own Python environment, Databento read-only access, historical context, current event calendar, and local scheduler. Keep credentials out of Git. Do not start a duplicate runner against the same account state.

## Next validation milestone

Inspect the first open-market paper run after the repair: completed history-to-live handoff, complete required timeframes/session levels, fresh quotes, calendar coverage, persisted risk/position state, and consistent per-book reports. If there is no trade, use the recorded setup and risk reasons; do not force entries to increase the sample.

Build sufficient fresh forward evidence before judging win rate, net expectancy after costs, drawdown, or portfolio ranking. Fees, slippage and margin remain provisional inputs requiring measurement; synthetic account settings are not verified prop-firm rules.

## Collaboration

Record the exact branch/commit, changes, test results, remaining limitations and next owner when handing work between Codex and Claude Code. Preserve local ledgers and unrelated BOT2 work. Keep exploratory strategy changes in a separate versioned research branch. This file is a shared record, not a live messaging channel or authorization for live orders.
