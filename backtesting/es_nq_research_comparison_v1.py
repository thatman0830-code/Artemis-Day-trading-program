"""Fail-closed comparison gate for the six ES/NQ research modules.

This milestone only admits validated replay inputs.  It does not generate
signals, choose direction, place orders, or change the baseline strategy.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from backtesting.es_nq_research_catalog_v1 import build_catalog
from backtesting.es_nq_research_artifact_registry_v1 import ArtifactRegistry


VERSION = "es-nq-research-comparison-v1"
EXPECTED_SYMBOLS = ("ES.c.0", "NQ.c.0")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_comparison(*, registry: ArtifactRegistry, capture: Mapping[str, Any],
                   evaluated_at: str | None = None) -> dict[str, Any]:
    catalog = build_catalog(registry)
    modules = catalog.get("modules", [])
    counts = capture.get("record_counts", {})
    diagnostics = capture.get("diagnostics", {})
    mapped = tuple(diagnostics.get("mapped_symbols", ()))
    sample_count = sum(int(counts.get(symbol, 0)) for symbol in EXPECTED_SYMBOLS)

    findings: list[str] = []
    if catalog.get("state") != "READY_FOR_COMPARISON_ONLY":
        findings.append("research_catalog_not_ready")
    if mapped != EXPECTED_SYMBOLS:
        findings.append("es_nq_symbol_mapping_incomplete")
    if sample_count <= 0:
        findings.append("no_validated_current_samples")
    if capture.get("trading_authority") is not False:
        findings.append("capture_authority_not_false")
    if capture.get("paper_execution_permitted") is not False:
        findings.append("capture_paper_execution_not_false")

    state = "READY_FOR_REPLAY" if not findings else "BLOCKED"
    module_rows = [
        {
            "module_id": module["id"],
            "status": state,
            "signals_emitted": 0,
            "orders_emitted": 0,
            "direction_inferred": False,
            "comparison_only": True,
        }
        for module in modules
    ]
    return {
        "schema_version": VERSION,
        "evaluated_at": evaluated_at or _utc_now(),
        "state": state,
        "findings": findings,
        "sample_count": sample_count,
        "mapped_symbols": list(mapped),
        "modules": module_rows,
        "baseline_unchanged": True,
        "comparison_only": True,
        "signal_authorized": False,
        "paper_execution_permitted": False,
        "live_trading_permitted": False,
        "trading_authority": False,
    }
