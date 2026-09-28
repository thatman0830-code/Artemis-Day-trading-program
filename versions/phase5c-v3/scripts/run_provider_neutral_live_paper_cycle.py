"""Consume canonical live bars into a read-only forward paper-cycle heartbeat."""
from pathlib import Path
from datetime import datetime, timezone
import json, os, uuid

ROOT = Path(__file__).resolve().parents[1]
STREAM = ROOT / "outputs/provider_neutral_paper_trial/live-bars.jsonl"
OUT = ROOT / "outputs/provider_neutral_paper_trial/live-paper-cycle-latest.json"
AUTHORITY = ROOT / "config/provider_neutral_paper_authority.json"

def main():
    bars = []
    if STREAM.exists():
        for line in STREAM.read_text(encoding="utf-8").splitlines():
            if line.strip(): bars.append(json.loads(line))
    symbols = sorted({b.get("symbol") for b in bars if b.get("symbol")})
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8")) if AUTHORITY.exists() else {}
    paper_enabled = authority.get("paper_execution_permitted") is True and authority.get("live_trading_permitted") is False
    now = datetime.now(timezone.utc).isoformat()
    document = {
        "schema_version": "provider-neutral-live-paper-cycle-v1",
        "evaluated_at": now,
        "bars_consumed": len(bars),
        "symbols": symbols,
        "signal_status": "NO_SIGNALS",
        "profiles": [{"profile": p, "starting_equity_usd": "50000", "ending_equity_usd": "50000", "trade_count": 0}
                     for p in ("CONSERVATIVE", "MODERATE", "AGGRESSIVE")],
        "comparison_only": True,
        "paper_execution_permitted": paper_enabled,
        "trading_authority": False,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_name("." + OUT.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        tmp.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(tmp, OUT)
    finally: tmp.unlink(missing_ok=True)
    print(json.dumps({"schema_version": document["schema_version"], "bars_consumed": len(bars),
                      "signal_status": "NO_SIGNALS", "trading_authority": False}, sort_keys=True))

if __name__ == "__main__": main()
