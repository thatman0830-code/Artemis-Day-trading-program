# VPS shadow milestone status

Prepared and locally verified on 2026-09-11. No paid infrastructure was created.

## Complete

- Existing hardened Hyperliquid public closed-candle recorder reused unchanged.
- Read-only, non-root container with all capabilities dropped and no inbound port.
- Persistent data and log volumes plus checksum-aware health probe.
- Wallet, account, exchange-action, and execution services absent.
- Oracle observation contract rejects malformed, future, action-like, or
  out-of-range output and remains comparison-only.
- Static third-party Oracle project preflight added; passing it does not grant
  deployment or trading authority.
- Baseline clustered-pool and experimental PDH/PDL/external-swing target lanes
  implemented outside canonical #23/#24 logic.
- MES/MNQ NinjaTrader/Databento paths unchanged.

## External gates still required

1. Attach the DigitalOcean browser tab and approve the displayed recurring cost.
2. Add an SSH public key; never transmit or install a private key through chat.
3. Select backups only after accepting their displayed additional cost.
4. Supply the Oracle project directory for static and manual audit.
5. Confirm platform eligibility independently; VPS location is not an access bypass.

Until all gates pass, deployment and Oracle execution remain disabled.
