from pathlib import Path


def test_continuity_backup_is_clean_hash_verified_and_non_authoritative():
    source=Path(__file__).with_name("create_obsidian_continuity_backup.ps1").read_text("utf-8")
    lowered=source.lower()
    assert source.isascii()
    assert "status --porcelain" in lowered
    assert "bundle create" in lowered and "bundle verify" in lowered
    assert lowered.count("safe.directory=")>=3
    assert "compress-archive" in lowered and "get-filehash" in lowered
    assert "raw_recorder_data_included=$false" in lowered
    assert "curated_canonical_and_bounded_recent" in lowered
    assert "select-object -first 10" in lowered
    assert "high-frequency logs" in lowered
    assert "trading_authority=$false" in lowered
    assert "project_journal.md" in lowered and "git history export failed" in lowered
    assert "canonical-strategy-status.json" in lowered and "runtime-result.json" in lowered
    assert "ninjatrader_canonical_smoke_history" in lowered
    assert "deterministic_repeat_verified" in lowered
    assert "ninjatrader_canonical_smoke_gate" in lowered
    assert "ninjatrader_canonical_smoke_acceptance" in lowered
    assert "ninjatrader_micro_instrument_specs" in lowered
    assert "ninjatrader_micro_paper_policy" in lowered
    assert "ninjatrader_shadow_profile_comparison" in lowered
    assert "ninjatrader_completed_shadow_trades" in lowered
    assert "ninjatrader-signal-lifecycle-status.json" in lowered
    assert "ninjatrader_gap_recovery" in lowered
    assert "canonical-replay.json" in lowered and "cross_source_equivalence_claimed" in lowered
    assert "ninjatrader-post-maintenance-gate.json" in lowered
    assert "ninjatrader-clean-day-gate.json" in lowered
    assert "forex_factory_shadow_trial" in lowered
    assert "session-attribution-v2.json" in lowered
    assert "performance-checkpoint.json" in lowered and "adapter-checkpoint.json" in lowered
    for field in ("decision_reason", "qualification_present", "entry_zone_present",
                  "fill_bindings", "net_result"):
        assert field in lowered
    for prohibited in ("private_key", "submit_order", "place_order"):
        assert prohibited not in lowered


def test_restore_verifier_is_isolated_integrity_checked_and_non_authoritative():
    source=Path(__file__).with_name("verify_obsidian_continuity_restore.ps1").read_text("utf-8")
    lowered=source.lower()
    assert "get-filehash" in lowered and "git clone" in lowered and "expand-archive" in lowered
    assert "gettemppath" in lowered and "restore path escaped" in lowered
    assert "repository_checkpoint" in lowered and "restore_verified" in lowered
    assert "trading_authority=$false" in lowered


def test_scheduled_backup_is_exact_limited_and_installed_disabled():
    root=Path(__file__).parent
    install=(root/"install_obsidian_continuity_backup_task.ps1").read_text("utf-8").lower()
    audit=(root/"audit_obsidian_continuity_backup_task.ps1").read_text("utf-8").lower()
    runner=(root/"run_obsidian_continuity_backup.ps1").read_text("utf-8").lower()
    assert "disable-scheduledtask" in install and "runlevel limited" in install
    assert "multipleinstances ignorenew" in install and "new-timespan -hours 6" in install
    assert "pt6h" in audit and "pt10m" in audit and "trading_authority=$false" in audit
    assert "create_obsidian_continuity_backup.ps1" in runner


def test_canonical_session_requires_vault_and_immediate_verified_backup():
    source=(Path(__file__).with_name("run_fresh_canonical_btc_paper_session.ps1")
        .read_text("utf-8").lower())
    assert "exact obsidian vault is unavailable" in source
    assert "run_obsidian_continuity_backup.ps1" in source
    assert "immediate obsidian backup failed" in source
    assert "$sessionexit = $lastexitcode" in source
    assert "paper_attribution_cohort_v1" in source
    assert "diagnostic evidence was backed up" in source
    assert source.index("supervised_btc_paper_launcher_v1") < source.index(
        "run_obsidian_continuity_backup.ps1")
    assert source.index("paper_attribution_cohort_v1") < source.index(
        "run_obsidian_continuity_backup.ps1")
    assert source.index("run_obsidian_continuity_backup.ps1") < source.index(
        "diagnostic evidence was backed up")
