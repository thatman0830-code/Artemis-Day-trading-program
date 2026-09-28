# Phase 5 Invariant Matrix

| Invariant | Enforcement | Focused evidence |
|---|---|---|
| Decimal-only limits/economics | constructors and arithmetic reject float/non-finite | `test_risk_limits_require_decimal_finite_effective_versioned_values` |
| Exact session ownership | UTC half-open resolver; one match only | session resolver tests |
| Effective identity/version isolation | pre/post evaluators bind run, market, instrument, contract, accounting and risk versions | stale/mismatch tests |
| Pre-trade has no execution authority | result contains decisions and values only | advisory boundary test |
| Session loss/drawdown cannot reset | prior immutable state and monotonic chronology required | reference reset test |
| Margin breach does not liquidate | unresolved facts/instruction only | margin breach test |
| No breach-bar fill | later finalized eligible bar required | forced flatten tests |
| End-of-data residual fails | explicit completed-run gate | residual test |
| Deterministic replay/idempotency | canonical SHA-256 identities and immutable ledger | replay/checkpoint tests |
| Tamper detection | ledger/checkpoint fingerprint verification | tamper test |

