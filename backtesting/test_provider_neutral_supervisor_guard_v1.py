from pathlib import Path


def test_supervisor_guard_is_fail_closed_and_paper_only():
    source = Path(__file__).parents[1] / "scripts" / "guard_provider_neutral_supervisor.ps1"
    text = source.read_text(encoding="utf-8")
    assert "live_trading_permitted -eq $false" in text
    assert "trading_authority -eq $false" in text
    assert "cockpit-stale-" in text
