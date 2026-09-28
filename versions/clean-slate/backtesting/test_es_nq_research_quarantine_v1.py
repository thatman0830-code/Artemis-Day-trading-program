import json
from pathlib import Path

import pytest

from backtesting.es_nq_research_quarantine_v1 import (
    VERSION,
    comparison_admission,
    load_research_quarantine,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "es_nq_research_quarantine.json"


def test_supplied_research_manifest_is_quarantined():
    quarantine = load_research_quarantine(MANIFEST)
    evidence = comparison_admission(quarantine)
    assert evidence["state"] == "QUARANTINED"
    assert evidence["comparison_only"] is True
    assert evidence["signal_authorized"] is False
    assert evidence["paper_execution_permitted"] is False
    assert evidence["live_trading_permitted"] is False
    assert evidence["trading_authority"] is False


def test_manifest_rejects_any_attempt_to_promote_module(tmp_path):
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    raw["modules"][0]["execution_authorized"] = True
    path = tmp_path / "unsafe.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot be promoted"):
        load_research_quarantine(path)


def test_manifest_schema_is_explicit():
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert raw["schema_version"] == VERSION
    assert raw["source_artifacts_present"] is False
    assert raw["walk_forward_required"] is True
    assert raw["monte_carlo_required"] is True
