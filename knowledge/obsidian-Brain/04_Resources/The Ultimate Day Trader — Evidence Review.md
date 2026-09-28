---
title: The Ultimate Day Trader — Evidence Review
type: source-derived-research
status: advisory-only
reviewed: 2026-09-10
trading_authority: false
paper_execution_permitted: false
live_trading_permitted: false
tags:
  - trading-brain
  - research
  - book-review
  - evidence-gate
---

# The Ultimate Day Trader — Evidence Review

## Provenance and limits

Reviewed all photographs available from the user’s three archives: approximately 50 pages covering pages 86–107 (gap trading), 109–123 (moving-average channel), and 125–137 (day-of-week relationships). This is not the majority of the complete book. The Thorium annotation export contained metadata but no notes or book text. The protected EPUB was not decrypted or bypassed.

This note is research evidence only. It cannot modify the canonical BTC strategy, MES/MNQ policy, approved risk limits, or order permissions.

## Findings retained for research

- Use an explicit **setup → trigger → follow-through** state machine.
- Preserve setup-without-trigger as `NO_TRADE` evidence.
- Preserve every risk, news, liquidity, and data-quality rejection with deterministic reason codes.
- Prefer reproducible features over subjective chart interpretation.
- Treat gap, channel, weekday, news, volatility, trend, session, and liquidity as context—not direction commands.
- Evaluate exits independently under equal risk and cost assumptions.

## Isolated research lanes

1. **Gap lane:** opening outside the prior RTH range followed by possible prior-range re-entry. Normalize gap size by ATR and prior range.
2. **Moving-average-channel lane:** historical hypothesis using a 10-period SMA of highs, 8-period SMA of lows, and two completed bars outside the channel. Parameters are hypotheses, not defaults or signals.
3. **Day-of-week lane:** Friday/Monday and other calendar relationships as descriptive features only. Correct for holidays, early closes, time zones, DST, rolls, news clustering, multiple testing, and structural decay.

## Claims rejected as policy

- Historical win rates do not establish current expectancy.
- Increasing leverage or position size is not an acceptable way to rescue small expected returns.
- Entering after a streak of losses is not statistically justified.
- Overnight and first-profitable-opening exits are outside the current intraday mandate.
- Old stock/futures examples cannot be pooled with modern MES, MNQ, or BTC results.

## Promotion gate

Any candidate must have an unambiguous specification, point-in-time data, explicit session and roll rules, realistic costs, untouched out-of-sample evaluation, adequate sample size, uncertainty intervals, baseline comparisons, multiple-search correction, bounded tail risk, shadow observation, and paper-only approval. There is no automatic promotion to live trading.

## Current implementation status

- Gap feature extractor: implemented as read-only research.
- Moving-average-channel extractor: implemented as read-only research with prior-bar-only channel semantics and fail-closed data checks.
- Day-of-week feature generator: implemented as descriptive, advisory-only research.
- Three-lane comparison harness: implemented and fail-closed.
- September 8–10 comparison attempt: blocked because both ES and NQ archives contain open-session gaps; no performance claims were generated.
- September 11 stream: clean and advancing, but not yet a complete trading day.
- Canonical execution logic: unchanged.

Full consolidated working review: `C:\Users\fjone\Documents\Codex\2026-08-21\referenced-chatgpt-conversation-this-is-an\ultimate-day-trader-evidence-review.md`
