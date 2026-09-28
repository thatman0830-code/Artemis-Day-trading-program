"""Hash-pinned ingestion and fail-closed validation for the ES/NQ research package."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


VERSION = "es-nq-research-artifact-registry-v1"
EXPECTED_STRATEGIES = ("OR-1", "OR-2", "TP-1", "AR-1", "SQ-1", "MS-1")
REQUIRED_TOP_LEVEL = (
    "principles", "evidence_grades", "traders", "strategies", "risk_engine",
    "operations", "validation", "sources",
)


@dataclass(frozen=True)
class ArtifactRegistry:
    strategy_specs_path: Path
    trader_package_path: Path
    strategy_specs_sha256: str
    trader_package_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_registry(path: str | Path) -> ArtifactRegistry:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != VERSION:
        raise ValueError("unsupported artifact registry schema")
    return ArtifactRegistry(
        strategy_specs_path=Path(raw["strategy_specs_path"]),
        trader_package_path=Path(raw["trader_package_path"]),
        strategy_specs_sha256=str(raw["strategy_specs_sha256"]).upper(),
        trader_package_sha256=str(raw["trader_package_sha256"]).upper(),
    )


def validate_registry(registry: ArtifactRegistry) -> dict[str, Any]:
    """Validate exact artifacts; result is evidence only, never an execution gate."""
    findings: list[str] = []
    if not registry.strategy_specs_path.is_file():
        findings.append("strategy_specs_missing")
    if not registry.trader_package_path.is_file():
        findings.append("trader_package_missing")
    if not findings:
        if _sha256(registry.strategy_specs_path) != registry.strategy_specs_sha256:
            findings.append("strategy_specs_hash_mismatch")
        if _sha256(registry.trader_package_path) != registry.trader_package_sha256:
            findings.append("trader_package_hash_mismatch")

    strategies: list[dict[str, Any]] = []
    raw: dict[str, Any] = {}
    if not findings:
        raw = json.loads(registry.strategy_specs_path.read_text(encoding="utf-8"))
        findings.extend(f"missing_top_level:{key}" for key in REQUIRED_TOP_LEVEL if key not in raw)
        strategies = raw.get("strategies", [])
        ids = tuple(item.get("id") for item in strategies)
        if ids != EXPECTED_STRATEGIES:
            findings.append("strategy_set_mismatch")
        if raw.get("default_deployment_status") != "research_only":
            findings.append("default_deployment_not_research_only")
        if any(item.get("deployment_status") != "research_only" for item in strategies):
            findings.append("strategy_not_research_only")
        if raw.get("risk_engine", {}).get("bypass_allowed") is not False:
            findings.append("risk_bypass_not_disabled")
        if raw.get("validation", {}).get("promotion_requires_human_review") is not True:
            findings.append("human_promotion_review_missing")
        if len(raw.get("traders", [])) != 15:
            findings.append("trader_roster_count_mismatch")

    return {
        "schema_version": VERSION,
        "state": "READY_FOR_COMPARISON_ONLY" if not findings else "QUARANTINED",
        "findings": findings,
        "strategy_ids": [item.get("id") for item in strategies],
        "trader_count": len(raw.get("traders", [])),
        "comparison_only": True,
        "signal_authorized": False,
        "paper_execution_permitted": False,
        "live_trading_permitted": False,
        "trading_authority": False,
    }
