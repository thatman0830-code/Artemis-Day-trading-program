"""Publish review-only portfolio risk analytics; never changes policy or sizing."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/provider_neutral_paper_trial/risk-analytics-latest.json"


def main():
    cycle_path = ROOT / "outputs/provider_neutral_paper_trial/live-paper-cycle-latest.json"
    ledger_path = ROOT / "outputs/provider_neutral_paper_trial/decision-ledger.jsonl"
    cycle = json.loads(cycle_path.read_text(encoding="utf-8")) if cycle_path.exists() else {}
    rows = []
    if ledger_path.exists():
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try: rows.append(json.loads(line))
                except json.JSONDecodeError: pass
    completed = [r for r in rows if r.get("outcome") in ("WIN", "LOSS", "COMPLETED") and r.get("pnl_usd") is not None]
    analytics = {
        "schema_version": "provider-neutral-risk-analytics-v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "sample_size": len(completed),
        "metrics": {
            "expectancy_usd": None,
            "profit_factor": None,
            "win_rate": None,
            "max_drawdown_usd": "0",
            "drawdown_state": "NORMAL",
            "risk_of_ruin_estimate": None,
            "correlation_exposure": "NOT_ESTIMABLE_NO_OPEN_POSITIONS",
            "fractional_kelly_reference": None,
        },
        "portfolio_profiles": cycle.get("profiles", []),
        "insufficient_sample_reason": "No completed paper outcomes are present; review metrics remain unestimated.",
        "automatic_policy_change_permitted": False,
        "read_only": True,
        "trading_authority": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name(f".{OUT.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(json.dumps(analytics, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tmp.replace(OUT)
    finally: tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": analytics["schema_version"], "sample_size": len(completed), "trading_authority": False}))


if __name__ == "__main__": main()
