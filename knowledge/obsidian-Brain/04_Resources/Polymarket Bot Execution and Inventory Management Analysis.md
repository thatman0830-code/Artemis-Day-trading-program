---
title: Polymarket Bot Execution and Inventory Management Analysis
type: external-research
status: REFERENCE_ONLY
authority: non-normative
---

# Polymarket Bot Execution and Inventory Management Analysis

## Status

External research and implementation rationale only. This note is not a mechanical definition and cannot override [[Trading Brain — Source Precedence]].

## Transferable Findings

- Many fills can belong to one larger trading decision; fill count is not setup count.
- A theoretical opportunity can cease to be executable after spread, slippage, depth, available size, speed, volatility, fees, or price movement are considered.
- Displayed price is not necessarily the achievable average fill price.
- Orders and fills require separate records; canceled/rejected instructions are not exposure.
- Position state must be reconstructed from actual fills.
- Setup quality and execution quality require separate evaluation.
- A mechanically valid signal can correctly produce no trade.
- Rapid alternating executions may reflect inventory reshaping rather than repeated changes in directional conviction.

These findings motivate [[#29.0 Execution Eligibility]], [[Execution Entity Hierarchy]], [[#29.6 Position Lifecycle]], and [[Execution Quality EOD Metrics]]. They do not supply directional market logic.

## Intentionally Not Adopted

The following source-specific ideas are prohibited from the core engine:

- Polymarket Up/Down pairing or complementary binary-outcome balancing
- asynchronous binary arbitrage and pair-cost-below-settlement logic
- binary-contract settlement mechanics and Polymarket-specific inventory balancing
- cross-market BTC/ETH/SOL binary-contract hedging
- illustrative Bayesian odds/probability-update formulas or sample posterior-odds code
- fractional Kelly or any Kelly Criterion sizing
- automated probability/fair-value estimation as a new source of directional truth

The deterministic Market/Setup Engine remains authoritative. Only the general execution, fill-accounting, position-reconciliation, and measurement lessons are adopted.

