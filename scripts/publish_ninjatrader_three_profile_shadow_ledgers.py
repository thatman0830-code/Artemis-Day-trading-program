"""Publish three isolated, non-executable ledgers from retained completed signals."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import json
import os
import uuid

from backtesting.ninjatrader_completed_trade_history_v1 import read_completed_shadow_trade_history
from backtesting.ninjatrader_three_profile_shadow_ledger_v1 import build_three_profile_shadow_ledgers


def clean(value):
    if isinstance(value, Decimal): return format(value, "f")
    if isinstance(value, Enum): return value.value
    if hasattr(value, "isoformat"): return value.isoformat()
    if isinstance(value, tuple): return [clean(x) for x in value]
    if isinstance(value, dict): return {k: clean(v) for k, v in value.items()}
    return value


def main():
    now = datetime.now(timezone.utc)
    trades = read_completed_shadow_trade_history(ROOT / "outputs/ninjatrader_completed_shadow_trades")
    ledgers = build_three_profile_shadow_ledgers(trades=trades, evaluated_at=now)
    document = {
        "schema_version": "ninjatrader-three-profile-shadow-ledger-publication-v1",
        "state": "COLLECTING_NO_COMPLETED_SIGNALS" if not trades else "COMPLETE",
        "evaluated_at": now.isoformat(), "input_trade_count": len(trades),
        "identical_input_signal_set_verified": True,
        "ledgers": [clean(asdict(x)) for x in ledgers],
        "comparison_only": True, "paper_execution_permitted": False,
        "live_trading_permitted": False, "trading_authority": False,
    }
    target = ROOT / "outputs/ninjatrader_three_profile_shadow_ledgers/latest.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x") as stream:
            json.dump(document, stream, sort_keys=True, separators=(",", ":"))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"schema_version": document["schema_version"],
        "state": document["state"], "ledger_count": len(ledgers),
        "input_trade_count": len(trades), "paper_execution_permitted": False,
        "trading_authority": False}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
