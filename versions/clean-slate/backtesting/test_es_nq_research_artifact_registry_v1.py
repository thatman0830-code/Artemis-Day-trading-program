from pathlib import Path

from backtesting.es_nq_research_artifact_registry_v1 import load_registry, validate_registry


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "es_nq_research_artifact_registry.json"


def test_exact_package_is_hash_valid_and_comparison_only():
    evidence = validate_registry(load_registry(REGISTRY))
    assert evidence["state"] == "READY_FOR_COMPARISON_ONLY"
    assert evidence["strategy_ids"] == ["OR-1", "OR-2", "TP-1", "AR-1", "SQ-1", "MS-1"]
    assert evidence["trader_count"] == 15
    assert evidence["comparison_only"] is True
    assert evidence["signal_authorized"] is False
    assert evidence["paper_execution_permitted"] is False
    assert evidence["live_trading_permitted"] is False
    assert evidence["trading_authority"] is False
