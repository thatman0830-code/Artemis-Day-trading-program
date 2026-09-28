---
title: Amendment 007
status: ACTIVE
precedence: OWNER_RESOLUTION
appendix_modified: false
resolves: ["setup-valid vs execution-eligible", "theoretical vs executable entry", "setup-trade-order-fill hierarchy"]
scope: "#29.0 execution eligibility; #29.1/#29.6 interfaces; data model; EOD execution metrics"
---

# Owner Resolution Amendment 007 — Execution Eligibility, Orders, Fills, and Position Management

Precedence tier 1. Existing #1–#29.7.2.20 definitions retain their numbers and ownership except for the additive interfaces explicitly stated here. Appendix A remains unchanged.

## R1 — Two-stage eligibility

[[#27 Setup Qualification]] retains the authoritative setup-level ≥2R decision using theoretical EQ. [[#29.0 Execution Eligibility]] adds a downstream authorization-time ≥2R gate using the realistic expected executable entry. Both must pass; execution failure does not rewrite setup validity.

## R2 — Entity hierarchy

The canonical hierarchy is [[Execution Entity Hierarchy]]: Setup → Trade → Order → Fill; Position is derived from fills. Requested quantity or order creation never proves exposure.

## R3 — Position management

[[#29.6 Position Lifecycle]] reconciles actual fills, average fill price, quantity, working/protective orders, risk, and closure. No pyramiding, discretionary scale-in/out, break-even move, or trailing rule is authorized.

## R4 — Auditability

The linked execution state machine is append-only. Setup, Trade, Order, and Position states may not be conflated. Execution-quality EOD measurement is defined in [[Execution Quality EOD Metrics]].

## R5 — Explicit exclusions

The source-specific concepts catalogued under “Intentionally Not Adopted” in [[Polymarket Bot Execution and Inventory Management Analysis]] are research-only and prohibited from the core engine.
