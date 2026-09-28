"""Fail-closed plan-adherence analytics for the local paper-trial cockpit."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Iterable


VERSION = "tradersync-style-adherence-v1"
CLASSES = ("TAKEN", "SKIPPED", "VETOED")


def build_adherence_report(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(rows)
    counts = Counter(row.get("decision_class") for row in rows)
    by_lane: dict[str, dict[str, int]] = defaultdict(lambda: Counter())
    missing_controls: Counter[str] = Counter()
    reviewed = 0
    adhered = 0
    completed_outcomes = []

    for row in rows:
        lane = row.get("lane") or "UNSPECIFIED"
        decision_class = row.get("decision_class")
        if decision_class in CLASSES:
            by_lane[lane][decision_class] += 1
        quality = row.get("execution_quality") or {}
        if decision_class == "TAKEN":
            value = quality.get("rule_adherence")
            if isinstance(value, bool):
                reviewed += 1
                adhered += int(value)
            elif value is None:
                missing_controls["rule_adherence"] += 1
            if row.get("outcome") is not None or row.get("pnl") is not None:
                completed_outcomes.append(row)
        if decision_class in {"VETOED", "SKIPPED"} and quality.get("quality") is None:
            missing_controls["lifecycle_quality"] += 1

    taken = counts.get("TAKEN", 0)
    report: dict[str, Any] = {
        "schema_version": VERSION,
        "decision_count": len(rows),
        "decision_counts": {name: counts.get(name, 0) for name in CLASSES},
        "by_lane": {lane: dict(values) for lane, values in by_lane.items()},
        "taken_sample_count": taken,
        "adherence_reviewed_count": reviewed,
        "plan_adherence_rate": (adhered / reviewed) if reviewed else None,
        "missing_rule_evidence": dict(missing_controls),
        "what_if_status": "READY" if completed_outcomes else "INSUFFICIENT_COMPLETED_OUTCOMES",
        "what_if_outcome_count": len(completed_outcomes),
        "profit_factor": None,
        "win_rate": None,
        "read_only": True,
        "comparison_only": True,
        "paper_execution_permitted": False,
        "live_trading_permitted": False,
        "trading_authority": False,
    }
    report["metric_status"] = "READY" if taken and reviewed else "INSUFFICIENT_REVIEWED_TAKEN_SAMPLE"
    return report
