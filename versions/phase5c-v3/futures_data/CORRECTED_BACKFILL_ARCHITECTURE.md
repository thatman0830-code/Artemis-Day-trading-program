# Corrected ES/NQ Two-Pass Historical Backfill

Status: executable design and offline-tested infrastructure; neither pass has
been executed. Frozen plan: `data/backtests/es_nq_rollover_discovery_plan_3`.

## Frozen scope

- Metadata as-of: `2026-08-26T20:44:47.227112Z`.
- Nominal two-year cap: `2024-08-25T20:44:47.227112Z` through the as-of.
- Evidence-supported metadata start: `2025-06-01`; earlier retained point-in-time
  responses are empty, so the system does not invent the missing chain.
- Finalized-history end: `2026-08-26` exclusive. The session forming at the
  as-of is not presumed complete.
- Policy: `OWNER_TWO_SESSION_VOLUME_CROSSOVER_V1`.
- Session exclusions: `OWNER_CME_ROLLOVER_CALENDAR_V1`. Any unmodeled holiday or
  early-close conflict fails closed during data validation.

Eligible chains are:

- ES: `ESM5, ESU5, ESZ5, ESH6, ESM6, ESU6`.
- NQ: `NQM5, NQU5, NQZ5, NQH6, NQM6, NQU6`.

The chains use provider lifecycle and settlement years to resolve one-digit
ticker years. Exact metadata observations are deduplicated while every source
response SHA-256 remains in each contract's provenance. Contracts after the
front contract at the frozen as-of are excluded as `FAR_FUTURE`; spreads/combos,
micros, options, continuous/synthetic symbols, malformed tickers, and unrelated
roots never enter either chain.

## Fixed metadata inventory

| Market | Eligible | Far-future exclusions | Spread/combo observations | Unsupported nominal history |
|---|---:|---:|---:|---|
| ES | 6 | 20 | 80 | 2024-08-25 through 2025-06-01 |
| NQ | 6 | 11 | 40 | 2024-08-25 through 2025-06-01 |

The unsupported interval is explicit missing evidence, not a fabricated gap or
an entitlement claim.

## Pass A — rollover discovery

Each of five consecutive pairs per market receives a five-ordinary-session
overlap ending before the outgoing contract's last-trade session. Both exact
contracts are requested, yielding two bounded requests per pair. Finalized
one-minute volume is summed into immutable daily-volume facts.

The first session completing two consecutive sessions where incoming volume is
strictly greater than outgoing volume freezes the decision. The new contract is
effective on the next planned tradable session. Equality resets the sequence.
If crossover is absent, the penultimate overlap session freezes a calendar
fallback effective on the last overlap session, still before the outgoing
last-trade session. Missing fallback evidence is ambiguous and fails closed.
Later data cannot move an earlier decision.

| Market | Pairs | Requests | Rows | Raw estimate | Normalized estimate | Minimum duration |
|---|---:|---:|---:|---:|---:|---:|
| ES | 5 | 10 | 69,000 | 14,007,000 B | 15,525,000 B | 3 min |
| NQ | 5 | 10 | 69,000 | 14,283,000 B | 15,525,000 B | 3 min |
| Combined | 10 | 20 | 138,000 | 28,290,000 B | 31,050,000 B | 5 min |

These are hard request/row bounds for the frozen plan. Response-size or
pagination beyond the plan fails closed.

## Pass B — active-contract history

Only validated Pass A decisions can create Pass B. Consecutive decisions form
non-overlapping `[start, end)` active windows with exactly one contract per
market/session. Each request and row retains its individual contract identity.
No price adjustment or continuous symbol is produced.

Provisional estimates use one active contract and weekday/session facts; final
request boundaries are generated only after Pass A:

| Market | Sessions | Requests | Rows | Raw range | Normalized | Minimum duration |
|---|---:|---:|---:|---:|---:|---:|
| ES | 322 | 65 | 444,360 | 79,984,800–115,533,600 B | 99,981,000 B | 17 min |
| NQ | 322 | 65 | 444,360 | 79,984,800–115,533,600 B | 99,981,000 B | 17 min |

Uncertainty remains for holidays/early closes, zero-volume minutes, provider
pagination, compressed/raw bytes, genuine gaps, aggregate entitlement, and the
roll decisions themselves.

## Transaction and recovery contract

`RequestStore` retains raw response bytes before parsing. A pending record binds
the raw checksum; normalized daily facts, a final manifest, and an atomic
checkpoint follow only after validation. Resume reuses a checksum-verified
raw/pending transaction without another provider request, or skips a completed
request only when raw, normalized, manifest, and checkpoint identities verify.
Partial, conflicting, or pre-existing unverified files fail closed. ES and NQ
use separate subtrees.

The runner performs no automatic retry, spaces real calls by at least 15
seconds, retains partial successful work, honors the owner stop marker between
requests, and atomically promotes staging only after all Pass A inputs,
decisions, and Pass B windows validate. It has no brokerage, account, wallet,
signing, order, or recorder capability.

Owner controls prepared but not executed:

- Secure hidden prompt: `scripts/enter_massive_es_nq_rollover_discovery_key.ps1`
- Status: `scripts/get_es_nq_rollover_discovery_status.ps1`
- Graceful stop: `scripts/stop_es_nq_rollover_discovery.ps1`

## Gates between passes

Pass B remains unavailable unless all gates pass:

1. Every planned Pass A raw body and normalized daily-volume file verifies.
2. Every response is exact-contract, in-window, finalized, unique, ordered, and
   free of pagination/schema/size conflicts.
3. Each pair yields either the first two-session crossover or a complete
   calendar fallback; ambiguous evidence is rejected.
4. Decisions are chronological, point-in-time, identity-compatible, and become
   effective no earlier than the following tradable session.
5. Active windows cover the evidence-supported interval exactly once, without
   gap or overlap.
6. The final Pass B plan is immutable, checksummed, and separately reviewed by
   the owner before any Pass B download.

Pass A completion is not permission to start Pass B, a continuous recorder, a
backtest, or trading. Market acceptance still requires at least 200 finalized
untouched out-of-sample trades per market.
