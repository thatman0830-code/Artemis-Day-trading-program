# Schedules verification failure diagnosis

The failed attempt is preserved unchanged at
`data/backtests/es_nq_schedule_verification_staging_1`.

Two ES schedules requests completed, both HTTP 200, with no retry and zero
aggregate or contract-metadata calls. NQ was never requested because ES parsing
failed first.

Retained raw evidence:

- Page 1: `ES/raw/d27abcbd88e3cb37fc5fe164c6e3d3b6a03e5d780ffc95fb33f1412a5d49c688.json`,
  1,000 records, SHA-256
  `993d5dd4ce1a2552dd8c292eaa3f808d17ca6325479554f347eacfbda0a8092e`.
- Page 2: `ES/raw/cd6cacf517ac608f015804cd2572803f5c7c5a2367938a2388f2631cf6948458.json`,
  926 records, SHA-256
  `3211f97a4dd212334abee357a66c0e43d12d2bf5b3320332c40281351e856c5b`.

The top-level fields are `status`, `request_id`, `results`, and optional
`next_url`. Every record has non-null string fields `product_code`,
`product_name`, `session_end_date`, `trading_venue`, `event`, and `timestamp`.
The response spans 313 represented ES session dates from 2025-06-02 through
2026-08-26 and uses `pre_open`, `open`, and `close` events.

The original key was `(product_code, session_end_date, event, timestamp)`. It
collapsed two distinct products: `E-mini S&P 500 Futures` and `ES Equity
Calendar Spread`. They share XCME event times but are not duplicate source
records. All 963 apparent duplicates were this product-name distinction.

The corrected source key is `(product_code, product_name, trading_venue,
session_end_date, event, timestamp, source_request_id)`. Only byte-equivalent
records within the same immutable source response may deduplicate; conflicts
fail closed. Normalized calendar evidence selects the exact outright product
name and retains counts for excluded schedule products. ES and NQ retain
separate paths and provenance.

The corrected attempt uses staging/result version 2. Failures now emit a concise
message without a traceback and atomically retain a local, secret-free
diagnostic record. The original version-1 evidence is never reused or changed.
