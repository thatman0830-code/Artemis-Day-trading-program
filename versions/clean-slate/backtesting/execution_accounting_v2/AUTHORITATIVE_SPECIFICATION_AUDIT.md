# Authoritative Economic Specification and Implementation-Readiness Audit

Audit date: 2026-08-27 UTC. This is not a production economic profile and authorizes no replay.

## Frozen owner decisions

- `CONSERVATIVE_OHLC_1M_V1` retains adverse-threshold collision resolution. When adverse ownership
  is not defined, the result is `AMBIGUOUS_INTRABAR_REJECTED`.
- End-of-data residual orders or positions fail the run. No terminal fill and no accounting-only
  liquidation are permitted.

## ES and NQ findings

Current first-party CME rules establish ES as Chapter 358 / commodity code ES and NQ as Chapter 359 /
commodity code NQ. Both are USD cash-settled index futures in integer contracts. ES is USD 50 per
index point with a 0.25-point/12.50-dollar outright tick. NQ is USD 20 per point with a
0.25-point/5.00-dollar outright tick.

The repository has verified individual-contract market data, retained schedules, and rollover facts,
but the earlier CME trading-hours retrieval retained no official calendar content. Current product
rules do not prove every historical holiday/session boundary. Existing provider schedules remain
data provenance, not a replacement for exchange-authored calendar evidence.

CME states that clearing performance bonds vary over time and offers historical PDFs. Exact
effective-dated ES/NQ initial and maintenance clearing requirements covering the archived interval
were not retained. These must remain distinct from any broker customer margin.

CME fee publications are participant-, venue-, and program-dependent. Available first-party pages
prove the structure, but do not establish the owner's applicable classification or complete interval.
No broker commission fact exists. Production ES/NQ eligibility therefore includes the mandatory
`MISSING_BROKER_COMMISSION_SPEC` gate.

## Execution assumptions and risk

Slippage and volume participation are explicitly research assumptions. Schemas support zero, fixed,
and scenario-set adverse tick slippage and separate entry, ordinary-exit, forced-exit, and rollover
participation. No production values were selected. Synthetic fixtures are labeled
`SYNTHETIC_TEST_ONLY` and can never pass production eligibility.

The risk schema requires effective-dated starting capital, gross/net exposure, instrument/market
limits, session loss, drawdown, leverage, margin utilization, flatten buffer, and rollover
participation. None are guessed. Missing fields fail closed through stable reason codes.

## BTC classification

The retained manifest checksum was independently recomputed. It identifies public Hyperliquid
mainnet candles and symbol `BTC`, but lacks an immutable request body and matching perpetual or spot
metadata identity. Current Hyperliquid documentation says perpetual and spot candle identities differ,
but current documentation cannot retroactively supply missing archive lineage.

The archive contains OHLCV candle streams only. It does not retain synchronized oracle prices, mark
prices, funding rates/payments, margin tier versions, user margin mode, maximum leverage history, or
fee schedule/tier versions. BTC remains `BTC_UNKNOWN_UNSUPPORTED`; perpetual accounting, funding,
margin, and liquidation replay are disabled.

A separately approved historical evidence collector/backfill would need to preserve, at every
applicable timestamp, perpetual universe metadata, asset precision, margin tables/tiers, mark and
oracle prices, funding history/payments, fee schedule version and applicable user tier, plus request
and response manifests with checksums. Candles cannot reconstruct these facts.

## Neutral infrastructure implemented

The additive `backtesting.execution_accounting_v2` package contains immutable evidence and
specification records, UTC half-open effective-date resolution, deterministic SHA-256 economic
fingerprints, capability gates, stable missing-specification reasons, synthetic-only validation, and
production eligibility reporting. It contains no fill, PnL, margin, strategy, provider, archive,
credential, recorder, or order-submission implementation.

Mixed v1/v2 ledgers fail with `MIXED_LEDGER_VERSION`. Core v1 is untouched and independently runnable.

## Remaining blockers

### Authoritative facts still missing

- Effective-dated ES/NQ historical CME clearing initial and maintenance performance bonds.
- Complete applicable CME exchange, clearing, and regulatory fee components by effective interval
  and owner account classification.
- Exchange-authored historical session/calendar material for all evaluation dates.

### Owner choices still missing

- `OWNER_BROKER_COMMISSION` schedule.
- Slippage mode/rates and sensitivity set; four participation limits.
- Starting capital and every required risk, exposure, leverage, utilization, loss, drawdown, flatten,
  and rollover limit.

### Historical evidence still missing

- Proven BTC spot/perpetual universe identity and precision history.
- BTC oracle, mark, funding, margin-tier, leverage/mode, fee-schedule and owner-tier histories.

### Mechanically implementable work remaining

- Phase 1 integration of these contracts into a v2-only configuration reader and schema validator.
- Schema example generation, manifest signing/checksum verification, and public eligibility CLI.
- Later order/execution/accounting phases remain unauthorized.

The neutral contracts are implementation-ready, while all production economic profiles remain
ineligible until their exact facts and owner values are supplied.
