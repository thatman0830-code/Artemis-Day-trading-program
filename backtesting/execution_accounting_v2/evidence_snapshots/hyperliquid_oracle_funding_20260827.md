# Frozen source note: Hyperliquid oracle and funding semantics

- Source organization: Hyperliquid
- Canonical URLs:
  - https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle
  - https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding
- Retrieved: 2026-08-27 UTC through public first-party documentation search
- Applicable use: current semantic model, not historical rates or prices.

Normalized facts retained: oracle prices contribute to funding and mark prices; mark prices are used
for margin and liquidation. Funding is paid hourly. The documented payment basis uses position size,
oracle price, and the funding rate, with positive funding paid by longs. The retained BTC candle
archive has no synchronized oracle, mark, or funding series.
