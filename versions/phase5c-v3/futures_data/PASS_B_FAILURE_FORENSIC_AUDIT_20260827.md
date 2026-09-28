# Pass B Failure Forensic Audit — 2026-08-27

This audit used retained local evidence only. No network request, provider retry, credential access, Pass B execution, promotion, recorder control, deletion, or overwrite occurred.

## Identity and failure

- Frozen plan ID: `2a4b82d4d5d5dc97d87d9fb57cb6b3ce05379af4239f1717bee55eda9d91820f`
- Plan path: `data/backtests/es_nq_pass_b_plan_3/plan.json`
- Original runtime attempt ID: not emitted by the v3 executor; this was an observability defect corrected for future attempts.
- Forensic attempt ID: `96b58ce12acb7ebcd2a055ab56a25d6e4d3a559acf41449d7a6def0d6c13f8b1`, derived from the immutable plan ID and diagnostic SHA-256.
- Diagnostic: `data/backtests/pass_b_diagnostics/diagnostic-20260827T024250163454Z.json`
- Diagnostic SHA-256: `fa2412503d8ab9e3e2af52ae46c0123255cd540a8e3b0f3bab13fee732f3073b`
- Failure timestamp: `2026-08-27T02:42:50.163454Z`
- Phase: `PASS_B`
- Exception: `PassBError`
- Category: `local implementation defect`
- Sanitized message: `unexpected boundary or duplicate row`

The failure occurred at global request ordinal 45, ES request ordinal 45:

- Request ID: `a7dd45b2dc3100c39c83e954c329043933deac995bf892b1d6b82244bb4a3dde`
- Contract: `ESM6`
- Sessions: 2026-04-01, 2026-04-02, 2026-04-03, 2026-04-06, 2026-04-07
- UTC request interval: `[2026-03-31T22:00:00Z, 2026-04-07T21:00:00Z)`

## Root cause

The HTTP 200 response contained 7,110 rows. It included 675 duplicated timestamps from `2026-04-03T02:00:00Z` through `2026-04-03T13:14:00Z`. Each pair had identical ticker and economic fields, but one observation carried `session_end_date=2026-04-02` and the other carried the schedule-correct `session_end_date=2026-04-03`.

The local validator checked that the provider session label appeared somewhere in the five-session request and that the timestamp appeared somewhere in the union of those sessions. It did not validate the session-label/timestamp pair. It then rejected the repeated timestamp generically. This was a local implementation defect, not authentication, entitlement, rate limiting, connectivity, provider HTTP failure, checksum conflict, or a cap stop.

The correction constructs a unique verified-calendar session for every permitted minute. It requires exactly one provider row with the matching session label. A duplicate with another requested-session label is excluded only when every other retained field is byte-equivalent to the canonical row; the exclusion is recorded in the request manifest. Conflicting duplicates, a missing canonical-label row, calendar overlap, wrong contract, or an out-of-bound timestamp still fail closed. No OHLC is synthesized.

Offline reprocessing of the retained request-45 raw bytes now produces exactly 6,435 rows, matching the frozen plan maximum, and records 675 excluded provider duplicates under `STRICT_SESSION_TIMESTAMP_PAIR_V1`. The prospective normalized payload is 2,425,779 bytes with SHA-256 `6be9e48fbd4cc26cf1230cf8f669dec0ede32f9230cde925bc903d07b1b58110`. This result was computed in memory only; it was not written into the preserved staging attempt.

## Request, status, and footprint audit

- Provider requests issued: 45
- Provider responses completed: 45
- HTTP distribution: 45 × 200
- Successfully committed requests: 44
- Raw-retained but uncommitted requests: 1
- Automatic retries: 0; every pending record says `automatic_retry: false`
- Raw bytes retained: 59,674,396
- Normalized rows committed: 293,836
- Normalized bytes committed: 110,766,211
- Combined retained footprint: 170,440,607 bytes
- Last committed checkpoint: global/ES ordinal 44, request `beb69d39434984ca2a37f37f2b7a1d86516a9836791e711f6abd9bcd654b3b4e`, ESM6 sessions 2026-03-25 through 2026-03-31
- First raw-retained uncommitted request: ordinal 45 above
- Next request that would require provider access after offline completion of request 45: global/ES ordinal 46, request `c765592d9535d8e74ddea6064262ea3a92350a0d988fda79796a27c96a2747aa`, ESM6 sessions 2026-04-08 through 2026-04-14

All limits remained respected: 45/130 requests, 293,836/1,000,000 committed rows, 59,674,396/314,572,800 raw bytes, 110,766,211/314,572,800 normalized bytes, and 170,440,607/681,574,400 combined bytes.

## Integrity audit

- All 44 committed raw files match their manifest raw SHA-256.
- All 44 committed normalized files match their manifest normalized SHA-256.
- All 44 manifests match their checkpoint `manifest_sha256`.
- The request-45 raw file matches its pending transaction `raw_sha256`.
- Result: 133 linked checksum validations passed; zero failed.
- Every retained plan ID and request ID matches the frozen plan.
- No `.partial` or `.tmp` file exists in staging.
- Request 45 intentionally contains only immutable raw and pending records; it has no normalized file, manifest, or checkpoint.
- ES and NQ paths remained isolated. Only ES contains retained execution artifacts; NQ was never reached.
- `data/backtests/es_nq_pass_b_archive_3` does not exist. No premature promotion occurred.
- The original diagnostic, raw files, pending transactions, manifests, normalized files, and checkpoints were not modified by this audit.

The 44 committed responses were also reevaluated under the corrected paired session rule: zero pair mismatches and zero duplicate timestamps were found. Existing verified normalized artifacts therefore remain compatible with the frozen plan and corrected executor.

## Resume and diagnostics conclusion

The frozen plan does not need replacement. On an explicitly authorized later resume, the executor verifies and skips the first 44 committed requests, consumes request 45 from retained raw bytes without a provider request, records its audited reconciliation, and first contacts the provider for request 46. An offline regression proves this order and proves that request 45 is not redownloaded.

Future failures now record a cryptographically derived runtime attempt ID, request ordinal, root, request ID, ticker, bounded session list, and process-local network-call count in the secret-free diagnostic. Console output remains concise and traceback-free.

## Credentials and BTC

The Pass B key and temporary key paths are absent. `MASSIVE_API_KEY` is absent from process, user, and machine persistent environments.

The BTC archive remains `RECORDING`; its five data-file checksums recompute successfully, all streams remain non-stale with zero gaps, and the latest observed event is `poll_complete` in `RECORDING` state at `2026-08-27T02:51:46.814Z`. No BTC artifact or process was changed.

## Tests

- Focused Pass B tests: 20 passed.
- Complete offline `futures_data` suite: 115 passed.
- Added coverage for the exact cross-session duplicate response, conflicting duplicates, missing canonical labels, audited exclusion counts, and resume beginning at the first genuinely uncommitted provider request.
