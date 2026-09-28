# Backtesting Engine Core v1 Adversarial Audit

Audit date: 2026-08-27  
Disposition after schema remediation: **ES/NQ read-only smoke ready**; BTC is validated only as
`PARTIAL_RESEARCH_ONLY`. The core remains fail-closed and offline.

## Corrections made

The audit proved and corrected these local defects:

1. Capability overstatement: limit/stop execution, BTC funding, futures rollover execution, and
   end-of-test flatten were advertised without complete implementations. They now reject at
   capability/preflight boundaries. Market orders are the only executable Core v1 order type.
2. Cross-market visibility: a strategy could receive previously processed bars from another market.
   Views and source event identities are now scoped to the current market and instrument, and a
   strategy is invoked only for declared markets.
3. Data-quality ordering: a bar carrying an explicit missing-interval marker could still fill or
   create an order. It now emits `DATA_QUALITY_HALT` and rejects same-bar actions and fills.
4. Reversal accounting: a fill crossing through zero retained the old average price. The residual
   reversed position now starts at the reversal fill price.
5. Instrument validation: market/effective-date compatibility and price tick grids are now checked
   before simulation state changes.
6. Fingerprint coverage: immutable archive hashes/windows, instrument specifications, calendar and
   rollover fingerprints, split identity, seed, schemas, execution, risk, and configuration now feed
   the logical result identity. Runtime remains excluded.
7. Decimal leakage: empty accounting sums now begin with `Decimal("0")`, not integer zero.
8. Event evidence: signal evaluation, mark-to-market, risk, order submission, and explicit gap-halt
   events are emitted with deterministic ordering and lineage.

## Confirmed synthetic invariants

- Frozen dataclasses prevent direct strategy mutation of views and records.
- Strategy views contain only finalized bars (`close_time <= event_time`) in the current scope.
- A signal on bar t cannot fill on bar t; a market order first uses the next eligible bar open with
  directionally adverse tick-based slippage.
- Non-tradable and missing-interval bars cannot fill. Volume participation bounds fills.
- Identical simulations produce byte-identical `machine_json()` and result identity.
- Risk rejection precedes order/position mutation and has stable reason codes.
- Futures bars retain exact contract identity and must match exactly one active-contract window.
- Chronological TRAIN/VALIDATION/TEST definitions reject overlap after purge/embargo.
- Fewer than 200 untouched OOS trades per market remains `INSUFFICIENT_EVIDENCE`.
- Static inspection found no provider/network, external order-submission, wallet, signing, or
  private-key path in `backtesting/core_v1`.

## Archive-adapter readiness

| Market | Retained evidence | Core v1 readiness | Reason |
|---|---|---|---|
| BTC | Completed manifest-bound 1m slice | PARTIAL SMOKE ONLY | Checksum and boundary validate; training/OOS/final eligibility remain false. |
| ES | Complete promoted Pass B v3 chain | READY FOR READ-ONLY SMOKE | Entire plan/checkpoint/raw/normalized/calendar/rollover chain validates. |
| NQ | Complete promoted Pass B v3 chain | READY FOR READ-ONLY SMOKE | Entire plan/checkpoint/raw/normalized/calendar/rollover chain validates. |

Read-only evidence hashes:

- Pass B plan manifest: `ac4606816f9b20bfe159eb5f9bf6f86ffa9cd798d3be99707947e49691c8e899`
- Final ES/NQ archive audit: `a1a122c3c09aa4d9e09047014c89a9cfd4b47abcc3fba06c6bb193e27dc75485`
- BTC partial manifest: `3165b81a8ff14870162c03b43a70bb8f4a1909defb3ed9900b3a959468cfc16c`

No archive or collector file was written during this audit.

## Known limitations / blocked behaviors

- Production adapters now exist. BTC remains partial-evidence-only; no final BTC dataset is claimed.
- Limit, stop, gap-through-stop, stop/target collision, cancellation, expiry, forced flatten,
  explicit rollover close/reopen, funding application, session-loss limits, drawdown-forced actions,
  and margin reservation/release are not implemented. Unsupported capabilities fail closed.
- The engine fingerprints but does not consume a `SplitPlan`; production adapters must enforce row
  membership and state reset/carry rules.
- OOS trade attribution is deliberately zero until final-trade and split ownership are integrated;
  therefore Core v1 cannot pass the research acceptance gate.
- Accounting is derivative-style cash plus PnL. BTC spot accounting is not claimed. Funding is unavailable.
- Per-market attribution and comprehensive session/rollover/funding event ingestion are pending.

These limitations do not authorize a strategy study.

## Verification

- Focused Core v1 adversarial suite: 22 passed.
- Complete backtesting package: 171 passed.
- Full offline repository suite: 1,112 passed.

All tests were local/offline and synthetic. No provider, credential, recorder, scheduled collector,
broker, exchange, wallet, signing, paper-trading, or live-trading path was used.
