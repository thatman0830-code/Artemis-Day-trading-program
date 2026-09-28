# Pass B Second Failure Forensic Audit — 2026-08-27

This audit was performed offline. Both failed attempts, the frozen plan, and every retained market-data artifact remain unchanged. No provider call, retry, resume, promotion, credential access, recorder operation, deletion, or overwrite occurred.

## Attempt identity and diagnostic

- Plan ID: `2a4b82d4d5d5dc97d87d9fb57cb6b3ce05379af4239f1717bee55eda9d91820f`
- Second-attempt ID: `05a7c895d297be11df2897c7a59467238ee88f1b01016f8aee8501636f259eff`
- Failure timestamp: `2026-08-27T04:23:48.633287Z`
- Diagnostic: `data/backtests/pass_b_diagnostics/diagnostic-20260827T042348633287Z.json`
- Diagnostic SHA-256: `90dbae903ee07ac3c708ff565ec3adcb18944f1efb93431802f01eb58c863979`
- Phase: `PASS_B`
- Exception: `PassBError`
- Exact classification: `cumulative-cap stop`
- Sanitized message: `cumulative cap exceeded`

## Execution progression

Retained request 45 completed entirely offline. Its corrected manifest records 6,435 normalized rows, 2,425,779 normalized bytes, SHA-256 `6be9e48fbd4cc26cf1230cf8f669dec0ede32f9230cde925bc903d07b1b58110`, and 675 audited provider duplicates reconciled under `STRICT_SESSION_TIMESTAMP_PAIR_V1`.

The first new provider call was global ordinal 46. The attempt made 79 new network calls, covering ordinals 46 through 124. All 79 returned HTTP 200. No automatic retry occurred.

- Last committed request: ordinal 123, NQ/NQU6, request `9a44a307210515c25a87f31096c11a33235d28fc47c1a2dc755ab3f21aedc67a`, sessions 2026-07-02 and 2026-07-06 through 2026-07-09.
- Next uncommitted request: ordinal 124, NQ/NQU6, request `7bf93577b2f585ed74042883c5b5cca5e27d7c6360778dc143c38c3abc341e58`, sessions 2026-07-10 and 2026-07-13 through 2026-07-16.
- Ordinal 124 raw response is retained and verified at 1,394,198 bytes with SHA-256 `20b9b69f0ed28d6745eab6c5608f7b1af8c5209f63c0eeeb7a6aa800d6ab47e2`.
- Offline normalization of ordinal 124 would produce 6,900 rows and 2,623,804 bytes, with no duplicate reconciliation required.

## Footprint and cap result

- Retained raw bytes: 167,758,947 / 314,572,800
- Committed normalized rows: 830,777 / 1,000,000
- Committed normalized bytes: 314,528,350 / 314,572,800
- Combined retained bytes: 482,287,297 / 681,574,400
- Request count: 124 / 130

Only 44,450 normalized bytes remained. Committing ordinal 124 would have raised normalized storage to 317,152,154 bytes, exceeding the owner’s 300 MiB normalized cap by 2,579,354 bytes. The engine stopped before writing a normalized file, manifest, or checkpoint. Every cap was respected.

The frozen plan cannot legally resume to completion under its current normalized JSONL representation and unchanged 300 MiB normalized cap. A retry would verify and skip ordinals 1–123 and consume ordinal 124 raw offline, but would stop at the same cap before any new provider request. No verified request would be reissued, but another resume is not useful or authorized without a separately reviewed versioned storage/plan design. Raising or ignoring the cap was not considered.

## Integrity

- 123 requests are fully committed.
- Ordinal 124 has exactly one raw file and one pending transaction, as required by the raw-first boundary.
- 493 linked checksum validations passed and zero failed: all 124 pending-to-raw links, 123 manifest-to-raw links, 123 manifest-to-normalized links, and 123 checkpoint-to-manifest links.
- Every plan ID and request ID matches the frozen plan.
- No `.partial` or `.tmp` staging artifact exists.
- No conflicting or prematurely promoted artifact exists.
- `data/backtests/es_nq_pass_b_archive_3` does not exist.
- ES and NQ directories remained isolated; no cross-root paths or contract identities were found.
- Both original diagnostics remain immutable and checksum-verifiable.

## Credentials, BTC, and wrapper

The Massive key and temporary key paths are absent. `MASSIVE_API_KEY` is absent from process, user, and machine environments.

BTC remains `RECORDING`, all five archive checksums recompute successfully, every stream remains non-stale with zero gaps, and the latest observed event was `poll_complete` at `2026-08-27T04:27:03.481Z`. BTC was not modified or controlled.

The Windows PowerShell 5.1 wrapper now suppresses the already-recorded child diagnostic stream and emits one fixed, concise failure message. Its cleanup remains in `finally`; no exception text, traceback, credential, authorization value, or provider body is printed. Parser syntax validation passed.

## Offline tests

- Focused Pass B tests: 20 passed.
- Complete offline `futures_data` suite: 115 passed.
- No network-dependent test was run.

## Decision

This is not an authentication, entitlement, rate-limit, provider, connectivity, schema, contract, session, checksum, or resume defect. It is an intentional cumulative-cap stop caused by actual normalized JSONL size exceeding the preflight estimate. Completing the remaining seven requests requires an owner-reviewed versioned representation/plan change that preserves exact data while remaining below the existing caps; it cannot be treated as a safe resume of the frozen plan.
