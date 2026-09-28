# ES/NQ session-gap reconciliation

This offline boundary reconciles scanner-reported one-minute ES/NQ discontinuities against retained, checksum-pinned XCME schedule responses and manifests.

It validates repository containment, exact raw bytes and SHA-256, manifest identity, response completeness, market, product, venue, unique `pre_open`/`open`/`close` events, UTC chronology, non-overlapping sessions, and gap coverage. Missing or conflicting evidence fails closed.

Each gap is deterministically classified as:

- `SCHEDULED_NON_TRADING_INTERVAL`: no overlap with a retained open session;
- `MISSING_OPEN_SESSION_DATA`: the entire gap overlaps retained open sessions; or
- `MIXED_REQUIRES_SPLIT`: only part overlaps, so the gap must be split before OOS use.

The source does not provide an authoritative maintenance subtype. The reconciler therefore does not guess whether a scheduled non-trading interval is maintenance, a weekend, or a holiday. Such subtype claims require separate effective-dated exchange evidence.

The result is immutable, content-addressed, and always has `trading_authority=false`. It does not access providers, modify archives, choose OOS partitions, run strategies, or authorize paper/live trading.
