from __future__ import annotations

import json, sys, uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtesting.ninjatrader_clean_day_gate_v1 import evaluate_ninjatrader_clean_day_gate


def clean(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, tuple): return [clean(item) for item in value]
    if isinstance(value, dict): return {key: clean(item) for key, item in value.items()}
    return value


def main():
    gate = evaluate_ninjatrader_clean_day_gate(
        archive_root=ROOT / "data/ninjatrader_closed_bars", as_of=datetime.now(timezone.utc)
    )
    document = clean(asdict(gate))
    target = ROOT / "outputs/operational_health/ninjatrader-clean-day-gate.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(document, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    print(json.dumps(document, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__": main()
