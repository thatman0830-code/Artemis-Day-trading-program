from pathlib import Path


def test_runner_and_installer_are_shadow_only_and_single_instance():
    root = Path(__file__).resolve().parent
    runner = (root / "run_coinbase_btc_shadow_recorder.ps1").read_text("utf-8")
    installer = (root / "install_coinbase_btc_shadow_recorder_task.ps1").read_text("utf-8")
    combined = (runner + installer).lower()
    assert "coinbase btc public shadow recorder" in combined
    assert "tradingbot-coinbase-btc-shadow-recorder" in combined
    assert "-multipleinstances ignorenew" in combined
    assert "run_coinbase_btc_shadow_recorder.ps1" in installer
    for forbidden in ("private_key", "wallet", "submit_order", "exchange endpoint"):
        assert forbidden not in combined
