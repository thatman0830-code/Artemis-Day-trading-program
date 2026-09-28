from pathlib import Path
import importlib.util


def load_cockpit_module():
    path = Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_cockpit.py"
    spec = importlib.util.spec_from_file_location("provider_neutral_cockpit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_analytics_is_fail_closed_when_no_trade_was_taken():
    analytics = load_cockpit_module().ledger_analytics()
    assert analytics["taken_sample_count"] == 0
    assert analytics["metric_status"] == "INSUFFICIENT_TAKEN_SAMPLE"
    assert analytics["win_rate"] is None
    assert analytics["profit_factor"] is None
    assert analytics["trading_authority"] is False
