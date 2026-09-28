# Final ES/NQ Historical Archive Audit

Audit time: 2026-08-27. Mode: offline, read-only. Archive: `data/backtests/es_nq_pass_b_archive_3`.

The audit passed all gates. The machine-readable report at `outputs/archive_audits/es_nq_pass_b_final_audit.json` contains the SHA-256, byte size, and path for every raw response, pending transaction, normalized file, request manifest, and checkpoint. Its archive tree fingerprint is `405ff5602600fbe361c7136b85be0b26d46567c1c080dfefab2e506e109a775b`.

| Market | Requests | Rows | Raw bytes | Normalized bytes |
|---|---:|---:|---:|---:|
| ES | 65 | 438,873 | 87,194,044 | 165,449,483 |
| NQ | 65 | 438,806 | 88,656,230 | 166,919,857 |
| Total | 130 | 877,679 | 175,850,274 | 332,369,340 |

Additional retained bytes: manifests 143,462; checkpoints 34,068; pending records 63,088. Raw plus normalized is 508,219,614 bytes; all archive artifacts total 508,460,232 bytes.

All 130 request identities occur exactly once. Every normalized row preserves its root, individual contract ID, ticker, original plan ID, session, and nanosecond UTC timestamp. Every economic row matches an immutable raw-provider observation exactly. There are no duplicate `(market, contract, timestamp)` keys. Ordering is strict within and across requests. UTC timestamps map deterministically through `America/Chicago`, including DST.

Every request belongs to exactly one frozen active-contract window from the versioned rollover decisions. No continuous ticker, synthetic splice, price adjustment, forward fill, or synthesized OHLC row exists. The 4,501 absent scheduled minutes are explicitly classified `ZERO_OBSERVED_ELIGIBLE_TRADE_VOLUME_NO_OHLC` under the pinned Massive sparse-aggregate semantics.

Final utilization remains within 130 requests, 1,000,000 rows, 300 MiB raw, 400 MiB normalized, 650 MiB combined, and 25 MiB per-response caps. ES and NQ paths are physically separate. The two failed attempts, original plan, superseded plan evidence, continuation overlay, raw-first cap stop, and diagnostics remain preserved.

Credential files and temporary material are absent. BTC remains `RECORDING`; all five BTC archive checksums pass, streams remain non-stale with zero gaps, and no BTC artifact or process was changed.
