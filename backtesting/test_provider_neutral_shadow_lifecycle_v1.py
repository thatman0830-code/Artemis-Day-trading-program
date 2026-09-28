from pathlib import Path
import importlib.util


def load_ledger_module():
    path = Path(__file__).parents[1] / "scripts" / "publish_provider_neutral_decision_ledger.py"
    spec = importlib.util.spec_from_file_location("provider_neutral_decision_ledger", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_synthetic_lifecycle_classifications_are_deterministic():
    module = load_ledger_module()
    assert module.classify_signal("NO_SIGNALS") == "SKIPPED"
    assert module.classify_signal("SIGNAL") == "TAKEN"
    assert module.classify_signal("INVALID") == "VETOED"
    assert module.classify_signal("UNKNOWN") == "VETOED"


def test_execution_quality_is_review_only_for_each_lifecycle():
    module = load_ledger_module()
    assert module.execution_quality("TAKEN")["quality"] == "PENDING_FILL_REVIEW"
    assert module.execution_quality("SKIPPED")["quality"] == "NO_ORDER"
    assert module.execution_quality("VETOED")["quality"] == "VETOED_BEFORE_ORDER"
    for status in ("TAKEN", "SKIPPED", "VETOED"):
        assert module.execution_quality(status)["fill_quality_score"] is None
        assert module.execution_quality(status)["rule_adherence"] is None
