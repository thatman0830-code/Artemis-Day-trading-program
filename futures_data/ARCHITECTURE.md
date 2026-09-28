# ES/NQ Futures Data Phase 1

This package is market-data infrastructure only. It cannot authorize or execute
trades and exposes no account, order, wallet, signing, or broker capability.

## Boundary and flow

`FuturesDataProvider` supplies point-in-time contract discovery/specifications,
schedules, and finalized one-minute pages. `MassiveFuturesProvider` implements
that boundary over an injected transport, allowing strict offline mocks now and
another adapter (for example Databento) later without changing validation,
rollover, archive, or backtest consumers.

Raw ingestion always uses individual ES or NQ outright contracts. Continuous
series are derived later from immutable `RollDecision` facts. The unadjusted
stitch is canonical; an adjusted series would need a separate method/version.

All economic values are `Decimal`; timestamps are UTC-aware while provider
timestamps and America/Chicago trading dates remain explicit. Session gaps are
classified as open, maintenance, weekend, holiday, early close, legitimate
no-trade, or unexplained. Missing bars are never synthesized.

## Archives and recovery

The compatible isolated paths are `data/backtests/es_forward_archive_1` and
`data/backtests/nq_forward_archive_1`. Commits use a single-writer lock, fsynced
temporary files, atomic replacement, deterministic JSONL, SHA-256 verification,
and immutable manifest/supersession lineage. BTC archives are outside this
package and must never be passed to it.

## Massive free-tier boundary

Phase 1 assumes no more than four calls/minute, bounded exponential backoff with
jitter, `Retry-After`, persistent request/cursor facts, and a hard failure
budget. Delayed/stale availability is research-only. The owner must confirm
Massive licensing, raw-response retention rights, entitlement, availability
delay, and any free-tier historical-depth limits before credential entry.
Nothing here creates an account, upgrades a plan, or performs a real request.

## Dry run and future credential workflow

First construct `create_backfill_plan(...)` from an already reviewed contract
list. It is always marked `dry_run_only` and `licensing_confirmation_required`,
limits the interval to two years, and reports calls, rows, storage, duration,
paths, and abort limits. A later owner-attended helper may store a data-only key
outside Git and pass it through a non-logging transport; Phase 1 has no such
helper and must not request a key.

Forward collection is currently design-only: fetch bars older than documented
delay plus safety buffer, retain checkpoints, reject concurrent writers, flag
STALE/GAPPED/STOPPED, and never schedule itself. Proposed future owner command:
`python -m futures_data collect --root ES --archive data/backtests/es_forward_archive_1`
(not implemented or runnable in Phase 1).

## Scientific validation

Validated ES and NQ archives will receive independent configuration locks,
partitions, folds, regimes, trade counts, confidence intervals, and conclusions.
They must never be combined with BTC metrics. Each market needs at least 200
finalized untouched out-of-sample trades before an owner PASS can be considered;
two years of data does not guarantee that sample.

## Raw-retaining bounded probe and historical preflight

The corrected bounded probe is isolated under
`data/backtests/es_probe_staging_2` and `nq_probe_staging_2`. Each provider
response is retained byte-for-byte before parsing, has a per-request manifest,
and is checksum-verified against normalized output. The earlier `staging_1`
probe remains rejected evidence because it did not retain raw responses.

`futures_data.backfill_preflight` is metadata-only. On a separately authorized
owner run it retains the ES and NQ contract-discovery responses, rejects every
instrument except an exact XCME quarterly ES/NQ outright, intersects each
contract lifecycle with the owner-confirmed entitlement window capped at two
years, and writes separate immutable inventories. It estimates sessions,
five-session aggregate windows, rows, bytes, and minimum duration at four calls
per minute. It performs zero aggregate downloads and starts neither a backfill
nor a recorder. Missing bars will never be fabricated and individual contracts
will never be silently spliced.

Owner commands (each resolves the repository from the script location):

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\enter_massive_es_nq_backfill_preflight_key.ps1"
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\get_es_nq_backfill_preflight_status.ps1"
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\stop_es_nq_backfill_preflight.ps1"
```

The hidden-prompt helper has no automatic retry. A later backfill must preserve
raw bytes, checkpoint every successful request, resume only after checksum
verification, and atomically promote validated per-contract data. Preflight
readiness is not backfill completion and does not authorize continuous
collection, brokerage, or trading.

Rollback is deletion of newly created, unreferenced ES/NQ Phase 1 artifacts only;
never alter a prior manifest or raw contract archive. Health monitoring reads
manifest checksums, cursor age, gaps, revision lineage, and writer-lock state.
