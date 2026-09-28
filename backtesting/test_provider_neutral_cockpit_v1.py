from pathlib import Path
import json

def test_cockpit_publishes_safe_scope():
    root = Path(__file__).parents[1]
    source = (root / "scripts/publish_provider_neutral_cockpit.py").read_text()
    assert "live_trading_permitted" in source
    assert '"trading_authority": False' in source
    assert '"decision_ledger": ledger' in source
    assert 'decision_class' in source
    assert 'provider-neutral-trading-analytics-v1' in source
    assert 'INSUFFICIENT_TAKEN_SAMPLE' in source
    assert '"profit_factor": None' in source
