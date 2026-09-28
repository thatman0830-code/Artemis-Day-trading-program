# V2 Phase 5 Risk and Sessions Implementation

Phase 5 implements deterministic, advisory-only risk and verified-session facts. It consumes
immutable Phase 4 snapshots, effective-dated owner risk limits, verified instrument/margin facts,
and verified sessions. It creates no order, fill, accounting mutation, provider request, or trading
authority.

## Public boundary

- `resolve_session` resolves exactly one UTC half-open verified session.
- `evaluate_pre_trade` calculates projected quantity, gross/net exposure, concentration, leverage,
  and customer initial margin, returning an immutable allow/reject record.
- `evaluate_post_accounting` advances immutable session reference/peak/loss/drawdown state and may
  emit margin-call, liquidation-required, and forced-flatten facts.
- `evaluate_session_flatten` emits an unresolved instruction at the configured verified deadline.
- `validate_forced_flatten_bar` proves only eligibility of a later finalized bar; it never fills.
- `completed_run_gate` rejects residual positions or unresolved forced actions.
- `RiskSessionLedgerV2` provides deterministic idempotent replay, chronology, and checkpoints.

## Frozen ordering

Data/session (10), settlement/funding/rollover (20), market data (30), strategy (40), pre-trade
risk (50), fills (60), accounting (70), post-accounting risk (80), reporting (90). Within a
post-accounting collision, maintenance margin precedes session loss, then drawdown. This ordering
changes no upstream fact.

## Fail-closed boundaries

Missing, overlapping, stale, mismatched, cross-version, chronologically regressed, non-Decimal,
non-finite, or tampered inputs reject. A breach bar cannot satisfy its own forced instruction.
Liquidation-required remains a fact only; Phase 5 creates no accounting-only liquidation.

## Phase 6 boundary

Any later orchestration may translate a validated unresolved instruction into the existing order
ledger only on a later eligible bar. That translation, rollover execution, portfolio-wide
multi-instrument aggregation, and completed result orchestration are not implemented here.

