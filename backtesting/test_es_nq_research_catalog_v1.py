from pathlib import Path

from backtesting.es_nq_research_artifact_registry_v1 import load_registry
from backtesting.es_nq_research_catalog_v1 import build_catalog


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "es_nq_research_artifact_registry.json"


def test_full_package_is_available_to_comparison_pipeline():
    catalog = build_catalog(load_registry(REGISTRY))
    assert catalog["state"] == "READY_FOR_COMPARISON_ONLY"
    assert catalog["trader_count"] == 15
    assert len(catalog["modules"]) == 6
    assert all(module["deployment_status"] == "research_only" for module in catalog["modules"])
    assert all(module["signal_authorized"] is False for module in catalog["modules"])
    assert catalog["risk_engine"]["bypass_allowed"] is False
    assert catalog["validation"]["promotion_requires_human_review"] is True
    assert catalog["paper_execution_permitted"] is False
    assert catalog["trading_authority"] is False
