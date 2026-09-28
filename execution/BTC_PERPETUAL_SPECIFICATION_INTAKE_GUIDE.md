# BTC perpetual specification intake guide

This intake is an evidence boundary, not a configuration shortcut. A field remains blank until its exact source bytes are retained and the owner explicitly approves the resulting value. Completing the intake grants no live-trading authority.

## Intake location

The generated working template is `outputs/paper_launch/btc-perpetual-specification-intake.json`. Runtime output is intentionally not committed.

## Required evidence

| Specification | Required retained evidence | Approval boundary |
|---|---|---|
| `INSTRUMENT` | Official contract-specification and tick/lot documentation plus a contemporaneous `meta` response identifying BTC and `szDecimals` | Contract, multiplier, currency, quantity step, and tick rule must agree |
| `MARK_PRICE` | Official robust-price documentation plus a contemporaneous `metaAndAssetCtxs` response | Never substitute candle close for the venue mark |
| `ORACLE_PRICE` | Official oracle documentation plus the same contemporaneous asset-context response | Oracle and mark remain distinct facts |
| `FUNDING` | Official funding documentation plus current and retained historical funding responses | No assumed zero funding |
| `MARGIN_TIER` | Official margin and margin-tier documentation plus the current BTC `meta` tier | Owner must select the supervised-paper leverage; maximum venue leverage is not a recommendation |
| `FEE_TIER` | Official fee documentation plus an account-specific `userFees` response | Requires the intended paper/live account public address; do not infer discounts |
| `SLIPPAGE` | Retained BTC order-book observations and a documented conservative estimation method | Owner-approved assumption; official docs do not provide a guaranteed slippage rate |
| `PARTICIPATION` | Retained liquidity observations and an explicit maximum participation policy | Owner-approved limit; do not derive it from venue order maxima |
| `RISK_LIMITS` | Signed/retained owner risk decision covering notional, leverage, loss, drawdown, and position limits | Owner policy; venue liquidation thresholds are hard constraints, not strategy risk limits |

## First-party references

- Hyperliquid contract specifications: `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/contract-specifications`
- Hyperliquid tick and lot size: `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/tick-and-lot-size`
- Hyperliquid robust price indices: `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/robust-price-indices`
- Hyperliquid oracle: `https://hyperliquid.gitbook.io/hyperliquid-docs/hypercore/oracle`
- Hyperliquid funding: `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/funding`
- Hyperliquid margining: `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margining`
- Hyperliquid margin tiers: `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/margin-tiers`
- Hyperliquid fees: `https://hyperliquid.gitbook.io/hyperliquid-docs/trading/fees`
- Hyperliquid perpetual Info endpoints: `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals`
- Hyperliquid user-fee endpoint: `https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint`

## Safe workflow

1. Retain each source response or document beneath a dedicated evidence root.
2. Compute SHA-256 from the exact retained bytes.
3. Enter only explicit string values and UTC effective dates.
4. Set `owner_approved` only after reviewing the retained source and value mapping.
5. Finalize the document to compute `intake_id`.
6. Compile it into the canonical bundle. Compilation reruns provenance and economic eligibility checks.
7. Treat any later source, account-tier, or policy change as a new effective-dated intake.

The current blank template is not eligible and must not be compiled until every category is evidenced and approved.
