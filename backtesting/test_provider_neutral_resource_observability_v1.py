from pathlib import Path


def test_cockpit_publishes_resource_observability_without_authority():
    source = (Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_cockpit.py").read_text(encoding="utf-8")
    assert "resource_snapshot" in source
    assert "network_reachability" in source
    assert '"trading_authority": False' in source
