# ES/NQ Pass B Owner Decision Audit

Status date: 2026-08-26. This is an offline, read-only decision artifact. It does not authorize or execute Pass B and does not start a recorder.

## Evidence and calendar

All four retained schedule responses in `data/backtests/es_nq_schedule_verification_2` were rehashed before use. Their response and manifest hashes match, both product streams have two complete pages, HTTP status 200, and the attempt recorded four schedule calls, zero aggregate calls, and no automatic retry. No Massive credential or credential-bearing temporary file remains. The established BTC read-only health boundary was not changed.

The complete retained responses contain two versioned outright product names for each root. After excluding the separately retained calendar-spread observations, the aliases combine to 963 schedule events over 313 unique session dates for ES and identically for NQ. The earlier number 331 described only the older-name portion of the result, not the complete session-date count. ES and NQ have identical event timestamps after product identity is removed; no open, close, break, venue, or timestamp conflict was found.

Calendar coverage is 2025-06-01 through 2026-08-26, in UTC and `America/Chicago`. It represents 313 sessions and 139 excluded dates. Every represented date occurs once per market. Every excluded date is explicitly categorized as `WEEKEND` or `PROVIDER_VERIFIED_NO_SESSION_EVENTS`. Provider events are preserved as pre-open, open, close, and active intervals; maintenance and special-session breaks are represented as separate intervals. Twelve sessions are marked early or special. DST is converted with the IANA `America/Chicago` zone, not a fixed offset.

Derived calendar:

- Path: `data/backtests/es_nq_pass_b_plan_3/calendar.json`
- Calendar version: `MASSIVE_SCHEDULE_EVENTS_20260826_V2`
- SHA-256: `9b87798eec32b617ea1407ae30f3e64802688e7f7c0115478c7328d28d6ea19a`

## Sparse aggregates and rollover decisions

Every Pass A raw response was rehashed. Missing expected active minutes are retained as missing OHLC observations and classified `ZERO_OBSERVED_ELIGIBLE_TRADE_VOLUME_NO_OHLC`, following the pinned Massive sparse-aggregate rule. They contribute zero observed eligible-trade volume only to daily-volume summation. No OHLC bar was synthesized. All decisions use two completed sessions, have a decision time at the end of the second completed session, and become effective on the next represented session.

### ES

| Decision session | Effective session | Outgoing volumes | Incoming volumes | Missing minutes (out/in, out/in) | Method |
|---|---|---:|---:|---|---|
| 2025-06-17 | 2025-06-18 | 541682, 277494 | 757791, 1161452 | 0/0, 0/0 | two-session crossover |
| 2025-09-16 | 2025-09-17 | 433344, 225833 | 698737, 961555 | 3/7, 3/3 | two-session crossover |
| 2025-12-16 | 2025-12-17 | 590475, 351626 | 975303, 1667671 | 0/0, 0/0 | two-session crossover |
| 2026-03-17 | 2026-03-18 | 798814, 239065 | 1055280, 1084921 | 0/0, 0/0 | two-session crossover |
| 2026-06-16 | 2026-06-17 | 579431, 182402 | 923610, 1087402 | 0/0, 4/0 | two-session crossover |

Active windows: ESM5 `[2025-06-01, 2025-06-18)`, ESU5 `[2025-06-18, 2025-09-17)`, ESZ5 `[2025-09-17, 2025-12-17)`, ESH6 `[2025-12-17, 2026-03-18)`, ESM6 `[2026-03-18, 2026-06-17)`, and ESU6 `[2026-06-17, 2026-08-27)`.

### NQ

| Decision session | Effective session | Outgoing volumes | Incoming volumes | Missing minutes (out/in, out/in) | Method |
|---|---|---:|---:|---|---|
| 2025-06-17 | 2025-06-18 | 169373, 92687 | 262263, 400305 | 1/2, 6/0 | two-session crossover |
| 2025-09-17 | 2025-09-18 | 94412, 107323 | 320651, 549031 | 2/0, 27/0 | two-session crossover |
| 2025-12-16 | 2025-12-17 | 241982, 115614 | 304939, 545470 | 0/0, 6/0 | two-session crossover |
| 2026-03-17 | 2026-03-18 | 249341, 77381 | 280694, 354897 | 1/0, 12/0 | two-session crossover |
| 2026-06-16 | 2026-06-17 | 147791, 75069 | 337967, 479880 | 0/0, 13/0 | two-session crossover |

Active windows: NQM5 `[2025-06-01, 2025-06-18)`, NQU5 `[2025-06-18, 2025-09-18)`, NQZ5 `[2025-09-18, 2025-12-17)`, NQH6 `[2025-12-17, 2026-03-18)`, NQM6 `[2026-03-18, 2026-06-17)`, and NQU6 `[2026-06-17, 2026-08-27)`.

No fallback was required. Windows are adjacent, non-overlapping, and assign each of the 313 supported sessions exactly once per root. No future bar contributes to an earlier decision.

## Frozen Pass B plan

- Plan ID: `2a4b82d4d5d5dc97d87d9fb57cb6b3ce05379af4239f1717bee55eda9d91820f`
- Plan path: `data/backtests/es_nq_pass_b_plan_3/plan.json`
- Plan SHA-256: `1aad101fbbb315a1da72f27ce819c4007e38a202ef91c4c6153c1c3277ab5448`
- Rollover SHA-256: `3babbde52da958d5c694d27d5a99a732cae7a363b566cca6710c07b818a91dbc`
- Requests: 65 ES + 65 NQ = 130
- Sessions: 313 per market
- Maximum expected rows: 441,090 per market; 882,180 total
- Minimum request-spacing runtime: 33 minutes; provider and validation time will add to this
- Per-response cap: 25 MiB
- Cumulative caps: 1,000,000 rows; 300 MiB raw; 300 MiB normalized; 650 MiB combined
- Research storage estimate: approximately 159–229 MB raw and 198 MB normalized, or 357–428 MB combined. Hard caps, not estimates, govern execution.
- Unsupported interval: `[2024-08-25, 2025-06-01)`
- Staging: `data/backtests/es_nq_pass_b_staging_3/{ES,NQ}`
- Archive: `data/backtests/es_nq_pass_b_archive_3/{ES,NQ}`
- Stop sentinel: `data/backtests/es_nq_pass_b.stop`

Inventory:

| Root | Ticker | Sessions | Requests | Maximum rows | First/last session |
|---|---|---:|---:|---:|---|
| ES | ESM5 | 12 | 3 | 16,560 | 2025-06-02 / 2025-06-17 |
| ES | ESU5 | 63 | 13 | 88,755 | 2025-06-18 / 2025-09-16 |
| ES | ESZ5 | 64 | 13 | 89,205 | 2025-09-17 / 2025-12-16 |
| ES | ESH6 | 61 | 13 | 86,235 | 2025-12-17 / 2026-03-17 |
| ES | ESM6 | 64 | 13 | 88,995 | 2026-03-18 / 2026-06-16 |
| ES | ESU6 | 49 | 10 | 71,340 | 2026-06-17 / 2026-08-26 |
| NQ | NQM5 | 12 | 3 | 16,560 | 2025-06-02 / 2025-06-17 |
| NQ | NQU5 | 64 | 13 | 90,135 | 2025-06-18 / 2025-09-17 |
| NQ | NQZ5 | 63 | 13 | 87,825 | 2025-09-18 / 2025-12-16 |
| NQ | NQH6 | 61 | 13 | 86,235 | 2025-12-17 / 2026-03-17 |
| NQ | NQM6 | 64 | 13 | 88,995 | 2026-03-18 / 2026-06-16 |
| NQ | NQU6 | 49 | 10 | 71,340 | 2026-06-17 / 2026-08-26 |

The executor persists immutable raw bytes and a pending transaction before parsing, records request-level SHA-256 manifests, includes exact contract identity in every normalized row, isolates ES and NQ paths, checkpoints atomically, verifies completed work on resume, and refuses overwrite or redownload. It performs one attempt per request with at least 15 seconds between actual provider calls. It validates before atomic staging-to-archive promotion, never fabricates bars or a synthetic continuous series, and has no recorder-start path. All cumulative caps are checked before and after each request.

Remaining uncertainties are provider entitlement at execution time, actual sparse-bar counts, provider response sizes, actual duration, and aggregate schema consistency. These fail closed; they do not authorize retries or weakened validation.

## BTC read-only health check

The established read-only check found `data/backtests/btc_forward_archive_2/archive_manifest.json` in `RECORDING` state, updated at `2026-08-27T02:26:40.981Z`. All five manifest file hashes recomputed successfully; every stream reports `gap_count: 0` and `stale: false`. The latest recorder event is a successful `poll_complete` in `RECORDING` state. No BTC file, process, configuration, or recorder control was changed.

## Owner commands (not executed)

Execution:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\enter_massive_es_nq_pass_b_key.ps1"
```

Status:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\get_es_nq_pass_b_status.ps1"
```

Graceful stop:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\stop_es_nq_pass_b.ps1"
```

## Verification

Sixteen focused offline tests cover source-exact holidays, early/special closes, maintenance intervals, DST, sparse rollover evidence, no-look-ahead, non-overlapping plans, exact contract identity, raw-first transactions, checksum-safe resume, path isolation, every cap, stop behavior, single-attempt provider failures, credential non-persistence, and recorder prohibition. The complete offline `futures_data` suite passes 111 tests. The three Windows PowerShell 5.1 scripts pass parser syntax validation. No network request was made by plan generation or tests.
