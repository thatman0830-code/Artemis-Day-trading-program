# BOT 2.0 Phase 5C v3 — Fresh Baseline Comparison

Run date: 2026-09-22. The comparison used the same Windows host, Python executable, pytest version, full-suite command, and corresponding clean-checkout test roots. No project-specific environment variables were set for either invocation.

## Invocation and environment

- Exact command on both worktrees: `python -m pytest -q`
- Python: `C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe` — Python 3.11.9
- pytest: 9.1.1
- Baseline checkout: `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3-baseline`
- Candidate checkout: `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`
- Baseline commit: `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94` (the documented clean pre-v3 protocol parent)
- Candidate source was the Phase 5C-V working tree on branch `bot2-phase5c-v-executable-controls`; the same tested source is committed as the review candidate after this report is prepared.
- Collection included the full repository test tree. No tests were deselected, xfailed, or xpassed; there were no collection errors.

## Counts

| Run | Collected | Passed | Failed | Skipped | Errors | Deselected | XFailed | XPassed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Clean baseline | 5,592 | 5,546 | 36 | 10 | 0 | 0 | 0 | 0 |
| Candidate | 5,606 | 5,560 | 36 | 10 | 0 | 0 | 0 | 0 |

Failure-node comparison:

- `BASELINE_ONLY_FAILURES`: 0
- `COMMON_FAILURES`: 36
- `CANDIDATE_ONLY_FAILURES`: 0
- `NEW_UNEXPLAINED_REGRESSIONS`: 0

The 14 additional collected/passing tests are the Phase 5C-V executable-control tests. The 36 common failures all reproduced in the clean baseline. Most are tests requiring ignored local `data/` or generated `outputs/` fixtures absent from both isolated checkouts; three require the repository-local pinned runtime/helper launch conditions. They are retained as failures rather than skipped or fabricated. The full repository suite is therefore not green.

## Exact common failure node IDs

```text
backtesting/test_es_nq_research_comparison_v1.py::test_current_capture_is_blocked_without_validated_samples
backtesting/test_provider_neutral_market_feed_v1.py::test_databento_replay_is_exposed_as_non_live_provider_neutral_feed
futures_data/test_archive_audit.py::test_final_archive_audit_report_is_complete_and_content_addressed
futures_data/test_backfill_preflight.py::test_real_probe_artifacts_recompute_and_are_market_isolated
futures_data/test_forward_bootstrap_refresh.py::test_retained_evidence_builds_zero_pending_immutable_bootstrap
futures_data/test_forward_bootstrap_refresh.py::test_installed_bootstrap_and_manifest_validate
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_raw_first_exact_contract_and_atomic_successor
futures_data/test_forward_bootstrap_refresh.py::test_contract_refresh_queries_bounded_lifecycle_index_not_weekend_point_in_time
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_accepts_only_newest_exact_contract_version
futures_data/test_forward_bootstrap_refresh.py::test_exact_contract_response_rejects_mislabeled_calendar_spread
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_untrusted_pagination_target[http://api.massive.com/futures/v1/schedules?cursor=x]
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_untrusted_pagination_target[https://evil.example/futures/v1/schedules?cursor=x]
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_untrusted_pagination_target[https://api.massive.com/futures/v1/contracts?cursor=x]
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_prohibited_contracts[micro]
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_prohibited_contracts[venue]
futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_prohibited_contracts[combo]
futures_data/test_forward_bootstrap_refresh.py::test_refresh_does_not_fabricate_non_contiguous_future_date
futures_data/test_forward_bootstrap_refresh.py::test_refresh_accepts_weekend_between_exclusive_boundary_and_next_session
futures_data/test_forward_bootstrap_refresh.py::test_refresh_horizon_boundary
futures_data/test_forward_bootstrap_refresh.py::test_future_rollover_is_prepared_but_not_decided
futures_data/test_forward_bootstrap_refresh.py::test_expired_contract_advances_to_verified_successor
futures_data/test_forward_bootstrap_refresh.py::test_successor_publication_is_versioned_and_pointer_is_checksum_verified
futures_data/test_forward_bootstrap_refresh.py::test_reconciled_current_configuration_avoids_duplicate_reference_request
futures_data/test_forward_collector.py::test_configuration_helper_runs_from_outside_repository
futures_data/test_forward_collector.py::test_configuration_helper_missing_manifest_is_one_sanitized_line
futures_data/test_pass_b_backfill.py::test_frozen_calendar_and_plan_are_complete_unique_and_bounded
futures_data/test_pass_b_backfill.py::test_rollovers_are_sparse_explicit_no_lookahead_and_no_fallback
futures_data/test_pass_b_backfill.py::test_calendar_holidays_early_closes_and_dst_are_source_exact
futures_data/test_pass_b_continuation.py::test_frozen_continuation_identity_links_and_caps
futures_data/test_pass_b_continuation.py::test_original_plan_and_caps_remain_immutable
futures_data/test_pass_b_continuation.py::test_retained_124_is_offline_and_first_fetch_is_125
futures_data/test_pass_b_continuation.py::test_cap_and_free_space_fail_closed
futures_data/test_pass_b_continuation.py::test_checkpoint_link_conflict_rejected
futures_data/test_rollover_backfill.py::test_actual_metadata_deduplicates_and_uses_lifecycle_year_and_excludes_far_future
futures_data/test_rollover_backfill.py::test_corrected_estimate_is_bounded_and_separate
futures_data/test_task_enable_policy.py::test_real_enable_helper_policy_path_runs_from_outside_repository
```

## Historical count discrepancy

Historical counts are not used as this phase's regression gate. The existing Phase 5C-V review material associated `5,546 passed / 36 failed / 10 skipped` with the clean baseline commit above and `5,555 / 36 / 10` with the earlier Phase 5C-S tree. The Phase 5C-T authorization separately quoted `5,554 / 36 / 10` without its matching raw run, commit, or collection record in the available repository history. This fresh run reproduces the recorded clean-baseline `5,546` result; the `5,554` figure remains unsupported by reproducible evidence. The new authoritative comparison is the exact node-ID comparison above, not historical aggregate counts.

Raw captured outputs are preserved in `docs/test_evidence/phase5c-v/baseline_full_suite.log` and `docs/test_evidence/phase5c-v/candidate_full_suite.log`.
