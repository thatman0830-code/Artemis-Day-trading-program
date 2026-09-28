# Delayed Daily ES/NQ Forward Collector Architecture

This subsystem collects research data only. It has no trading, brokerage, account, wallet, signing, order, backtest, Pass B, or BTC-recorder control interface.

One bounded process supervises isolated `ES` and `NQ` pipelines. Its sole input is a finalized, content-addressed session manifest derived from retained Massive Schedules evidence. Each item names one outright contract, exact session date, UTC active intervals, contract identity, schedule source, and version. Calendar-spread, micro, option, combo, continuous, synthetic, missing, or ambiguous contract facts fail closed.

## Bootstrap and reference advancement

The initial configuration is produced—not hand-authored—by `futures_data.forward_bootstrap` from the checksum-verified Pass B plan, verified calendar, rollover windows, and final archive audit. The bootstrap records all 313 archived sessions per market as immutable history and has a zero-item pending queue because retained authoritative schedules stop at 2026-08-26. A zero-pending configuration is valid; it represents a verified horizon, not permission to infer another session.

Reference advancement is a separate bounded phase implemented by `futures_data.forward_reference_refresh`. It runs only when the verified horizon is within 14 days, makes independently filtered ES and NQ schedule and exact-contract requests, retains raw bytes and manifests before parsing, permits at most eight requests and 8 MiB per refresh, waits at least 15 seconds between calls, and never retries automatically. Only `single` XCME ES/NQ quarterly contracts pass. New sessions must begin exactly at the previous exclusive boundary. A successor is written as a new content-addressed version; prior configurations, history, and rollover decisions are never rewritten.

When the returned evidence reaches a contract boundary, the refresh creates an `AWAITING_FINALIZED_VOLUME` overlap preparation for the outgoing and next exact quarterly contract. It does not decide the rollover. Aggregate facts for both legs remain separate; only the existing two-consecutive-finalized-session rule can produce a next-session-effective decision.

The production ordering is: acquire the filesystem lock; verify credential presence without logging it; validate configuration, manifest, provenance, and checkpoint handoff; refresh references when the horizon threshold requires it; atomically publish a successor; select only verified eligible sessions; retain and validate aggregates; commit checkpoints; release the lock; emit sanitized status. Aggregate collection is impossible for a session absent from a validated configuration.

Eligibility is calculated independently per session:

`eligible_at = verified exchange close + 8-hour Futures Basic delay + safety buffer`

No forming or merely scheduled session is requested. The default safety buffer is one hour and remains configurable. Holidays, early closes, maintenance breaks, and DST come from explicit UTC exchange events; the task's wall-clock trigger never determines eligibility. After downtime, all eligible sessions without verified checkpoints are processed in chronological order.

For each session the collector performs one aggregate request with no automatic retry and at least 15 seconds between calls. Raw response bytes and a pending transaction are persisted atomically before parsing. Only after schema, exact-contract, OHLC, schedule-boundary, duplicate, and cap validation does it write normalized JSONL, a SHA-256 manifest, and an atomic checkpoint. Existing verified sessions cannot be overwritten or redownloaded.

During a bounded rollover window, the session manifest supplies separate `OUTGOING` and `INCOMING` facts. Their paths include distinct tickers, preventing collision. Completed daily volume treats absent eligible-trade bars as zero observed volume without creating OHLC. Two consecutive finalized sessions with incoming volume greater than outgoing volume freeze a decision effective on the following verified session. A future session manifest consumes that immutable decision; the running process does not retroactively rewrite prior contract selection.

Per-run caps are 20 requests, 100,000 rows, 50 MiB raw, 100 MiB normalized, and 150 MiB combined. Cumulative forward caps are 1 GiB raw, 2 GiB normalized, and 3 GiB combined. The collector fails closed before writes that exceed a cap. A filesystem lock and Task Scheduler `IgnoreNew` policy prevent overlap. A stop sentinel is checked before every provider call.

Storage is isolated under `data/futures_forward/{ES,NQ}`. Sanitized reports live under `outputs/futures_forward`; diagnostics contain no credentials, headers, response bodies, or query strings. BTC's path is an explicit rejected boundary.

The scheduled job runs daily at 02:30 under the owner account with limited privileges and an explicit repository working directory. `StartWhenAvailable` supports downtime catch-up, while runtime eligibility—not the trigger time—controls requests. The installer uses an owner-attended hidden Windows logon prompt so Task Scheduler can run when the owner is logged off; Windows retains that task-logon secret in its protected scheduler/LSA boundary. This is separate from the Massive DPAPI ciphertext and is a residual Windows-account risk. Installation initially leaves the task disabled for owner review. No service, recorder, or task was installed or started by this implementation.
