# Backtesting Engine Core v1

Core v1 is an offline, provider-neutral implementation of the architecture in
`GS_QUANT_INSPIRED_ARCHITECTURE.md`:

`Trigger -> Action -> Strategy -> CalculationEngine -> BacktestResult`

It is separate from data acquisition, recorders, brokers, wallets, and order submission. A strategy
receives only an immutable `Trigger` and `ReadOnlyState`; its only output is an immutable advisory
`Action`. The engine alone owns simulated orders, fills, positions, accounting, risk rejection, and
the result ledger.

## Frozen contracts

- `CoreBar` and `CoreEvent` carry market, instrument/contract, session, source, checksum, version,
  UTC time, and deterministic sequence lineage.
- Same-time events use the explicit `EVENT_PRIORITY` table and then market, instrument, sequence,
  and identity ordering.
- `VerifiedArchiveSlice` checks source hashes and publishes only bars closed by the point-in-time
  cursor. ES/NQ bars must match exactly one explicit active-contract window. It never creates a
  synthetic continuous contract or fills a gap.
- `StrategyRequirements` and `CapabilityReport` are mandatory pre-run facts. Missing volume,
  funding, rollover, markets, or order capabilities reject the run before evaluation.
- Market actions generated on bar `t` cannot fill on `t`. They first become eligible at the next
  valid tradable bar open, with adverse slippage. Volume participation bounds fills and permits
  deterministic partial fills. Ambiguous intrabar limit/stop execution fails closed.
- Instrument, commission, margin, tick, quantity-step, and slippage facts are immutable, versioned,
  effective-dated Decimals. Float economic inputs are rejected.
- The result contains deterministic event/order/fill/position/accounting ledgers and identities.
  Wall-clock runtime facts are excluded from `machine_json()` and its logical identity.
- Time partitions are market-specific TRAIN, VALIDATION, then untouched TEST intervals with explicit
  purge and embargo. There is no random split.

## Acceptance and safety

The result is advisory. Core v1 never authorizes trading. The research acceptance boundary requires
at least 200 finalized untouched out-of-sample trades per market; otherwise the result is
`INSUFFICIENT_EVIDENCE`. Higher-level evaluation retains the owner gates for win rate, net expectancy,
and planned R:R. Core v1 neither edits strategy rules nor chooses parameters.

Approved inputs are validated immutable archives and deterministic synthetic fixtures. Runtime
provider requests, credentials, live streams, brokerage APIs, and recorder control are inaccessible.

## Capability example

```python
report = CalculationEngine().preflight(strategy=strategy, archives=(btc, es, nq))
if not report.accepted:
    raise ValueError(report.issues)
```

## Deterministic result example

```json
{"advisory_acceptance":"INSUFFICIENT_EVIDENCE","dataset_fingerprints":["fixture"],"result_version":"core-v1-result-1","run_id":"synthetic-core-v1"}
```

This abbreviated example illustrates the stable identity fields; the machine result also contains
the complete immutable ledgers and calculation facts.
