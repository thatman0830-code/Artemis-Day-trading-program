# BOT 2.0 Phase 5C-S — Clean Baseline and Full-Suite Comparison

## Reproduction environment

- Platform: Windows / PowerShell, same host and filesystem for both checkouts.
- Interpreter: Python 3.11.9 at `C:\Users\fjone\hyperliquid-trading-bot\.venv\Scripts\python.exe`.
- Dependencies: pytest 9.1.1, NumPy 2.4.6.
- Command for both runs: `python -m pytest -q` (invoked with the interpreter above).
- Clean baseline: `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3-baseline`, exact parent commit `ff81aa31d5cf1ea7168ceb2eaa017c0d50b47b94`.
- Remediation: `C:\Users\fjone\hyperliquid-trading-bot-phase5c-v3`, branch `bot2-phase5c-s-remediation`, based on the v3 protocol anchor `9a1ecfaf08077252049dd187d44f8641da1186aa`.

## Results

| Checkout | Passed | Skipped | Failed | Duration |
|---|---:|---:|---:|---:|
| Clean pre-v3 baseline | 5,546 | 10 | 36 | 84.54 s |
| Phase 5C-S remediation | 5,555 | 10 | 36 | 78.30 s |

The remediation branch adds nine passing Phase 5C v3 tests. Comparing the complete pytest failure IDs from the post-run cache against the clean-baseline cache yields 36 identical IDs, zero new failures, and zero baseline failures resolved. The suite therefore remains partially failing; it is not represented as green.

## Failure classification and fixture audit

All 36 failures reproduce in the clean baseline. Each has the exclusive classification `ENVIRONMENT_OR_FIXTURE_DEFICIENCY`; the clean-baseline reproduction is recorded as evidence that none is a Phase 5C-S regression. There are no `PHASE5C_REGRESSION` or `UNKNOWN` failures.

### Ignored local data and generated-evidence fixtures — 33 failures

These paths are ignored by `.gitignore` (`data/` and `outputs/`) and are therefore absent from a clean clone. The tests require them and do **not** skip when absent; they fail closed with missing-file/invalid-evidence errors. No market data was fabricated or downloaded. The corresponding data was found in the user's original local checkout at `C:\Users\fjone\hyperliquid-trading-bot`; it was not copied into either clean test checkout.

| Test(s) | Required ignored asset(s) / evidence | Available in original checkout? | Classification |
|---|---|---|---|
| `backtesting/test_es_nq_research_comparison_v1.py::test_current_capture_is_blocked_without_validated_samples` | `outputs/provider_neutral_paper_trial/live-capture-latest.json` | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| `backtesting/test_provider_neutral_market_feed_v1.py::test_databento_replay_is_exposed_as_non_live_provider_neutral_feed` | `data/databento_recovery_staging/` normalized replay and manifests | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| `futures_data/test_archive_audit.py::test_final_archive_audit_report_is_complete_and_content_addressed` | `data/backtests/es_nq_pass_b_archive_3/` and `outputs/archive_audits/es_nq_pass_b_final_audit.json` | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| `futures_data/test_backfill_preflight.py::test_real_probe_artifacts_recompute_and_are_market_isolated` | `data/backtests/es_probe_staging_2/`, `nq_probe_staging_2/` | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| All 19 failures in `futures_data/test_forward_bootstrap_refresh.py` | `data/backtests/es_nq_pass_b_plan_3/`, `es_nq_pass_b_archive_3/`, `es_nq_schedule_verification_2/`, `es_nq_rollover_discovery_plan_3/`, and derived ignored bootstrap/reference output | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| All 3 failures in `futures_data/test_pass_b_backfill.py` | Pass B plan/archive, schedule verification, and rollover discovery inputs listed above | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| All 5 failures in `futures_data/test_pass_b_continuation.py` | `data/backtests/es_nq_pass_b_continuation_plan_1/`, Pass B archive, checkpoint-linked continuation evidence | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| Both failures in `futures_data/test_rollover_backfill.py` | `data/backtests/es_backfill_preflight_1/`, `nq_backfill_preflight_1/`, `es_nq_rollover_discovery_plan_3/`, and `es_nq_rollover_discovery_1/` | Yes | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |

The original checkout's read-only inventory builder produced valid ES and NQ inventories (six contracts each). This supports that the missing local evidence is present outside the clean clone, but it does not convert the clean-clone failures to passes. The tests are data-dependent; silently skipping them or inventing replacement market fixtures would weaken the gate, so their current fail-closed behavior is retained.

### Branch-local Python runtime / platform helper fixtures — 3 failures

| Test | Expected asset | Observation | Classification |
|---|---|---|---|
| `futures_data/test_forward_collector.py::test_configuration_helper_runs_from_outside_repository` | Repository-local `.venv\Scripts\python.exe` | The isolated baseline/remediation clones have no repository-local venv. Helper returns `BLOCKED: Pinned repository Python is unavailable.` | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| `futures_data/test_forward_collector.py::test_configuration_helper_missing_manifest_is_one_sanitized_line` | Same repository-local pinned Python, then missing-manifest behavior | Runtime guard fires first, returning the pinned-Python message instead of the expected missing-manifest message. | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |
| `futures_data/test_task_enable_policy.py::test_real_enable_helper_policy_path_runs_from_outside_repository` | Repository-local `.venv\Scripts\python.exe` used by the PowerShell helper | PowerShell reports `Process.Start`: “The system cannot find the file specified”; the helper cannot launch its repository-pinned Python. | `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` |

The harness invoked pytest with the original checkout's Python explicitly, but the helper tests intentionally resolve Python relative to each test checkout. No task was enabled or started.

## Exact failed test IDs

Every ID below failed both the clean baseline and the Phase 5C-S branch and is classified `ENVIRONMENT_OR_FIXTURE_DEFICIENCY` for the documented missing fixture/runtime cause. This complete list is the 36/36 failure-set comparison.

1. `backtesting/test_es_nq_research_comparison_v1.py::test_current_capture_is_blocked_without_validated_samples`
2. `backtesting/test_provider_neutral_market_feed_v1.py::test_databento_replay_is_exposed_as_non_live_provider_neutral_feed`
3. `futures_data/test_archive_audit.py::test_final_archive_audit_report_is_complete_and_content_addressed`
4. `futures_data/test_backfill_preflight.py::test_real_probe_artifacts_recompute_and_are_market_isolated`
5. `futures_data/test_forward_bootstrap_refresh.py::test_retained_evidence_builds_zero_pending_immutable_bootstrap`
6. `futures_data/test_forward_bootstrap_refresh.py::test_installed_bootstrap_and_manifest_validate`
7. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_raw_first_exact_contract_and_atomic_successor`
8. `futures_data/test_forward_bootstrap_refresh.py::test_contract_refresh_queries_bounded_lifecycle_index_not_weekend_point_in_time`
9. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_accepts_only_newest_exact_contract_version`
10. `futures_data/test_forward_bootstrap_refresh.py::test_exact_contract_response_rejects_mislabeled_calendar_spread`
11. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_untrusted_pagination_target[http://api.massive.com/futures/v1/schedules?cursor=x]`
12. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_untrusted_pagination_target[https://evil.example/futures/v1/schedules?cursor=x]`
13. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_untrusted_pagination_target[https://api.massive.com/futures/v1/contracts?cursor=x]`
14. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_prohibited_contracts[micro]`
15. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_prohibited_contracts[venue]`
16. `futures_data/test_forward_bootstrap_refresh.py::test_reference_refresh_rejects_prohibited_contracts[combo]`
17. `futures_data/test_forward_bootstrap_refresh.py::test_refresh_does_not_fabricate_non_contiguous_future_date`
18. `futures_data/test_forward_bootstrap_refresh.py::test_refresh_accepts_weekend_between_exclusive_boundary_and_next_session`
19. `futures_data/test_forward_bootstrap_refresh.py::test_refresh_horizon_boundary`
20. `futures_data/test_forward_bootstrap_refresh.py::test_future_rollover_is_prepared_but_not_decided`
21. `futures_data/test_forward_bootstrap_refresh.py::test_expired_contract_advances_to_verified_successor`
22. `futures_data/test_forward_bootstrap_refresh.py::test_successor_publication_is_versioned_and_pointer_is_checksum_verified`
23. `futures_data/test_forward_bootstrap_refresh.py::test_reconciled_current_configuration_avoids_duplicate_reference_request`
24. `futures_data/test_forward_collector.py::test_configuration_helper_runs_from_outside_repository`
25. `futures_data/test_forward_collector.py::test_configuration_helper_missing_manifest_is_one_sanitized_line`
26. `futures_data/test_pass_b_backfill.py::test_frozen_calendar_and_plan_are_complete_unique_and_bounded`
27. `futures_data/test_pass_b_backfill.py::test_rollovers_are_sparse_explicit_no_lookahead_and_no_fallback`
28. `futures_data/test_pass_b_backfill.py::test_calendar_holidays_early_closes_and_dst_are_source_exact`
29. `futures_data/test_pass_b_continuation.py::test_frozen_continuation_identity_links_and_caps`
30. `futures_data/test_pass_b_continuation.py::test_original_plan_and_caps_remain_immutable`
31. `futures_data/test_pass_b_continuation.py::test_retained_124_is_offline_and_first_fetch_is_125`
32. `futures_data/test_pass_b_continuation.py::test_cap_and_free_space_fail_closed`
33. `futures_data/test_pass_b_continuation.py::test_checkpoint_link_conflict_rejected`
34. `futures_data/test_rollover_backfill.py::test_actual_metadata_deduplicates_and_uses_lifecycle_year_and_excludes_far_future`
35. `futures_data/test_rollover_backfill.py::test_corrected_estimate_is_bounded_and_separate`
36. `futures_data/test_task_enable_policy.py::test_real_enable_helper_policy_path_runs_from_outside_repository`

## Failure disposition

- Total classified: 36/36.
- `ENVIRONMENT_OR_FIXTURE_DEFICIENCY`: 36.
- `PHASE5C_REGRESSION`: 0.
- `UNKNOWN`: 0.
- New regressions: **0**.
- OOS evaluation/scored models: **0**.
