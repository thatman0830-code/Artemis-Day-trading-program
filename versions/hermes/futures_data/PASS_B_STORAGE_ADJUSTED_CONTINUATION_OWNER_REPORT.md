# Pass B Storage-Adjusted Continuation Owner Report

Prepared offline on 2026-08-27. This report and its content-addressed continuation plan do not authorize or execute Pass B. No retained evidence or frozen-plan artifact was modified.

## Plan identity and lineage

- Continuation plan ID: `cd39f6dc8a3fa93502144bad5f55a1c3d4839a3c4be9ac21439938d7c76d443e`
- Plan path: `data/backtests/es_nq_pass_b_continuation_plan_1/plan.json`
- Plan SHA-256: `a35e6c3fe728bb2c604b1eac4143f2bbdc69f1b3a80448872490ab26f15a0c27`
- Artifact-manifest SHA-256: `540f831742d6d21ab786bf4b41dfe3fa4fd673f523b50e4fd658042281566d41`
- Original plan ID: `2a4b82d4d5d5dc97d87d9fb57cb6b3ce05379af4239f1717bee55eda9d91820f`
- Original plan SHA-256: `1aad101fbbb315a1da72f27ce819c4007e38a202ef91c4c6153c1c3277ab5448`
- Original artifact-manifest SHA-256: `ac4606816f9b20bfe159eb5f9bf6f86ffa9cd798d3be99707947e49691c8e899`
- Stable checkpoint/evidence fingerprint through retained request 124: `9b960cc7079c1c2388ca8a5adf6dc149b4a167c280ef0e02c9e2aab6bfc54b9e`
- Retained request-124 raw SHA-256: `20b9b69f0ed28d6745eab6c5608f7b1af8c5209f63c0eeeb7a6aa800d6ab47e2`
- Retained request-124 pending SHA-256: `84523b685598fcb3aa7582dc2eca07bc659ccecd3a6ea8db5e1d651ed51fd355`
- First-attempt diagnostic SHA-256: `fa2412503d8ab9e3e2af52ae46c0123255cd540a8e3b0f3bab13fee732f3073b`
- Second-attempt diagnostic SHA-256: `90dbae903ee07ac3c708ff565ec3adcb18944f1efb93431802f01eb58c863979`

The continuation is a new versioned, content-addressed authorization overlay. It does not rewrite or replace the original plan. No private signing key was introduced. Its identity commits cryptographically to the original plan, original artifact manifest, both attempt diagnostics, the verified checkpoint prefix, and request 124’s immutable raw-first transaction.

## Current storage audit

| Artifact class | Count | Bytes |
|---|---:|---:|
| Raw responses | 124 | 167,758,947 |
| Normalized JSONL | 123 | 314,528,350 |
| Request manifests | 123 | 134,823 |
| Checkpoints | 123 | 31,611 |
| Raw-first pending records | 124 | 59,638 |
| Raw + normalized cap footprint | — | 482,287,297 |
| All retained Pass B artifacts | — | 482,513,369 |

All 493 linked hashes pass. The old plan remains capped at 300 MiB normalized; its constants and plan file are unchanged.

## Observed storage distribution

Normalized density is tightly clustered near 377 bytes/row for ES and 380 bytes/row for NQ. Per-request variation is driven principally by session length and returned row count.

| Market/contract | Requests | Rows | Raw bytes | Normalized bytes | Normalized B/row | Raw request min/median/max | Normalized request min/median/max |
|---|---:|---:|---:|---:|---:|---:|---:|
| ES ESM5 | 3 | 16,560 | 3,280,296 | 6,241,660 | 376.91 | 544,749 / 1,367,294 / 1,368,253 | 1,039,436 / 2,601,066 / 2,601,158 |
| ES ESU5 | 13 | 88,734 | 17,559,643 | 33,439,409 | 376.85 | 814,369 / 1,365,552 / 1,590,745 | 1,556,328 / 2,599,934 / 3,029,364 |
| ES ESZ5 | 13 | 88,510 | 17,562,976 | 33,369,986 | 377.02 | 1,083,097 / 1,370,596 / 1,418,000 | 2,062,128 / 2,601,570 / 2,699,197 |
| ES ESH6 | 13 | 86,232 | 17,115,745 | 32,510,730 | 377.01 | 271,916 / 1,369,849 / 1,595,951 | 519,592 / 2,601,353 / 3,031,453 |
| ES ESM6 | 13 | 88,990 | 17,809,557 | 33,553,303 | 377.05 | 1,093,129 / 1,371,091 / 1,595,312 | 2,078,700 / 2,601,900 / 3,031,041 |
| ES ESU6 | 10 | 69,847 | 13,865,827 | 26,334,395 | 377.03 | 1,084,147 / 1,371,064 / 1,597,390 | 2,061,532 / 2,601,821 / 3,031,557 |
| NQ NQM5 | 3 | 16,553 | 3,336,643 | 6,294,046 | 380.24 | 551,723 / 1,391,859 / 1,393,061 | 1,045,636 / 2,623,816 / 2,624,594 |
| NQ NQU5 | 13 | 90,097 | 18,171,284 | 34,265,026 | 380.31 | 1,100,241 / 1,391,960 / 1,622,723 | 2,085,103 / 2,624,092 / 3,058,283 |
| NQ NQZ5 | 13 | 87,143 | 17,609,367 | 33,152,191 | 380.43 | 821,333 / 1,395,062 / 1,445,546 | 1,552,943 / 2,625,541 / 2,725,998 |
| NQ NQH6 | 13 | 86,157 | 17,407,356 | 32,775,744 | 380.42 | 273,219 / 1,394,155 / 1,625,381 | 519,234 / 2,625,098 / 3,059,218 |
| NQ NQM6 | 13 | 88,975 | 17,997,972 | 33,850,730 | 380.45 | 1,107,533 / 1,396,712 / 1,624,526 | 2,092,150 / 2,625,427 / 3,057,544 |
| NQ NQU6 committed | 3 | 22,979 | 4,648,083 | 8,741,130 | 380.40 | 1,396,715 / 1,624,738 / 1,626,630 | 2,625,131 / 3,057,470 / 3,058,529 |

The earlier estimate used approximately 225 normalized bytes per row. Actual canonical JSONL repeats long schema, plan, contract, and field identities on every row, producing roughly 377–380 bytes per row. The low estimate was therefore a representation-density error, not unexpected market volume or excess requests.

## Conservative requests 124–130 projection

Request 124 is known exactly: 6,900 rows and 2,623,804 normalized bytes; its 1,394,198 raw bytes are already included above. For requests 125–130, the plan uses the largest observed NQ per-request values across all NQ contracts: 3,059,218 normalized bytes and 1,626,630 raw bytes. It then adds a 25% uncertainty margin.

- Conservative final normalized: 340,752,240 bytes
- Conservative final raw: 179,958,672 bytes
- Conservative final raw + normalized: 520,710,912 bytes
- Minimum whole-MiB normalized cap supported by this bound: 325 MiB
- Minimum whole-MiB combined cap supported by this bound: 497 MiB
- Selected normalized cap: 400 MiB
- Selected combined cap: unchanged at 650 MiB

Current utilization before continuation is 124/130 requests, 830,777/1,000,000 rows, 167,758,947/314,572,800 raw bytes, and 482,287,297/681,574,400 combined bytes. Request count is intentionally near its terminal bound; row, raw, and combined caps retain substantial headroom. No cap is exceeded.

## Destination capacity

- Exact destination volume: `C:` containing `C:\Users\fjone\hyperliquid-trading-bot`
- Free bytes at plan creation: 1,788,869,165,056
- Conservative additional-space gate, including a 25 MiB response transaction allowance: 64,638,015 bytes

The executor rechecks free space read-only before continuation. Insufficient free space fails before processing request 124 or contacting the provider.

## Continuation behavior

- Revised caps: 130 requests; 1,000,000 rows; 300 MiB raw; 400 MiB normalized; 650 MiB combined; 25 MiB per response.
- Requests 1–123 must verify and are skipped.
- Retained request 124 is normalized and committed offline.
- The first possible provider call is request 125.
- Requests 1–124 cannot be redownloaded.
- The call interval remains 15 seconds, or no more than four requests per minute.
- Automatic retry remains disabled.
- Raw-first persistence, exact-contract validation, session validation, checksums, atomic checkpoints, stop handling, and final all-130 promotion remain required.
- Promotion occurs only after the loop verifies or commits every request through ordinal 130.
- No recorder import, command, or startup path exists.

## Offline verification

Eight focused continuation tests cover plan identity and cryptographic links, immutable old caps, migration from the 123-checkpoint/124-raw boundary, offline request-124 commitment, request 125 as the first fetch, no redownload of 1–124, revised normalized/combined cap enforcement, insufficient free space, checkpoint-link conflicts, promotion gating, credential redaction, and traceback-free PowerShell output. The complete offline `futures_data` suite passes 123 tests. PowerShell 5.1 parser validation passes.

## Owner command — not executed

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy Bypass -File "C:\Users\fjone\hyperliquid-trading-bot\scripts\enter_massive_es_nq_pass_b_continuation_key.ps1"
```

This command securely prompts for the dedicated key. It has not been run by Codex and does not authorize a recorder or trading operation.
