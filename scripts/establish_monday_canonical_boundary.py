from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backtesting.ninjatrader_canonical_boundary_v1 import establish_boundary


def clean(value):
    if isinstance(value, datetime): return value.isoformat()
    if isinstance(value, tuple): return [clean(item) for item in value]
    if isinstance(value, dict): return {key: clean(item) for key, item in value.items()}
    return value


def main() -> int:
    boundary = establish_boundary(
        archive_root=ROOT / "data/ninjatrader_closed_bars",
        target_day=date(2026, 9, 14), as_of=datetime.now(timezone.utc))
    target = ROOT / "outputs/operational_health/ninjatrader-canonical-boundary-2026-09-14.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(clean(asdict(boundary)), sort_keys=True,
                                    separators=(",", ":")), encoding="utf-8")
    os.replace(temporary, target)
    print(target)
    return 0


if __name__ == "__main__": raise SystemExit(main())
