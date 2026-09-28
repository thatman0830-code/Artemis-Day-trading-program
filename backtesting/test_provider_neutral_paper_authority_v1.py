from pathlib import Path
import json

def test_paper_authority_scope_is_paper_only():
    root = Path(__file__).parents[1]
    scope = json.loads((root / "config/provider_neutral_paper_authority.json").read_text())
    assert scope["paper_execution_permitted"] is True
    assert scope["live_trading_permitted"] is False
    assert scope["trading_authority"] is False
    assert scope["profiles"] == ["CONSERVATIVE", "MODERATE", "AGGRESSIVE"]
