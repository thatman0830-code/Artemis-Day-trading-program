# Phase 5 Risk and Sessions Test Inventory

Published before Phase 5 production implementation. Every test is deterministic, offline, and
uses immutable synthetic facts. No test may access providers, credentials, archives, collectors,
recorders, schedulers, exchanges, wallets, brokerage accounts, or out-of-sample results.

## Contracts and sessions

- `test_verified_session_requires_utc_half_open_interval_and_lineage`
- `test_verified_session_rejects_naive_time_invalid_timezone_and_effective_gap`
- `test_session_resolution_rejects_missing_overlapping_and_mismatched_sessions`
- `test_session_resolution_observes_exact_open_and_exclusive_close`
- `test_risk_limits_require_decimal_finite_effective_versioned_values`
- `test_risk_records_are_frozen_and_identifiers_are_deterministic`
- `test_cross_market_contract_run_and_version_isolation`

## Pre-trade risk

- `test_pretrade_accepts_projection_within_every_limit`
- `test_pretrade_rejects_gross_exposure_limit`
- `test_pretrade_rejects_net_exposure_limit`
- `test_pretrade_rejects_position_and_concentration_limits`
- `test_pretrade_rejects_leverage_and_initial_margin_limits`
- `test_pretrade_rejects_missing_stale_or_mismatched_limits`
- `test_pretrade_is_advisory_and_creates_no_order_or_fill`

## Post-accounting risk

- `test_session_loss_and_drawdown_use_verified_reference_equity`
- `test_session_reference_cannot_reset_after_session_activity`
- `test_postaccounting_margin_breach_emits_margin_call_and_liquidation_required_facts`
- `test_postaccounting_loss_and_drawdown_emit_forced_flatten_instruction`
- `test_postaccounting_priority_is_deterministic_when_breaches_collide`
- `test_duplicate_postaccounting_evaluation_is_idempotent`
- `test_conflicting_identity_reuse_and_event_time_regression_fail_closed`
- `test_negative_equity_is_accounted_without_float_or_implicit_reset`

## Forced action eligibility and residual state

- `test_forced_flatten_never_creates_an_order_or_fill`
- `test_forced_flatten_rejects_breach_bar_and_accepts_only_later_finalized_valid_bar`
- `test_forced_flatten_rejects_wrong_session_contract_and_unverified_bar`
- `test_unresolved_forced_flatten_remains_explicit_at_end_of_data`
- `test_completed_run_gate_rejects_residual_position_or_unresolved_instruction`

## Replay, priority, and integrity

- `test_pipeline_priority_matches_frozen_phase_order`
- `test_risk_ledger_replay_and_checkpoint_are_byte_identical`
- `test_checkpoint_tamper_and_mixed_accounting_version_reject`
- `test_duplicate_event_identity_is_idempotent_but_conflict_rejects`
- `test_reason_catalog_covers_every_phase5_failure_and_transition`
- `test_phase5_import_graph_has_no_strategy_provider_or_execution_authority`

