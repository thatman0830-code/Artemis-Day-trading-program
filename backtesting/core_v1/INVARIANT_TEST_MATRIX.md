# Core v1 invariant/test matrix

| Area | Invariant | Evidence | Result |
|---|---|---|---|
| Dependency | Strategy receives frozen state | `test_strategy_cannot_mutate_snapshot` | PASS |
| Scope | No future/cross-market bars | `test_strategy_view_is_market_and_time_bounded` | PASS |
| Ordering | Explicit priority and deterministic ties | `test_event_priority_is_stable` | PASS |
| Replay | Identical machine-result bytes | `test_wall_clock_does_not_change_machine_result` | PASS |
| Execution | t signal waits for next eligible bar | `test_signal_bar_cannot_fill_itself_and_next_open_is_used` | PASS |
| Data quality | Gap blocks fill/action | `test_data_quality_halt_blocks_same_bar_action_and_fill` | PASS |
| Execution | Non-tradable bar cannot fill | `test_nontradable_bar_does_not_fill` | PASS |
| Execution | Volume participation bounds fills | `test_volume_participation_creates_partial_fill` | PASS |
| Capability | Unsupported behavior fails closed | `test_capability_truthfully_rejects_unimplemented_behaviors` | PASS |
| Accounting | Reversal residual average resets | `test_reversal_resets_average_to_residual_fill_price` | PASS |
| Instrument | Scope/effective time/tick grid | `test_instrument_market_and_tick_grid_fail_closed` | PASS |
| Identity | Economic spec/seed changes ID | `test_result_identity_changes_for_economic_inputs` | PASS |
| Splits | Chronology and purge/embargo | `test_chronological_partitions_and_embargo` | PASS |
| Acceptance | Under 200 OOS is insufficient | `test_result_is_advisory_and_requires_200_oos` | PASS |
| Security | No network/order/secret capability | `test_core_source_has_no_network_or_external_order_path` | PASS |
| Archive | Native retained BTC/ES/NQ adapters | Read-only inspection | BLOCKED |
| Orders | Limit/stop/cancel/expiry | Capability report | UNSUPPORTED / FAIL-CLOSED |
| Lifecycle | Forced flatten/rollover execution | Capability report | UNSUPPORTED / FAIL-CLOSED |
| Economics | Funding/full attribution | Capability report/audit | UNSUPPORTED / FAIL-CLOSED |

