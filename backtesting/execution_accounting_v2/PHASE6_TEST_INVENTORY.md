# Phase 6 Rollover and Funding Test Inventory

Published before Phase 6 production implementation. Tests are deterministic, offline, Decimal-only,
and use immutable synthetic facts. They cannot access operational or trading systems.

## Rollover contracts and lifecycle

- `test_es_long_roll_closes_outgoing_then_opens_incoming`
- `test_nq_short_roll_closes_outgoing_then_opens_incoming`
- `test_partial_outgoing_close_blocks_incoming_activation`
- `test_failed_outgoing_close_leaves_roll_incomplete`
- `test_missing_incoming_leg_preserves_explicit_flat_state`
- `test_wrong_contract_market_session_and_roll_version_reject`
- `test_stale_overlapping_and_ambiguous_roll_specs_reject`
- `test_participation_limit_floors_quantity_to_verified_step`
- `test_zero_or_missing_volume_cannot_authorize_roll_quantity`
- `test_rollover_rejects_same_bar_and_future_bar_lookahead`
- `test_missing_outgoing_bar_fails_rollover`
- `test_incoming_instruction_is_distinct_from_outgoing_event`
- `test_roll_replay_is_idempotent_and_conflicting_fill_rejects`

## Funding boundaries and applications

- `test_perpetual_long_funding_debit_and_short_credit_are_symmetric`
- `test_flat_perpetual_funding_is_verified_zero_application`
- `test_duplicate_funding_application_is_idempotent`
- `test_conflicting_funding_identity_rejects`
- `test_late_stale_and_out_of_order_funding_reject`
- `test_missing_required_funding_boundary_blocks_held_position`
- `test_btc_spot_es_and_nq_funding_reject`
- `test_cross_instrument_contract_basis_multiplier_and_version_reject`
- `test_funding_event_preserves_mark_oracle_rate_and_accounting_lineage`
- `test_zero_funding_is_never_inferred_when_fact_is_missing`

## Priority, replay, integrity, and gates

- `test_phase6_collision_priority_is_total_and_stable`
- `test_same_priority_identity_collision_rejects_ambiguity`
- `test_rollover_funding_ledger_checkpoint_resume_is_byte_stable`
- `test_duplicate_event_and_economic_identity_prevention`
- `test_checkpoint_tamper_and_chronology_regression_reject`
- `test_market_instrument_run_and_version_isolation`
- `test_incomplete_roll_and_missing_funding_fail_completed_run_gate`
- `test_reconciliation_binds_execution_accounting_risk_session_roll_and_funding`
- `test_phase6_has_no_provider_strategy_order_submission_or_runtime_authority`

The same-priority collision test exercises both lexical event-id orders and
requires the stable `PRIORITY_AMBIGUITY` reason.
