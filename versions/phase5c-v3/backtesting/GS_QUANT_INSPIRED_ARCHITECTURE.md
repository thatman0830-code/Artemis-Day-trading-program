# Provider-Neutral Quantitative Simulation Architecture

Status: design only. This document adds no dependency on `gs-quant`, Goldman
Sachs APIs, services, models, or credentials. It adapts the requested GS
Quant-style separation of concerns into repository-owned immutable contracts:

```text
Trigger -> Action -> Strategy -> CalculationEngine -> BacktestResult
```

It does not modify market-data ingestion and does not implement a simulation
engine.

## Boundaries and dependency direction

Historical datasets remain immutable upstream facts. Triggers observe only
facts visible at their point-in-time boundary. Actions describe simulated
intent, Strategy maps eligible triggers to actions through frozen Trading Brain
interfaces, CalculationEngine validates capabilities and resolves simulation
facts, and BacktestResult aggregates immutable outputs. Results and analytics
never feed back into Strategy, triggers, risk authorization, or execution.

Each run freezes dataset fingerprints, strategy/configuration identities,
instrument metadata, roll/funding/cost/margin policies, engine version,
random-seed identity, partition/fold definitions, and UTC/account-timezone
conventions. Missing capability or lineage fails closed before replay.

## Triggers

- **Periodic:** deterministic UTC clock boundaries, daily accounting snapshots,
  funding timestamps, partition/fold boundaries, and reporting intervals.
- **Session:** CME open, maintenance break, close, holiday, early close, and
  contract-last-trade boundaries; BTC remains 24/7 with exchange-defined candle
  boundaries.
- **Market:** finalized candle availability, price touch, liquidity observation,
  spread/volume update, and strictly point-in-time higher-timeframe close.
- **Risk:** simulated margin threshold, exposure limit, stale-data veto, missing
  protective fact, and owner-authored research stop conditions. These are
  simulation facts, not live authorization.
- **Rollover:** explicit immutable current/next-contract eligibility and a
  versioned fixed-date or point-in-time volume-crossover decision.
- **Data quality:** duplicate, gap, overlap, schema drift, checksum conflict,
  stale stream, non-final candle, or unavailable required timeframe.

Every trigger has a deterministic identity, observation time, availability
time, source/version lineage, and scope. Future facts cannot create or revise an
earlier trigger.

## Actions

The action vocabulary is simulation-only: `ENTER`, `EXIT`, `REDUCE`, and
`CANCEL`. An action records instrument/contract identity, side, requested
quantity, immutable limit/stop/target facts where applicable, creation time,
eligibility time, strategy/setup lineage, and reason. It cannot submit an order,
access an account, sign a payload, or authorize risk.

Partial fills create child facts that conserve requested quantity. Cancel and
reduce actions cannot erase prior fills. Futures rollover exits and replacement
entries remain distinct economic actions; they are never hidden by a synthetic
continuous price series.

## Strategy

Strategy is a read-only adapter over the frozen Trading Brain public contract.
It consumes validated visible market facts and emits canonical qualification,
entry, sizing, protective, exit, cost, lifecycle, and accounting facts only
through approved interfaces. It cannot inspect future candles, analytics,
portfolio results, or test-partition outcomes. Parameter sensitivity uses
separately locked owner-authored configurations and never mutates the canonical
strategy automatically.

## CalculationEngine

Before replay, the engine publishes a capability manifest and rejects a run if
it cannot model every required feature. Capabilities include:

- exact Decimal price, quantity, tick, multiplier, and currency arithmetic;
- commissions, bid/ask spread, adverse slippage, latency, and partial fills;
- initial/maintenance margin and deterministic simulated margin events;
- BTC funding at explicit timestamps when a versioned source/model exists;
- ES/NQ individual-contract CME sessions and immutable roll decisions;
- stale-data and unresolved-gap handling without interpolation;
- canonical #29 execution, lifecycle, cost, accounting, and analytics adapters;
- deterministic checkpoint/replay and idempotent event processing.

Unsupported funding, margin, spread, latency, fill, or roll behavior is an
explicit `UNSUPPORTED_CAPABILITY` result—not silently zero or a favorable
assumption.

## Portfolio and accounting snapshots

At every action/fill/funding/roll/accounting boundary, the engine emits an
immutable snapshot containing cash by currency, positions by exact contract,
average/economic entry, realized and unrealized PnL, accrued costs/funding,
margin used/available, exposure, protective facts, event lineage, and prior
snapshot identity. ES, NQ, and BTC scopes remain separately attributable even
when an explicitly versioned portfolio view is later requested.

Snapshots never mutate account equity outside the simulation, and accounting
does not infer missing prices, costs, funding, or FX rates.

## BacktestResult and computational audit

The result binds the run/dataset/configuration/engine identities; input/output
fingerprints; ordered trigger/action/event counts; rejected, unresolved, and
unsupported facts; fill and cost decomposition; portfolio snapshots; closed
trade accounting; analytics snapshots; checkpoints; and deterministic replay
identity.

Computational audit metrics include event counts by phase, no-look-ahead
violations (required zero), duplicate/idempotent replay counts, gap/stale vetoes,
partial-fill and cancellation counts, roll decisions and evidence, latency and
slippage distributions, commission/spread/funding totals, margin utilization,
runtime and peak memory, checksum verification, and model-capability coverage.

## Market-specific modeling

- **BTC:** 24/7 closed-candle visibility, explicit venue tick/quantity rules,
  versioned commission/spread/slippage/latency models, partial fills, and
  cryptocurrency funding only when timestamped canonical inputs exist.
- **ES/NQ:** individual XCME quarterly contracts, America/Chicago sessions plus
  UTC event time, maintenance/holiday/early-close facts, contract multipliers,
  commission/spread/slippage/latency/margin models, and explicit point-in-time
  rollover. Continuous series may be derived for analysis only from recorded
  roll facts and never substitute for execution prices.

## Scientific evaluation

Dataset/configuration locks precede chronological train, validation, and final
untouched test partitions. Walk-forward folds are immutable. Regime labels are
descriptive only. Multiple testing and parameter sensitivity are recorded, and
95% confidence intervals accompany win rate, expectancy, and relevant returns.

BTC, ES, and NQ are evaluated separately. An owner-facing evidence gate remains
advisory and requires at least 200 finalized untouched out-of-sample trades per
market, plus the frozen win-rate, net-expectancy, and planned-R:R requirements.
Calendar days, bars, folds, or combined markets cannot substitute for that
trade count. No result authorizes live or paper order submission.

