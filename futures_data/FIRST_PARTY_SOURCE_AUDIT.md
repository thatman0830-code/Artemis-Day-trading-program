# First-party calendar and sparse-aggregate source audit

Frozen retrieval: `2026-08-26T21:36:56.4438380Z`. Source checksums are in
`pinned_sources/MANIFEST.json`.

Massive's retained missing-aggregate statement establishes that an aggregate is
not populated unless OHLC changed or an eligible trade occurred. The bounded
implementation conclusion is that absence represents zero observed eligible
trade volume for volume summation only. The missing minute remains explicit;
no OHLC is synthesized.

The Massive Schedules documentation establishes a product/date-filtered API
that returns UTC session events, breaks, and holiday/special-event adjustments,
with two years of history and access listed for all Futures plans. It does not
itself enumerate the historical 2025–2026 schedule.

CME's authorized trading-hours page could not be frozen: the retrieval timed
out and then returned HTTP 403. No third-party calendar or inferred date was
substituted. Because CME holiday hours can be revised, the exact historical
calendar remains blocked.

`futures_data.schedule_verification` therefore implements only a separately
owner-authorized schedules verification boundary. It queries ES and NQ
independently, retains raw bytes and SHA-256 manifests, permits at most eight
pages per market and sixteen requests total, waits at least fifteen seconds
between requests, caps each response at 8 MiB and total raw data at 64 MiB,
performs zero aggregate requests, never retries, and cannot start a recorder.
The Windows PowerShell 5.1 helper uses a hidden prompt and removes its owner-only
temporary credential on success or failure.

No revised rollover decisions, calendar, Pass B plan, or Pass B executor is
authorized until the retained schedules are reviewed offline against the
frozen source contract.
