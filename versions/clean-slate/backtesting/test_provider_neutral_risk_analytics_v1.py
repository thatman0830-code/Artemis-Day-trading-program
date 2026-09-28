from pathlib import Path


def test_risk_analytics_is_review_only_and_does_not_invent_sample_metrics():
    source = (Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_risk_analytics.py").read_text(encoding="utf-8")
    assert '"expectancy_usd": None' in source
    assert '"automatic_policy_change_permitted": False' in source
    assert '"trading_authority": False' in source
