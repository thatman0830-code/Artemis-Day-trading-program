"""Publish a dated, read-only operational review for the paper campaign."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]


def read(path: str, default=None):
    target = ROOT / path
    return json.loads(target.read_text(encoding="utf-8")) if target.exists() else default

def ledger_summary():
    target = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"
    counts = {"TAKEN": 0, "SKIPPED": 0, "VETOED": 0}
    if target.exists():
        for line in target.read_text(encoding="utf-8").splitlines():
            try: classification = json.loads(line).get("decision_class")
            except json.JSONDecodeError: continue
            if classification in counts: counts[classification] += 1
    return {"counts": counts, "total": sum(counts.values())}


def main() -> None:
    cockpit = read("outputs/provider_neutral_paper_trial/cockpit-latest.json", {})
    health = read("outputs/provider_neutral_paper_trial/pipeline-supervisor-health.json", {})
    coverage = read("outputs/provider_neutral_paper_trial/coverage.json", {})
    adaptive = read("outputs/provider_neutral_paper_trial/adaptive-lane-latest.json", {})
    forex = read("outputs/forex_factory_shadow_trial/latest.json", {})
    scorecard = read("outputs/forex_factory_shadow_trial/decision-diagnostics/scorecard.json", {})
    ledger = cockpit.get("decision_ledger") or ledger_summary()
    observed = datetime.now(timezone.utc)
    review = {
        "schema_version": "provider-neutral-daily-review-v1",
        "review_date_utc": observed.date().isoformat(),
        "observed_at": observed.isoformat(),
        "pipeline": {
            "state": health.get("state", "UNKNOWN"),
            "consecutive_failures": health.get("consecutive_failures", 0),
            "bars_consumed": cockpit.get("pipeline", {}).get("bars_consumed", 0),
            "latency": cockpit.get("pipeline", {}).get("latency", {}),
        },
        "resources": cockpit.get("resources", {}),
        "authority": {
            "paper_execution_permitted": cockpit.get("authority", {}).get("paper_execution_permitted", False),
            "live_trading_permitted": cockpit.get("authority", {}).get("live_trading_permitted", False),
            "trading_authority": False,
        },
        "portfolios": cockpit.get("portfolios", []),
        "baseline_signal_status": cockpit.get("baseline", {}).get("signal_status", "UNKNOWN"),
        "adaptive_candidate_count": cockpit.get("adaptive", {}).get("candidate_count", 0),
        "decision_ledger": ledger,
        "analytics": cockpit.get("analytics", {"metric_status": "INSUFFICIENT_TAKEN_SAMPLE",
                                                   "read_only": True, "trading_authority": False}),
        "coverage": coverage,
        "news_trial": {
            "state": scorecard.get("state", "UNKNOWN"),
            "trial_days": forex.get("trial_days", []),
            "diagnostic_decisions": scorecard.get("decision_count", 0),
            "order_influence_permitted": False,
            "trading_authority": False,
        },
        "incidents": {
            "supervisor_error": health.get("error"),
            "unresolved_count": 0,
        },
        "review_questions": [
            "Were any inputs stale or out of order?",
            "Were any candidates rejected or vetoed correctly?",
            "Did any component require recovery or manual intervention?",
            "What must be fixed before the next supervised session?",
        ],
        "read_only": True,
        "trading_authority": False,
    }
    output = ROOT / "outputs/provider_neutral_paper_trial/daily-review" / f"{review['review_date_utc']}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(review, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tmp.replace(output)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": review["schema_version"], "path": str(output), "trading_authority": False}))


if __name__ == "__main__":
    main()
