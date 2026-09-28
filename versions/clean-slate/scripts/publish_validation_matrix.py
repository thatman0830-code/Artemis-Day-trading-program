"""Publish a fail-closed validation matrix for non-baseline research lanes."""
from datetime import datetime, timezone
from pathlib import Path
import json, uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/provider_neutral_paper_trial/validation-matrix-latest.json"

def read(rel, default=None):
    path = ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default

def main():
    historical = read("outputs/provider_neutral_paper_trial/latest.json", {})
    capture = read("outputs/provider_neutral_paper_trial/live-capture-latest.json", {})
    adaptive = read("outputs/provider_neutral_paper_trial/adaptive-lane-latest.json", {})
    risk = read("outputs/provider_neutral_paper_trial/risk-analytics-latest.json", {})
    authority = read("config/provider_neutral_paper_authority.json", {})

    days = historical.get("feeds", {}).get("ES", {}).get("days", [])
    completed_sessions = historical.get("completed_sessions", 0)
    required_sessions = int(historical.get("configured_sessions", 15))
    live_samples = capture.get("latency", {}).get("sample_count", 0)
    lanes = [
        {"lane": "baseline-historical-replay", "dataset": historical.get("feeds", {}).get("ES", {}).get("dataset_id"),
         "dataset_days": len(days), "model_version": "baseline-v1", "out_of_sample": completed_sessions >= required_sessions,
         "required_sessions": required_sessions, "completed_sessions": completed_sessions,
         "remaining_sessions": max(0, required_sessions - completed_sessions),
         "controls": ["paper-only", "three-profile-ledger", "risk-analytics"],
         "status": "VALIDATED_FOR_RESEARCH_ONLY" if days and completed_sessions >= required_sessions else "INCOMPLETE"},
        {"lane": "adaptive-confirmation", "dataset": "provider-neutral-historical-replay", "dataset_days": len(days),
         "model_version": "adaptive-confirmation-lane-v1", "out_of_sample": False,
         "controls": ["comparison-only", "no-order-influence", "baseline-unchanged"],
         "status": "BLOCKED_COMPARISON_ONLY"},
        {"lane": "databento-live-es-nq", "dataset": capture.get("dataset"), "dataset_days": 0,
         "model_version": "none", "out_of_sample": False,
         "controls": ["continuous-rollover", "latency-gate", "fail-closed"],
         "status": "BLOCKED_NO_SAMPLES" if live_samples == 0 else "PENDING_REVIEW",
         "symbols": capture.get("symbols", []), "mapping_symbols": capture.get("mapping_symbols", [])},
        {"lane": "risk-analytics", "dataset": risk.get("data_version"), "dataset_days": len(days),
         "model_version": risk.get("schema_version", "unknown"), "out_of_sample": False,
         "controls": ["review-only", "no-auto-sizing", "no-authority"], "status": "REVIEW_ONLY"},
    ]
    doc = {"schema_version": "provider-neutral-validation-matrix-v1",
           "observed_at": datetime.now(timezone.utc).isoformat(), "lanes": lanes,
           "oos_progress": {"required_sessions": required_sessions,
                            "completed_sessions": completed_sessions,
                            "remaining_sessions": max(0, required_sessions - completed_sessions)},
           "paper_execution_permitted": authority.get("paper_execution_permitted", False),
           "live_trading_permitted": False, "trading_authority": False,
           "release_gate": "BLOCKED_UNTIL_DATASET_MODEL_AND_CONTROLS_PASS"}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("." + OUT.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        tmp.replace(OUT)
    finally:
        tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": doc["schema_version"], "release_gate": doc["release_gate"], "trading_authority": False}))

if __name__ == "__main__":
    main()
