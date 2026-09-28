# Closed BTC valuation input

This pure function consumes caller-supplied immutable CSV bytes. It never opens
an archive, contacts a provider, creates orders/fills, or starts a session.

It reuses the repository archive scanner's CSV/OHLCV validation and adds positive
BTC prices, aligned exact 1m/15m intervals, bounded bytes/rows, strict continuity,
explicit UTC availability, source SHA-256 agreement, and configurable freshness
within a bounded ceiling. It returns the latest close as `PriceEvidenceV2` with
an immutable source receipt. Explicit availability can be later than bar close;
the implementation does not infer availability from close time or file mtime.

The receipt binds the exact input bytes' hash, row content, instrument identity,
mark specification, source version and availability. It is not provider
authentication, proof of data licensing, or validation of authoritative market
specifications. Those must be supplied by the source-evidence layer.

The optional `previous` argument is a trusted receipt returned by this function,
not an untrusted serialized checkpoint decoder. Same-bar polling preserves its
first receipt and first-known availability; a later read's hash/metadata do not
replace that retained receipt. Conflicting revisions of the retained bar reject,
including when that bar is included before a new latest row. Advancement must
be exactly one interval. This is in-memory continuity, not crash-safe cursor
storage or a complete historical revision audit.

## Execution boundary

One-minute and fifteen-minute closes may produce valuation marks. Neither CSV
closure flags nor this mark receipt establish execution eligibility. The existing
OHLC execution engine still requires its separate, aligned one-minute execution
bar contract and strategy/order/cost evidence. Fifteen-minute dashboard bars must
not be relabeled as one-minute execution evidence.

The bounded driver integration test uses temporary synthetic fixtures explicitly
for testing, sends a validated close as a mark, and stops without creating orders.
No real recorder archive or operational session was read or started.

## Remaining integration

A real runtime still needs trustworthy UTC/monotonic timing, a watchdog,
safe byte-snapshot acquisition with retained source receipts, durable cursor
handling, and strategy-to-validated-fill integration. This module alone is not
an autonomous runner or approval to trade. It has local tests but no independent
Hermes audit is claimed.

Focused verification: 19 passed.
