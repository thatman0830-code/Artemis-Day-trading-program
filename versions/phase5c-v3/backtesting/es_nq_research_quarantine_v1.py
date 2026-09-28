"""Fail-closed quarantine for externally supplied ES/NQ strategy research.

Research claims are useful inputs for comparison experiments, but they are not
strategy authorization.  This module deliberately does not emit signals,
orders, sizing, or trading direction.  It only validates that a research
manifest is explicitly marked research-only and returns non-authoritative
admission evidence for the comparison lane.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping


VERSION = "es-nq-research-quarantine-v1"
REQUIRED_MODULES = (
    "opening_range_continuation_failure",
    "trend_pullback_resumption",
    "regime_classification",
)


@dataclass(frozen=True)
class ResearchModule:
    module_id: str
    hypothesis: str
    evidence_grade: str
    research_only: bool
    comparison_only: bool
    signal_authorized: bool
    execution_authorized: bool


@dataclass(frozen=True)
class ResearchQuarantine:
    package_id: str
    source_artifacts_present: bool
    modules: tuple[ResearchModule, ...]
    walk_forward_required: bool
    monte_carlo_required: bool
    staged_micro_deployment_required: bool
    paper_execution_permitted: bool
    live_trading_permitted: bool
    trading_authority: bool
    schema_version: str = VERSION


def _bool(raw: Mapping[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def load_research_quarantine(path: str | Path) -> ResearchQuarantine:
    """Load and validate a research manifest; reject unsafe promotion flags."""

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != VERSION:
        raise ValueError("unsupported research quarantine schema")
    modules_raw = raw.get("modules")
    if not isinstance(modules_raw, list):
        raise ValueError("modules must be a list")

    modules: list[ResearchModule] = []
    for item in modules_raw:
        if not isinstance(item, dict):
            raise ValueError("each module must be an object")
        modules.append(
            ResearchModule(
                module_id=str(item["module_id"]),
                hypothesis=str(item["hypothesis"]),
                evidence_grade=str(item["evidence_grade"]),
                research_only=_bool(item, "research_only"),
                comparison_only=_bool(item, "comparison_only"),
                signal_authorized=_bool(item, "signal_authorized"),
                execution_authorized=_bool(item, "execution_authorized"),
            )
        )

    if tuple(module.module_id for module in modules) != REQUIRED_MODULES:
        raise ValueError("research module set does not match the approved quarantine set")
    if any(
        not module.research_only
        or not module.comparison_only
        or module.signal_authorized
        or module.execution_authorized
        for module in modules
    ):
        raise ValueError("research modules cannot be promoted through this manifest")

    return ResearchQuarantine(
        package_id=str(raw["package_id"]),
        source_artifacts_present=_bool(raw, "source_artifacts_present"),
        modules=tuple(modules),
        walk_forward_required=_bool(raw, "walk_forward_required"),
        monte_carlo_required=_bool(raw, "monte_carlo_required"),
        staged_micro_deployment_required=_bool(raw, "staged_micro_deployment_required"),
        paper_execution_permitted=_bool(raw, "paper_execution_permitted"),
        live_trading_permitted=_bool(raw, "live_trading_permitted"),
        trading_authority=_bool(raw, "trading_authority"),
    )


def comparison_admission(quarantine: ResearchQuarantine) -> dict[str, Any]:
    """Return non-authoritative evidence; never enables simulator execution."""

    ready = (
        quarantine.source_artifacts_present
        and quarantine.walk_forward_required
        and quarantine.monte_carlo_required
        and not quarantine.paper_execution_permitted
        and not quarantine.live_trading_permitted
        and not quarantine.trading_authority
    )
    return {
        "schema_version": VERSION,
        "package_id": quarantine.package_id,
        "state": "COMPARISON_ADMISSIBLE" if ready else "QUARANTINED",
        "source_artifacts_present": quarantine.source_artifacts_present,
        "module_ids": [module.module_id for module in quarantine.modules],
        "comparison_only": True,
        "signal_authorized": False,
        "paper_execution_permitted": False,
        "live_trading_permitted": False,
        "trading_authority": False,
        "reason": (
            "validated research artifact may enter comparison lane"
            if ready
            else "source/evidence gates incomplete; no promotion permitted"
        ),
    }
