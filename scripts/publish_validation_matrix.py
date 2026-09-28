"""Publish a fail-closed validation matrix for non-baseline research lanes."""
from datetime import datetime, timezone
from pathlib import Path
import json, uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/provider_neutral_paper_trial/validation-matrix-latest.json"

def read(rel, default=None):
    path = ROOT / rel
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default

def main():
    historical = read("outputs/provider_neutral_paper_trial/latest.json", {})
    capture = read("outputs/provider_neutral_paper_trial/live-capture-latest.json", {})
    adaptive = read("outputs/provider_neutral_paper_trial/adaptive-lane-latest.json", {})
    risk = read("outputs/provider_neutral_paper_trial/risk-analytics-latest.json", {})
    health = read("outputs/provider_neutral_paper_trial/pipeline-supervisor-health.json", {})
    hard_controls = read("outputs/provider_neutral_paper_trial/hard-controls-latest.json", {})
    cockpit = read("outputs/provider_neutral_paper_trial/cockpit-latest.json", {})
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
    paper_admission_findings = []
    if int(live_samples or 0) <= 0:
        paper_admission_findings.append("no_current_live_samples")
    if tuple(capture.get("diagnostics", {}).get("mapped_symbols", ())) != ("ES.c.0", "NQ.c.0"):
        paper_admission_findings.append("live_symbol_mapping_incomplete")
    stale_sample_count = capture.get("latency", {}).get("stale_sample_count")
    if capture.get("latency", {}).get("freshness_state") != "FRESH" or stale_sample_count is None or int(stale_sample_count) != 0:
        paper_admission_findings.append("live_feed_not_fresh")
    if health.get("state") != "HEALTHY" or health.get("trading_authority") is not False:
        paper_admission_findings.append("supervisor_not_healthy")
    if hard_controls.get("state") != "PASS" or hard_controls.get("trading_authority") is not False:
        paper_admission_findings.append("hard_controls_not_pass")
    if cockpit.get("authority", {}).get("paper_execution_permitted") is not True:
        paper_admission_findings.append("paper_authority_not_enabled")
    if cockpit.get("authority", {}).get("live_trading_permitted") is not False or cockpit.get("authority", {}).get("trading_authority") is not False:
        paper_admission_findings.append("live_authority_not_disabled")
    if int(cockpit.get("coverage", {}).get("covered_days", 0) or 0) < 5 or cockpit.get("coverage", {}).get("missing_or_unqualified_days"):
        paper_admission_findings.append("five_session_coverage_incomplete")
    doc = {"schema_version": "provider-neutral-validation-matrix-v1",
           "observed_at": datetime.now(timezone.utc).isoformat(), "lanes": lanes,
           "oos_progress": {"required_sessions": required_sessions,
                            "completed_sessions": completed_sessions,
                            "remaining_sessions": max(0, required_sessions - completed_sessions)},
           "paper_execution_permitted": authority.get("paper_execution_permitted", False),
           "live_trading_permitted": False, "trading_authority": False,
           # Historical/OOS research remains blocked until its 15-session
           # requirement is genuinely complete.  Supervised paper admission
           # has a separate evidence gate and never grants live authority.
           "release_gate": "BLOCKED_UNTIL_DATASET_MODEL_AND_CONTROLS_PASS",
           "paper_admission_gate": "READY_FOR_SUPERVISED_PAPER" if not paper_admission_findings else "BLOCKED",
           "paper_admission_findings": paper_admission_findings}
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
