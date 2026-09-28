from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_evaluator_is_versioned_offline_and_non_authoritative():
    source = (ROOT / "scripts/evaluate_experimental_target_five_day.py").read_text()
    assert "CME_GLOBEX_1700_1600_AMERICA_CHICAGO_V1" not in source
    assert "SESSION_POLICY" in source
    assert '"canonical_policy_changed": False' in source
    assert '"paper_execution_permitted": False' in source
    assert '"trading_authority": False' in source
    for forbidden in ("SubmitOrder", "CreateOrder", "requests", "websocket"):
        assert forbidden not in source


def test_lifecycle_cannot_append_to_canonical_history_or_execute():
    source = (ROOT / "scripts/resolve_experimental_target_five_day_lifecycles.py").read_text()
    assert "build_three_profile_shadow_ledgers" in source
    assert '"canonical_history_modified": False' in source
    assert "append_completed_shadow_trade" not in source
    assert '"paper_execution_permitted": False' in source
    assert '"trading_authority": False' in source
    for forbidden in ("SubmitOrder", "CreateOrder", "from execution"):
        assert forbidden not in source
