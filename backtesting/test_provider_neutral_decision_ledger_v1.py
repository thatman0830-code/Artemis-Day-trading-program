from pathlib import Path


def test_decision_ledger_is_versioned_and_non_authoritative():
    source = (Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_decision_ledger.py").read_text(encoding="utf-8")
    assert "provider-neutral-decision-ledger-v1" in source
    assert '"expected_value": None' in source
    assert '"trading_authority": False' in source


def test_decision_ledger_has_explicit_shadow_classifications():
    source = (Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_decision_ledger.py").read_text(encoding="utf-8")
    assert '"decision_class": baseline_class' in source
    assert '"execution_quality"' in source
    assert '"fill_quality_score": None' in source
    assert '"rule_adherence": None' in source
    assert 'def classify_signal(signal_status):' in source
