"""Publish an evidence-based pre-market readiness state; never grants authority."""
from datetime import datetime, timezone
from pathlib import Path
import json, uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/provider_neutral_paper_trial/readiness-latest.json"

def read(rel):
    path = ROOT / rel
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def main():
    capture = read("outputs/provider_neutral_paper_trial/live-capture-latest.json")
    health = read("outputs/provider_neutral_paper_trial/pipeline-supervisor-health.json")
    matrix = read("outputs/provider_neutral_paper_trial/validation-matrix-latest.json")
    cockpit = read("outputs/provider_neutral_paper_trial/cockpit-latest.json")
    hard_controls = read("outputs/provider_neutral_paper_trial/hard-controls-latest.json")
    authority = read("config/provider_neutral_paper_authority.json")
    samples = int(capture.get("latency", {}).get("sample_count", 0) or 0)
    supervisor_ok = health.get("state") == "HEALTHY" and health.get("trading_authority") is False
    authority_safe = authority.get("live_trading_permitted") is False and authority.get("trading_authority") is False
    gate_open = matrix.get("release_gate") == "READY"
    findings = []
    if not supervisor_ok: findings.append("supervisor_not_healthy")
    if samples == 0: findings.append("databento_no_current_samples")
    if not gate_open: findings.append("validation_gate_blocked")
    if hard_controls.get("state") != "PASS": findings.append("hard_controls_not_validated")
    if not authority_safe: findings.append("authority_state_unsafe")
    state = "GREEN" if not findings else ("RED" if not authority_safe or not supervisor_ok else "YELLOW")
    doc = {"schema_version": "provider-neutral-readiness-v1", "observed_at": datetime.now(timezone.utc).isoformat(),
           "state": state, "findings": findings, "paper_start_blocked": bool(findings),
           "supervisor_state": health.get("state", "UNKNOWN"), "databento_sample_count": samples,
           "validation_release_gate": matrix.get("release_gate", "UNKNOWN"),
           "paper_execution_permitted": authority.get("paper_execution_permitted", False),
           "live_trading_permitted": False, "trading_authority": False,
           "cockpit_observed_at": cockpit.get("observed_at")}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("." + OUT.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        tmp.replace(OUT)
    finally: tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": doc["schema_version"], "state": state, "paper_start_blocked": doc["paper_start_blocked"], "trading_authority": False}))

if __name__ == "__main__": main()
