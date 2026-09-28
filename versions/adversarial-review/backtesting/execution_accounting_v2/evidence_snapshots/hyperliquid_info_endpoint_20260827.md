# Frozen source note: Hyperliquid Info endpoint

- Source organization: Hyperliquid
- Canonical URL: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
- Retrieved: 2026-08-27 UTC through public first-party documentation search
- Applicable use: current API identity semantics, not historical market evidence.

Normalized facts retained: perpetual coins use names returned by perpetual metadata; most spot
pairs use an `@index` identity returned by spot metadata. The endpoint supports candle snapshots for
both product families. Consequently a current request convention can support a classification, but
a retained archive must preserve the actual request and matching metadata lineage to prove it.
