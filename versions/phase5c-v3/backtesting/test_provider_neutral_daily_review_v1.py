from pathlib import Path


def test_daily_review_is_read_only_and_non_authoritative():
    source = Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_daily_review.py"
    text = source.read_text(encoding="utf-8")
    assert 'provider-neutral-daily-review-v1' in text
    assert '"read_only": True' in text
    assert '"trading_authority": False' in text
    assert '"decision_ledger": ledger' in text
    assert '"analytics": cockpit.get("analytics"' in text
