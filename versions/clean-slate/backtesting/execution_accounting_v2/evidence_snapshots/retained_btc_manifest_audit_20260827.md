# Retained local BTC provenance audit

- Source: `data/backtests/btc_forward_archive_2/archive_manifest.json`
- Inspected: 2026-08-27 UTC, read-only
- SHA-256 observed at inspection: `9240a64ee5df39ce3e9f277f858bbb46ab1c549cc92101563536d56be40881b9`
- Manifest schema: `backtesting-forward-archive-v1`
- Candle schema: `historical-candle-v1`
- Declared source: `hyperliquid-public-mainnet`
- Declared symbol: `BTC`

The manifest contains candle file checksums, timeframes, closed-candle coverage, and network/source
labels. It does not contain an immutable perpetual-universe metadata response, spot metadata response,
actual candle request body, source-code fingerprint, mark/oracle history, funding, margin-tier history,
fee-tier history, or margin mode. The evidence is consistent with the repository's public Hyperliquid
candle collector but does not by itself prove the economic instrument. Classification remains
`BTC_UNKNOWN_UNSUPPORTED` for production accounting.
