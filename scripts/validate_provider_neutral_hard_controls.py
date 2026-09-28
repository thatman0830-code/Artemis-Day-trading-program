"""Validate the deterministic risk-control contract without changing policy."""
from datetime import datetime, timezone
from pathlib import Path
import json, uuid

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/provider_neutral_hard_risk_controls.json"
OUT = ROOT / "outputs/provider_neutral_paper_trial/hard-controls-latest.json"

def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    required = ("max_risk_per_trade_pct", "max_daily_loss_pct", "max_portfolio_exposure_pct",
                "max_leverage", "max_data_age_seconds", "max_feed_latency_seconds",
                "max_drawdown_pct", "max_concurrent_positions")
    findings = []
    for key in required:
        value = cfg.get(key)
        if not isinstance(value, (int, float)) or value <= 0:
            findings.append(f"invalid:{key}")
    if cfg.get("max_risk_per_trade_pct", 99) > cfg.get("max_daily_loss_pct", 0):
        findings.append("per_trade_risk_exceeds_daily_loss")
    if cfg.get("max_leverage", 99) < 1:
        findings.append("leverage_below_one")
    if cfg.get("emergency_halt_on_unknown_state") is not True:
        findings.append("unknown_state_halt_not_enabled")
    if cfg.get("automatic_policy_change_permitted") is not False:
        findings.append("automatic_policy_change_enabled")
    if cfg.get("live_trading_permitted") is not False or cfg.get("trading_authority") is not False:
        findings.append("unauthorized_state")
    doc = {"schema_version": "provider-neutral-hard-controls-validation-v1",
           "observed_at": datetime.now(timezone.utc).isoformat(), "config_schema": cfg.get("schema_version"),
           "state": "PASS" if not findings else "FAIL", "findings": findings,
           "controls": cfg, "read_only": True, "trading_authority": False}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("." + OUT.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(doc, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        tmp.replace(OUT)
    finally: tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": doc["schema_version"], "state": doc["state"], "trading_authority": False}))
    if findings: raise SystemExit(1)

if __name__ == "__main__":
    main()
