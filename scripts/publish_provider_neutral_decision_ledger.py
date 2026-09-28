"""Append deterministic, non-authoritative decision evidence for each paper cycle."""
from datetime import datetime, timezone
import hashlib, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"


def read(name):
    path = ROOT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def decision_id(row):
    body = json.dumps(row, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def execution_quality(status, *, comparison_only=False):
    """Return review-only execution fields; never grants execution authority."""
    if status == "TAKEN":
        quality = "PENDING_FILL_REVIEW"
    elif status == "VETOED":
        quality = "VETOED_BEFORE_ORDER"
    elif status == "SKIPPED":
        quality = "NO_ORDER"
    else:
        quality = "NOT_APPLICABLE"
    return {
        "classification": status,
        "quality": quality,
        "comparison_only": comparison_only,
        "fill_quality_score": None,
        "slippage_realized": None,
        "rule_adherence": None,
    }


def classify_signal(signal_status):
    """Map an observed signal state to an auditable shadow-lifecycle class."""
    if signal_status == "NO_SIGNALS":
        return "SKIPPED"
    if signal_status == "SIGNAL":
        return "TAKEN"
    if signal_status in {"UNKNOWN", "INVALID", None}:
        return "VETOED"
    return "VETOED"


def main():
    cycle = read("outputs/provider_neutral_paper_trial/live-paper-cycle-latest.json")
    adaptive = read("outputs/provider_neutral_paper_trial/adaptive-lane-latest.json")
    evaluated_at = cycle.get("evaluated_at") or datetime.now(timezone.utc).isoformat()
    signal_status = cycle.get("signal_status", "UNKNOWN")
    # No signal is an explicit skipped decision, not missing telemetry.
    baseline_class = classify_signal(signal_status)
    rows = [{
        "decision_status": signal_status, "decision_class": baseline_class, "lane": "BASELINE",
        "evaluated_at": evaluated_at, "symbols": cycle.get("symbols", []),
        "probability_estimate": None, "expected_value": None, "volatility_regime": None,
        "assumed_slippage": None, "assumed_fees": None, "risk_fraction": "0R",
        "drawdown_state": "NORMAL", "strategy_version": "baseline-v1",
        "data_version": "provider-neutral-live-bars-v1", "model_version": "none",
        "paper_execution_permitted": cycle.get("paper_execution_permitted", False),
        "trading_authority": False,
    }]
    rows[0]["execution_quality"] = execution_quality(baseline_class)
    for report in adaptive.get("reports", []):
        candidate = report.get("candidate")
        adaptive_class = "SKIPPED" if candidate else "VETOED"
        rows.append({
            "decision_status": "ADAPTIVE_CANDIDATE" if candidate else "ADAPTIVE_REJECTED",
            "decision_class": adaptive_class,
            "lane": "ADAPTIVE_COMPARISON", "evaluated_at": report.get("evaluated_at", evaluated_at),
            "symbol": report.get("symbol"), "candidate_id": candidate.get("candidate_id") if candidate else None,
            "missing_confirmations": candidate.get("missing_confirmations", []) if candidate else [],
            "probability_estimate": None, "expected_value": None, "volatility_regime": None,
            "assumed_slippage": None, "assumed_fees": None,
            "risk_fraction": candidate.get("risk_fraction", "0R") if candidate else "0R",
            "drawdown_state": "NORMAL", "strategy_version": "adaptive-confirmation-lane-v1",
            "data_version": "provider-neutral-live-bars-v1", "model_version": "none",
            "paper_execution_permitted": False, "comparison_only": True, "trading_authority": False,
        })
        rows[-1]["execution_quality"] = execution_quality(adaptive_class, comparison_only=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if OUT.exists():
        for line in OUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try: existing.add(json.loads(line)["decision_id"])
                except (KeyError, json.JSONDecodeError): pass
    with OUT.open("a", encoding="utf-8") as stream:
        for row in rows:
            row["decision_id"] = decision_id(row)
            if row["decision_id"] not in existing:
                stream.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    print(json.dumps({"schema_version": "provider-neutral-decision-ledger-v1", "rows": len(rows), "trading_authority": False}))


if __name__ == "__main__": main()
