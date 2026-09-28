# Production Eligibility Examples

Examples use `[2025-06-01T00:00:00Z, 2025-07-01T00:00:00Z)` and a synthetic dataset fingerprint.
They demonstrate rejection and are not economic configurations.

## ES and NQ

With no specifications, each report returns all nine missing fields, including instrument, session,
settlement, clearing margin, exchange execution costs, owner broker commission, slippage,
participation, and risk inputs. Exchange cost and slippage share
`MISSING_EXECUTION_COST_SPEC` but retain distinct fields and evidence classes. Reports remain
ineligible until continuous, non-overlapping, owner-approved records cover the entire interval.

## BTC generic archive

`BTC_UNKNOWN_UNSUPPORTED` returns `UNSUPPORTED_INSTRUMENT_PROFILE`. A directory or generic `BTC`
label cannot select spot or perpetual accounting.

## BTC linear perpetual

Without synchronized historical observations it returns, among other blockers,
`MISSING_MARK_PRICE_EVIDENCE`, `MISSING_ORACLE_PRICE_HISTORY`, `MISSING_FUNDING_SPEC`,
`MISSING_MARGIN_SPEC`, and `MISSING_FEE_TIER_HISTORY`. Current documentation cannot fill historical
gaps. Synthetic records add `OWNER_APPROVAL_REQUIRED` and never make the report eligible.

Every report is stable JSON through `as_machine_dict()` and includes both dataset and economic
fingerprints. Repeated identical evaluation produces the same report identity.
