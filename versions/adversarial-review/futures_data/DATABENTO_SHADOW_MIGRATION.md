# Databento MES/MNQ Shadow Migration

Status: offline recorder boundary implemented; provider enrollment and network
activation intentionally pending.

The new `databento_shadow_recorder` is a data-only, headless candidate primary
source. It requests CME Globex `GLBX.MDP3` `ohlcv-1m` data for the `MES.FUT` and
`MNQ.FUT` parent symbols through an injected transport. It cannot access an
account, place an order, sign a request for trading, or grant trading authority.

## Promotion sequence

1. Offline normalization, replay-window, single-writer, chain-integrity,
   revision-conflict, lane-isolation, and authority tests must pass.
2. The owner separately creates a data-only account, accepts applicable CME
   agreements, and chooses the desired data plan.
3. A dedicated revocable API key is enrolled through
   `scripts/enroll_databento_historical_credential.ps1`, which uses a hidden
   Windows SecureString prompt and owner-bound DPAPI. Ciphertext is stored at
   `%LOCALAPPDATA%\Hermes\Databento\es-nq-historical\credential.dpapi` with
   inherited permissions removed. The key must never enter the repository,
   command line, environment file, logs, reports, or Obsidian.
4. A bounded connectivity probe requests no more than five finalized minutes
   for MES and MNQ and validates exact timestamps, symbols, OHLCV, and finality.
5. A seven-session shadow comparison runs beside NinjaTrader. Both sources are
   retained independently; neither is silently merged or allowed to influence
   orders.
6. Promotion requires complete source uptime, successful restart replay,
   explicit rollover handling, deterministic reconciliation, zero unexplained
   gaps, and an owner-reviewed evidence report.

Databento documents up to 24 hours of intraday replay for a live session. The
recorder therefore fails closed when its stored head is older than that limit;
historical recovery must use a separately authorized and independently retained
historical request. Recovered records are never inserted behind an existing
immutable chain head.

NinjaTrader remains the secondary visual comparison source during the trial.
Existing BTC, canonical strategy, risk, paper execution, and live-execution
boundaries are unchanged.

The initial proof uses the account's historical, usage-based service for bounded
post-session recovery and reconciliation. It does not require or imply purchase
of the Standard live-data subscription. A separate owner decision is required
before any paid live plan is activated.

`databento_ninjatrader_reconciliation.py` is the offline comparison boundary.
It authenticates the NinjaTrader daily chain, validates exact decimal OHLCV,
rejects records outside the declared UTC archive date, records input hashes,
and classifies matching, missing, and conflicting minutes. Databento recovery
candidates remain noncanonical and no cross-source merge is performed.
