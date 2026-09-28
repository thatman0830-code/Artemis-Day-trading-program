# Owner Economic Input Template

Do not fill values from fixtures or observed performance. Every schedule needs a stable ID,
`effective_from`, optional exclusive `effective_to`, source/decision identity, approval timestamp,
and owner approval.

## ES and NQ, separately

- `OWNER_BROKER_COMMISSION`: basis (`PER_CONTRACT_PER_SIDE` or explicitly supported alternative),
  Decimal amount, currency, applicability.
- Research slippage: `ZERO`, `FIXED`, or `SCENARIO_SET`; entry, ordinary exit, forced exit, and
  rollover adverse ticks.
- Participation: entry, ordinary exit, forced exit, rollover rates in `[0,1]`.
- Risk: starting capital; gross/net exposure; per-position and per-market limits; session loss;
  drawdown; leverage; margin utilization; session-flatten buffer seconds.
- Account classification needed to select applicable CME fees. Do not enter broker credentials.

## BTC

- Explicit approved profile: `BTC_SPOT` or `BTC_LINEAR_PERPETUAL` only after evidence proves it.
- For spot: quote currency, valuation source, precision, fee schedule and tier.
- For perpetual: contract/notional convention, collateral/quote currency, precision, maximum
  leverage, margin mode/tier, mark/oracle/funding sources and histories, fee schedule/tier, and
  liquidation policy.

## Frozen choices requiring no further input

- Collision: adverse threshold wins; undefined ownership rejects.
- End of data: unresolved state fails; no fabricated or accounting-only liquidation.

Approval of a template is configuration approval only. It does not authorize trading or strategy
optimization, and every value changes the economic fingerprint.
