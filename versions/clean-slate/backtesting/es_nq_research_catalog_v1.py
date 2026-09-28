"""Expose the validated ES/NQ research package to the comparison pipeline.

This is a data catalog, not a signal engine.  Strategy fields are retained for
analysis and feature coverage checks, while every emitted record is explicitly
non-authoritative.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from backtesting.es_nq_research_artifact_registry_v1 import (
    ArtifactRegistry,
    validate_registry,
)


VERSION = "es-nq-research-catalog-v1"


def build_catalog(registry: ArtifactRegistry) -> dict[str, Any]:
    evidence = validate_registry(registry)
    if evidence["state"] != "READY_FOR_COMPARISON_ONLY":
        return {
            "schema_version": VERSION,
            "state": "QUARANTINED",
            "validation": evidence,
            "comparison_only": True,
            "signal_authorized": False,
            "paper_execution_permitted": False,
            "live_trading_permitted": False,
            "trading_authority": False,
        }

    specs = json.loads(registry.strategy_specs_path.read_text(encoding="utf-8"))
    modules = []
    for strategy in specs["strategies"]:
        modules.append({
            "id": strategy["id"],
            "name": strategy["name"],
            "deployment_status": strategy["deployment_status"],
            "instruments": strategy["instruments"],
            "spec": strategy,
            "comparison_only": True,
            "signal_authorized": False,
            "execution_authorized": False,
        })

    return {
        "schema_version": VERSION,
        "state": "READY_FOR_COMPARISON_ONLY",
        "research_cutoff": specs.get("research_cutoff"),
        "purpose": specs.get("purpose"),
        "principles": specs["principles"],
        "evidence_grades": specs["evidence_grades"],
        "trader_count": len(specs["traders"]),
        "source_count": len(specs["sources"]),
        "modules": modules,
        "risk_engine": specs["risk_engine"],
        "operations": specs["operations"],
        "validation": specs["validation"],
        "research_only": True,
        "comparison_only": True,
        "signal_authorized": False,
        "paper_execution_permitted": False,
        "live_trading_permitted": False,
        "trading_authority": False,
    }


def write_catalog(registry: ArtifactRegistry, output_path: str | Path) -> dict[str, Any]:
    catalog = build_catalog(registry)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return catalog
