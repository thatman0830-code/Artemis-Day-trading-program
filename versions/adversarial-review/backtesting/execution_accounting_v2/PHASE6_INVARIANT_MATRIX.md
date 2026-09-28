# Phase 6 Invariant Matrix

| Invariant | Enforcement | Test evidence |
|---|---|---|
| Outgoing closes before incoming | `RolloverStateV2` lifecycle | ES/NQ, partial and failed roll tests |
| No synthetic transfer/fill | instructions consume later accepted fills only | separate-leg and authority tests |
| Participation is Decimal and step-floored | `eligible_roll_quantity` | participation tests |
| Same-bar/look-ahead prohibited | `create_roll_instruction` | same-bar test |
| Missing incoming remains flat/incomplete | `record_missing_roll_bar` and completed gate | missing-leg tests |
| Funding is perpetual-only and never inferred | `prepare_funding_application` | profile/missing tests |
| Funding boundary cannot be crossed missing | `funding_boundary_gate` | boundary test |
| Economic fact applied once | Phase 4 event identity plus Phase 6 ledger | duplicate tests |
| Collision order deterministic | `Phase6Priority`; equal-time/equal-priority always `PRIORITY_AMBIGUITY` before event-id ordering | priority tests |
| Replay/checkpoint byte-stable | canonical identities/fingerprints | replay/tamper test |
| Cross-ledger lineage immutable | `Phase6ReconciliationV2` | reconciliation test |
