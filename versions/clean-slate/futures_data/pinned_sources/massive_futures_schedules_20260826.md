# Massive Futures Schedules API (frozen excerpt)

- Canonical URL: https://massive.com/docs/rest/futures/schedules
- Linked from: https://massive.com/docs/rest/futures/overview
- Retrieved UTC: 2026-08-26T21:36:56.4438380Z
- Title: REST API - Futures Schedules
- Publisher: Massive.com, Inc.
- Applicable version: documentation retrieved 2026-08-26

## Source facts

- The endpoint returns session open/close times, intraday breaks, and holiday or
  special-event adjustments.
- Results can be filtered by `product_code` and `session_end_date`; documented
  comparison filters include `session_end_date.gte` and `.lte`.
- All returned times are UTC.
- `session_end_date` is the trading date; the documentation describes the
  ordinary session as ending at 5 PM Central Time.
- Documented result fields include `product_code`, `session_end_date`, `event`,
  and `timestamp`; example event values include `pre_open`, `open`, and `close`.
- The endpoint supports two years of history and is included in all Futures
  plans according to the retrieved plan-access table.

## Reproducibility boundary

This documents the API model but is not itself the historical schedule. Exact
2025–2026 dates require a separately authorized schedules-only retrieval.
