---
title: Execution Entity Hierarchy
type: data-model-contract
status: LOCKED_AND_IMPLEMENTABLE
governing_amendments: ["007"]
---

# Execution Entity Hierarchy

## Canonical Hierarchy

```text
Setup
└── Trade
    ├── Order
    │   └── Fill
    ├── Order
    │   ├── Fill
    │   └── Fill
    └── Position (derived from all fills and exits)
```

- **Setup:** the opportunity detected and validated by [[#27 Setup Qualification]]. One setup may produce zero trades.
- **Trade:** one authorized attempt to express one setup. A valid but execution-ineligible setup creates no Trade.
- **Order:** one instruction associated with a Trade. Replacement/retry orders remain part of the same Trade unless a new Setup is mechanically required.
- **Fill:** one actual execution associated with exactly one Order and one Trade. An Order may have zero, one, or many fills.
- **Position:** current exposure derived only from immutable fills and exits, never requested quantity.

## Identity and Cardinality

```text
Setup 1 → 0..* Trade
Trade 1 → 1..* Order
Order 1 → 0..* Fill
Trade 1 → 0..1 Position
```

Every Trade stores `setup_id`; every Order stores `trade_id`; every Fill stores `order_id` and `trade_id`. IDs obey [[Identity — Versioning Policy]]. Canceled, rejected, and expired orders are not fills. Partial fills retain their originating Order. Multiple fills must not be counted as multiple setups or trades.

## Canonical Minimum Records

- `Trade { trade_id; setup_id; eligibility_evaluation_id; authorization_time; state; direction; requested_quantity; reason_codes }`
- `Order { order_id; trade_id; parent_order_id?; order_role; order_type; side; requested_quantity; limit_or_stop_price?; submitted_time; state }`
- `Fill { fill_id; order_id; trade_id; fill_time; fill_price; fill_quantity; fees; source_execution_id }`
- `Position` is specified by [[#29.6 Position Lifecycle]] and reconciled from the signed sum of Fill quantities.

Canonical uniqueness violations fail closed under [[Error Precedence — Fail Closed]]. The audit history is append-only.

## Lifecycle Separation

Setup, Trade, Order, and Position states are distinct. An order can be canceled while a partially filled Trade still has an OPEN Position. A Trade can close only after its derived position is flat and all working orders are resolved. See [[#29.0 Execution Eligibility]], [[#29.1 Entry Execution]], and [[#29.6 Position Lifecycle]].

## Research Rationale

[[Polymarket Bot Execution and Inventory Management Analysis]] is supporting research only and does not own this schema.

