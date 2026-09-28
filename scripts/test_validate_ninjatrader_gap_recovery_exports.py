from pathlib import Path


def test_recovery_validator_is_read_only_and_non_authoritative():
    source = Path(__file__).with_name("validate_ninjatrader_gap_recovery_exports.py").read_text().lower()
    assert "read_ninjatrader_historical_export" in source and "independent_replay_eligible" in source
    assert "immutable_archive_repair_eligible\": false" in source
    assert "paper_execution_permitted\": false" in source and "trading_authority\": false" in source
    for prohibited in ("append_completed", "place_order", "submitorder", "private_key", "write_text"):
        assert prohibited not in source
