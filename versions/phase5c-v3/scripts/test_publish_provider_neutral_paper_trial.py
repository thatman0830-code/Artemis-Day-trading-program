from pathlib import Path


def test_publisher_is_non_executable_and_uses_owned_trial_schema():
    source = Path(__file__).with_name("publish_provider_neutral_paper_trial.py").read_text()
    assert "provider_neutral_paper_trial" in source
    assert "market_data_live_connected\": False" in source
    assert "paper_execution_permitted\": False" in source
    assert "trading_authority\": False" in source
    assert "SubmitOrder" not in source and "CreateOrder" not in source
