# Master Operating Directive Alignment

The current directive source is the expanded 60-section version supplied on
2026-09-18 (SHA-256:
`2bc2d8bf1ebc93509bb4b503afc7d2609c8a1a8bfd716ec550257d80fc7c2939`). It
supersedes the earlier condensed wording while
preserving the same fail-closed operating intent.

This document maps the supplied AI Day-Trading Platform directive to the current
provider-neutral paper-trading system. It is an engineering control document,
not a trading signal source. It does not grant live authority.

## Already enforced

- Provider-neutral ES/NQ Databento supervisor with bounded recovery and fail-closed health state.
- Three $50,000 portfolios with paper execution permitted and live execution/trading authority disabled.
- Read-only cockpit aggregating feed health, coverage, portfolio state, baseline decisions, adaptive candidates, and authority.
- Five-session historical coverage gate and explicit no-signal accounting.
- Adaptive confirmation lane is comparison-only and cannot place or authorize orders.
- BTC recorder heartbeat, manifest integrity checks, scheduled-task verification, and recovery procedure.
- Forex Factory shadow trial with source hash, fixed trial dates, diagnostic association, non-authoritative scorecard, and no order influence.
- Atomic evidence writes, versioned schemas, deterministic tests, and Obsidian continuity backup.
- Legacy NinjaTrader watchdog dependency removed from the active operating path.
- Databento live capture uses continuous ES/NQ symbology with rollover mappings and
  records subscription diagnostics; expired quarterly symbols are not hard-coded.
- Validation matrix records dataset identity, model/strategy version, out-of-sample
  progress, required controls, and a fail-closed release gate.
- Readiness evaluator publishes GREEN/YELLOW/RED state without granting execution
  authority; current state is YELLOW while live samples and validation evidence are
  incomplete.
- Expanded directive requirements for state reconciliation, failure-injection
  testing, reproducibility, and change management are now tracked as explicit
  release gates rather than implied behavior.

## Gaps to close in priority order

### P0 — unattended-session continuity

The ES/NQ supervisor is currently a bounded worker. Add a small, independent
launcher/monitor that verifies cockpit freshness and restarts only after preserving
the prior health/error evidence. A restart must be followed by a fresh-bar and
authority verification; it must never blindly restart an unknown execution state.

### P0 — freshness and latency contract

Persist source, receive, processing, and decision timestamps for each live bar and
publish feed, processing, and end-to-end latency in the cockpit. Any stale or
out-of-order input must be marked and excluded from new paper decisions.

### P1 — incident and daily-review artifacts

Generate a daily operational report covering incidents, downtime, data gaps,
recovery attempts, stale inputs, rejected candidates, latency, and unresolved
actions. Preserve reports by date; never overwrite an earlier experiment.

### P1 — resource observability

Add CPU, memory, disk, network reachability, queue/backlog, and recorder-process
health to the cockpit. Resource observations are diagnostic only and cannot infer
market direction.

### P1 — quantitative decision ledger

For every accepted, rejected, vetoed, or no-signal candidate, persist probability,
expected value, volatility regime, assumed slippage/fees, risk fraction, drawdown
state, and model/strategy/data versions. Keep adaptive evidence separate from the
baseline ledger.

### P2 — portfolio risk analytics

Add rolling expectancy, profit factor, R-multiple distribution, drawdown duration,
correlation/exposure, risk-of-ruin scenarios, and fractional-Kelly reference values.
These are review metrics only; they must not automatically change policy or sizing.

### P2 — recovery and replay validation

After each incident, run a deterministic replay/backfill check, continuity check,
and focused regression suite before resuming the supervised session.

## Operating rule

Until the P0 controls are complete, the system remains supervised paper-only. No
directive section authorizes live trading, automatic policy changes, or use of news
as directional authority.

## Directive-derived release gates

The following are explicit prerequisites for any future authority change:

1. Databento (or an approved replacement) must produce current, timestamped ES/NQ
   records with freshness and ordering checks passing.
2. The baseline must complete the configured 15-session out-of-sample window with
   immutable dataset and strategy fingerprints.
3. Any adaptive, machine-learning, options, macro, or news lane must have its own
   dataset, model version, out-of-sample evidence, and controls; adding a section
   to this directive does not authorize it.
4. Readiness must be GREEN and the authority configuration must be independently
   reviewed. Until then, all non-baseline lanes remain comparison-only or review-only.
5. Restart, disconnect, stale-data, duplicate-data, out-of-order-data, and recorder
   failure drills must produce evidence before those recovery paths are considered
   validated.
6. Every meaningful change must retain version, reason, test result, deployment
   result, and rollback reference; a clean process exit is not proof of correctness.
