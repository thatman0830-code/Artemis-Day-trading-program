from pathlib import Path


def test_provider_neutral_launch_gate_is_paper_only():
    source = Path(__file__).parents[1] / "scripts" / "collect_provider_neutral_paper_launch_evidence.ps1"
    text = source.read_text(encoding="utf-8")
    assert "live_trading_permitted=$false" in text
    assert "ready_for_supervised_paper=$true" in text
