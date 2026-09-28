import json
from pathlib import Path

from backtesting.es_nq_research_artifact_registry_v1 import load_registry
from backtesting.es_nq_research_comparison_v1 import run_comparison


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "config" / "es_nq_research_artifact_registry.json"
CAPTURE = ROOT / "outputs" / "provider_neutral_paper_trial" / "live-capture-latest.json"


def test_current_capture_is_ready_for_replay_but_still_non_authoritative():
    capture = json.loads(CAPTURE.read_text(encoding="utf-8"))
    result = run_comparison(registry=load_registry(REGISTRY), capture=capture)
    assert result["state"] == "READY_FOR_REPLAY"
    assert result["findings"] == []
    assert len(result["modules"]) == 6
    assert all(row["signals_emitted"] == 0 for row in result["modules"])
    assert all(row["orders_emitted"] == 0 for row in result["modules"])
    assert result["paper_execution_permitted"] is False
    assert result["trading_authority"] is False
