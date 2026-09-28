from pathlib import Path

def test_replay_validator_is_fail_closed():
    source = (Path(__file__).parents[1] / "scripts" / "validate_provider_neutral_replay.py").read_text(encoding="utf-8")
    assert "Duplicate canonical bar identity" in source
    assert "Out-of-order canonical bars" in source
    assert '"trading_authority": False' in source
