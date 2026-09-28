# NinjaTrader read-only quote bridge

`HermesReadOnlyQuoteExporter.cs` is a chart indicator, not a trading strategy. It exports only current MES/MNQ bid, ask, last, volume, instrument, sequence, and UTC time to a local JSON file using replacement writes. It does not access accounts, credentials, positions, or orders and has no network client.

Do not install it until repository tests pass and the source has been reviewed. A valid file still has `entitlement_confirmed=false` and `decision_use_permitted=false` when loaded; separate retained evidence and owner approval are required before any paper-execution gate may consume the quote.
