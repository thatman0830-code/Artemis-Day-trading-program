# Hyperliquid read-only VPS shadow node

This deployment runs only the existing public closed-candle recorder. It has no
wallet, account credentials, order endpoint, execution service, or inbound
network port. MES/MNQ remain on the independent NinjaTrader/Databento lane.

## Compliance boundary

Choose a VPS region for lawful availability, operational reliability, and
latency—not to conceal residency or bypass platform restrictions. Deployment
does not establish user eligibility. If public access is not permitted for the
operator, do not deploy it.

## Oracle boundary

The external Oracle engine is not bundled because its source and dependency
inventory have not been supplied or audited. It may export observations matching
`oracle-shadow-observation-v1`; `research.oracle_shadow_lane_v1` validates those
facts for offline comparison. Oracle output cannot influence canonical strategy
state, paper orders, or live orders.

## Start and verify

```sh
docker compose -f deploy/hyperliquid-shadow/compose.yaml up -d --build
docker compose -f deploy/hyperliquid-shadow/compose.yaml ps
docker compose -f deploy/hyperliquid-shadow/compose.yaml logs --tail=100 hyperliquid-recorder
```

Enable DigitalOcean backups and external uptime notification separately. Do not
place wallet keys, exchange API credentials, or NinjaTrader material on this VPS.

The A/B target experiment lives in `backtesting.target_liquidity_ab_research_v1`.
It compares clustered pools against eligible PDH/PDL and external structural
swings, while remaining explicitly non-authoritative.
