# Frozen source note: Hyperliquid perpetual contract and margin semantics

- Source organization: Hyperliquid
- Canonical URLs:
  - https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications
  - https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining
  - https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margin-tiers
- Retrieved: 2026-08-27 UTC through public first-party documentation search
- Applicable use: current semantics only; not historical tier evidence.

Normalized facts retained: the documented core product is a linear perpetual with one unit of the
underlying per unit, cross or isolated margin, no expiration, and hourly funding. Initial margin
depends on selected leverage. Maintenance uses tiered rates and deductions, while maximum leverage
depends on the asset. Historical BTC universe metadata, tier versions, leverage, and mode were not
retained with the candle archive.
